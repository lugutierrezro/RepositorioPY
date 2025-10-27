# app.py (versión mejorada con control remoto de IP)
import cv2
import time
import requests
import threading
import numpy as np
import json
from io import BytesIO
from flask import Flask, jsonify, request
from ultralytics import YOLO

app = Flask(__name__)

# ========== CONFIGURACIÓN ==========
BOT_TOKEN = "8387352187:AAHjaAerl7CYtabW37TEfzZKgitApSSPgSE"
CHAT_ID = "7138077762"
CLASES_INTERES = None
UMBRAL_CONF = 0.5
COOLDOWN_S = 10

# ✅ IP DINÁMICA - Se actualiza desde el móvil
URL_STREAM = "http://192.168.1.78:81/stream"  # IP por defecto
CONFIG_FILE = "camera_config.json"  # Guardar configuración

# Clave de seguridad (cámbiala por una propia)
API_KEY = "SolarPanelPro_Despiadado"  # ⚠️ IMPORTANTE: Cámbiala

# ========== VARIABLES GLOBALES ==========
model = None
ultimo_envio = 0
detection_active = False
detection_thread = None
stats = {
    'detections_today': 0,
    'last_detection': None,
    'status': 'Inicializando...',
    'current_camera_ip': URL_STREAM
}


# ========== FUNCIONES DE CONFIGURACIÓN ==========
def cargar_configuracion():
    """Carga la IP guardada del archivo"""
    global URL_STREAM
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            URL_STREAM = config.get('stream_url', URL_STREAM)
            stats['current_camera_ip'] = URL_STREAM
            print(f"✅ Configuración cargada: {URL_STREAM}")
    except FileNotFoundError:
        print("⚠️ Archivo de configuración no encontrado, usando IP por defecto")
        guardar_configuracion()
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")


