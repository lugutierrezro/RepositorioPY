# app.py - Endpoint completo con captura a Telegram
from flask import Flask, jsonify, request
import json
import os
import requests
from io import BytesIO

app = Flask(__name__)

# Configuración
API_KEY = "SolarPanelPro_Despiadado"
CONFIG_FILE = "camera_config.json"

# Telegram
BOT_TOKEN = "8387352187:AAHjaAerl7CYtabW37TEfzZKgitApSSPgSE"
CHAT_ID = "7138077762"

# Estado global
config = {
    'camera_ip': '192.168.1.78',
    'port': '81',
    'stream_path': '/stream',
    'last_update': None,
}


def cargar_configuracion():
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config.update(json.load(f))
            print(f"✅ Config cargada: {config}")
    except Exception as e:
        print(f"⚠️ Error cargando config: {e}")


def guardar_configuracion():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print("✅ Config guardada")
    except Exception as e:
        print(f"❌ Error guardando: {e}")


def validar_api_key(key):
    return key == API_KEY


# ========== FUNCIONES DE CAPTURA ==========

def capturar_imagen_esp32cam():
    """Intenta capturar imagen de la ESP32-CAM usando múltiples métodos"""
    camera_ip = config['camera_ip']
    port = config['port']
    
    # Lista de URLs a intentar
    urls_to_try = [
        f"http://{camera_ip}:{port}/capture",
        f"http://{camera_ip}:{port}/jpg",
        f"http://{camera_ip}:{port}/cam-lo.jpg",
        f"http://{camera_ip}:{port}/cam-hi.jpg",
    ]
    
    for url in urls_to_try:
        try:
            print(f"📸 Intentando capturar desde: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200 and len(response.content) > 1000:
                print(f"✅ Captura exitosa desde {url}: {len(response.content)} bytes")
                return response.content
            else:
                print(f"⚠️ Respuesta inválida desde {url}: {response.status_code}, {len(response.content)} bytes")
        except Exception as e:
            print(f"❌ Error con {url}: {e}")
            continue
    
    return None


def enviar_a_telegram(image_bytes, caption):
    """Envía imagen a Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        
        files = {
            'photo': ('esp32cam.jpg', BytesIO(image_bytes), 'image/jpeg')
        }
        data = {
            'chat_id': CHAT_ID,
            'caption': caption
        }
        
        response = requests.post(url, files=files, data=data, timeout=15)
        response.raise_for_status()
        
        print("✅ Imagen enviada a Telegram")
        return True
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")
        return False


# ========== ENDPOINTS ==========

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'ESP32-CAM Control Endpoint',
        'camera_url': f"http://{config['camera_ip']}:{config['port']}{config['stream_path']}",
        'last_update': config['last_update'],
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


# ✅ NUEVO: Endpoint para capturar y enviar a Telegram
@app.route('/capture-and-send', methods=['POST'])
def capture_and_send():
    """
    Captura imagen de la ESP32-CAM y la envía a Telegram
    """
    try:
        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if not validar_api_key(api_key):
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        print("🔄 Iniciando captura...")
        
        # 1. Capturar imagen de la ESP32-CAM
        image_bytes = capturar_imagen_esp32cam()
        
        if image_bytes is None:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo capturar imagen de la ESP32-CAM. Verifica que esté encendida y accesible.'
            }), 500
        
        # 2. Preparar caption
        from datetime import datetime
        caption = (
            f"📸 Captura desde ESP32-CAM\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📡 IP: {config['camera_ip']}\n"
            f"📏 Tamaño: {len(image_bytes) / 1024:.1f} KB"
        )
        
        # 3. Enviar a Telegram
        if enviar_a_telegram(image_bytes, caption):
            return jsonify({
                'status': 'success',
                'message': 'Imagen capturada y enviada a Telegram',
                'image_size_kb': round(len(image_bytes) / 1024, 1),
                'camera_ip': config['camera_ip']
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Imagen capturada pero error al enviar a Telegram'
            }), 500
    
    except Exception as e:
        print(f"❌ Error en capture_and_send: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# Actualizar IP desde Flutter
@app.route('/update-camera-ip', methods=['POST'])
def update_camera_ip():
    try:
        api_key = request.headers.get('X-API-Key')
        if not validar_api_key(api_key):
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        
        if not data or 'camera_ip' not in data:
            return jsonify({'status': 'error', 'message': 'Falta camera_ip'}), 400
        
        config['camera_ip'] = data['camera_ip']
        config['port'] = data.get('port', '81')
        config['stream_path'] = data.get('stream_path', '/stream')
        
        import datetime
        config['last_update'] = datetime.datetime.now().isoformat()
        
        guardar_configuracion()
        
        return jsonify({
            'status': 'success',
            'message': 'IP actualizada correctamente',
            'camera_url': f"http://{config['camera_ip']}:{config['port']}{config['stream_path']}"
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Obtener configuración actual
@app.route('/get-camera-config', methods=['GET'])
def get_camera_config():
    api_key = request.headers.get('X-API-Key')
    if not validar_api_key(api_key):
        return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
    
    return jsonify({
        'status': 'success',
        'camera_ip': config['camera_ip'],
        'port': config['port'],
        'stream_path': config['stream_path'],
        'camera_url': f"http://{config['camera_ip']}:{config['port']}{config['stream_path']}",
        'last_update': config['last_update']
    })


if __name__ == '__main__':
    cargar_configuracion()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
