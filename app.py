# app.py - API de control en Render
from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

# Configuración
API_KEY = "SolarPanelPro_Despiadado"
CONFIG_FILE = "camera_config.json"

# Estado global
config = {
    'camera_ip': '192.168.1.78',
    'port': '81',
    'stream_path': '/stream',
    'last_update': None,
    'colab_status': 'unknown'
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


# ========== ENDPOINTS ==========

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'ESP32-CAM Control Endpoint',
        'camera_url': f"http://{config['camera_ip']}:{config['port']}{config['stream_path']}",
        'last_update': config['last_update'],
        'colab_status': config['colab_status']
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


# Actualizar IP desde Flutter
@app.route('/update-camera-ip', methods=['POST'])
def update_camera_ip():
    try:
        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if not validar_api_key(api_key):
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        
        if not data or 'camera_ip' not in data:
            return jsonify({'status': 'error', 'message': 'Falta camera_ip'}), 400
        
        # Actualizar configuración
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


# Obtener configuración actual (para Colab)
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


# Actualizar estado de Colab
@app.route('/update-colab-status', methods=['POST'])
def update_colab_status():
    api_key = request.headers.get('X-API-Key')
    if not validar_api_key(api_key):
        return jsonify({'status': 'error'}), 401
    
    data = request.get_json()
    config['colab_status'] = data.get('status', 'unknown')
    
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    cargar_configuracion()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