def guardar_configuracion():
    """Guarda la IP actual en archivo"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'stream_url': URL_STREAM}, f)
        print(f"✅ Configuración guardada: {URL_STREAM}")
    except Exception as e:
        print(f"❌ Error guardando configuración: {e}")


def validar_ip(ip_str):
    """Valida formato de IP o URL"""
    import re
    # Patrón para IP:puerto o URL completa
    pattern = r'^https?://[\d\.:a-zA-Z-]+(/\w+)?$'
    return re.match(pattern, ip_str) is not None


# ========== FUNCIONES EXISTENTES ==========
def cargar_modelo():
    global model
    try:
        print("🔄 Cargando modelo YOLO11...")
        model = YOLO("yolo11n.pt")
        print("✅ Modelo YOLO11 cargado exitosamente")
        stats['status'] = 'Modelo cargado'
    except Exception as e:
        print(f"❌ Error cargando modelo: {e}")
        stats['status'] = f'Error: {e}'


def enviar_telegram_imagen(frame_bgr, mensaje="🚨 Detección de objetos"):
    try:
        _, buffer = cv2.imencode('.jpg', frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        files = {'photo': ('detection.jpg', BytesIO(buffer.tobytes()), 'image/jpeg')}
        data = {
            'chat_id': CHAT_ID,
            'caption': mensaje
        }
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        resp = requests.post(url, files=files, data=data, timeout=15)
        resp.raise_for_status()
        print(f"✅ Imagen enviada a Telegram")
        return True
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")
        return False


def detectar_objetos_continuo():
    global ultimo_envio, detection_active, stats, URL_STREAM
    
    detection_active = True
    stats['status'] = 'Conectando al stream...'
    
    intentos_reconexion = 0
    max_intentos = 5
    
    while detection_active:
        cap = None
        try:
            print(f"🔄 Conectando al stream: {URL_STREAM}")
            cap = cv2.VideoCapture(URL_STREAM)
            
            if not cap.isOpened():
                raise Exception("No se pudo abrir el stream")
            
            stats['status'] = 'Detectando objetos...'
            intentos_reconexion = 0
            
            frame_count = 0
            
            while detection_active:
                ret, frame = cap.read()
                
                if not ret:
                    print("⚠️ No se pudo leer frame del stream")
                    break
                
                frame_count += 1
                
                if frame_count % 3 != 0:
                    continue
                
                results = model(frame, stream=True, verbose=False)
                
                hay_detecciones_interes = False
                objetos_detectados = []
                
                for result in results:
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        
                        if conf < UMBRAL_CONF:
                            continue
                        
                        if CLASES_INTERES is not None and cls not in CLASES_INTERES:
                            continue
                        
                        hay_detecciones_interes = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        label = f"{model.names.get(cls, str(cls))} {conf:.2f}"
                        cv2.putText(frame, label, (x1, max(0, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        objetos_detectados.append(model.names.get(cls, str(cls)))
                
                ahora = time.time()
                if hay_detecciones_interes and (ahora - ultimo_envio) >= COOLDOWN_S:
                    mensaje = f"🚨 Detectado: {', '.join(set(objetos_detectados))}"
                    if enviar_telegram_imagen(frame, mensaje):
                        ultimo_envio = ahora
                        stats['detections_today'] += 1
                        stats['last_detection'] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                time.sleep(0.1)
        
        except Exception as e:
            print(f"❌ Error en detección: {e}")
            stats['status'] = f'Error: {e}'
            intentos_reconexion += 1
            
            if intentos_reconexion >= max_intentos:
                print(f"❌ Máximo de intentos alcanzado. Esperando nueva IP...")
                stats['status'] = 'Esperando nueva configuración de IP'
                detection_active = False
                break
            
            print(f"🔄 Reintentando en 10 segundos...")
            time.sleep(10)
        
        finally:
            if cap is not None:
                cap.release()


# ========== ENDPOINTS FLASK ==========
@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'ESP32-CAM Object Detection',
        'detections_today': stats['detections_today'],
        'last_detection': stats['last_detection'],
        'detection_status': stats['status'],
        'current_camera_ip': stats['current_camera_ip']
    })


@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'detection_active': detection_active,
        'camera_ip': URL_STREAM
    })


@app.route('/stats')
def get_stats():
    return jsonify(stats)


# ✅ NUEVO: Actualizar IP desde el móvil
@app.route('/update-camera-ip', methods=['POST'])
def update_camera_ip():
    """Endpoint para actualizar la IP de la cámara desde Flutter"""
    global URL_STREAM, detection_active, detection_thread
    
    try:
        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if api_key != API_KEY:
            return jsonify({
                'status': 'error',
                'message': 'API Key inválida'
            }), 401
        
        data = request.get_json()
        
        if not data or 'camera_ip' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Falta el campo camera_ip'
            }), 400
        
        new_ip = data['camera_ip']
        port = data.get('port', '81')  # Puerto por defecto
        stream_path = data.get('stream_path', '/stream')  # Ruta por defecto
        
        # Construir URL completa
        new_url = f"http://{new_ip}:{port}{stream_path}"
        
        # Validar formato
        if not validar_ip(new_url):
            return jsonify({
                'status': 'error',
                'message': 'Formato de URL inválido'
            }), 400
        
        # Detener detección actual
        detection_active = False
        time.sleep(2)  # Esperar a que termine el thread actual
        
        # Actualizar IP
        URL_STREAM = new_url
        stats['current_camera_ip'] = URL_STREAM
        
        # Guardar configuración
        guardar_configuracion()
        
        # Reiniciar detección con nueva IP
        detection_active = True
        detection_thread = threading.Thread(target=detectar_objetos_continuo, daemon=True)
        detection_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'IP actualizada correctamente',
            'new_url': URL_STREAM
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ✅ NUEVO: Obtener IP actual
@app.route('/get-camera-ip', methods=['GET'])
def get_camera_ip():
    """Obtener la IP actual de la cámara"""
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
    
    return jsonify({
        'status': 'success',
        'camera_ip': URL_STREAM,
        'is_detecting': detection_active
    })


@app.route('/test-telegram')
def test_telegram():
    try:
        img = np.zeros((400, 600, 3), dtype=np.uint8)
        cv2.putText(img, "Test desde Render", (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        if enviar_telegram_imagen(img, "🧪 Prueba de conexión"):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/start-detection')
def start_detection():
    global detection_active, detection_thread
    if not detection_active:
        detection_active = True
        detection_thread = threading.Thread(target=detectar_objetos_continuo, daemon=True)
        detection_thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})


@app.route('/stop-detection')
def stop_detection():
    global detection_active
    detection_active = False
    return jsonify({'status': 'stopped'})


# ========== INICIO DEL SERVICIO ==========
if __name__ == '__main__':
    # Cargar configuración guardada
    cargar_configuracion()
    
    # Cargar modelo
    cargar_modelo()
    
    # Iniciar detección
    detection_thread = threading.Thread(target=detectar_objetos_continuo, daemon=True)
    detection_thread.start()
    
    # Iniciar servidor Flask
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
