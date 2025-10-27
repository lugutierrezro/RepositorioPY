# app_cron.py
import cv2
import requests
from ultralytics import YOLO
from io import BytesIO
import time

BOT_TOKEN = "8387352187:AAHjaAerl7CYtabW37TEfzZKgitApSSPgSE"
CHAT_ID = "7138077762"
URL_STREAM = "http://192.168.1.78:81/stream"

model = YOLO("yolo11n.pt")

cap = cv2.VideoCapture(URL_STREAM)

for _ in range(10):  # Capturar 10 frames
    ret, frame = cap.read()
    if not ret:
        continue
    
    results = model(frame, verbose=False)
    
    for result in results:
        if len(result.boxes) > 0:  # Si hay detecciones
            # Dibujar y enviar
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            _, buffer = cv2.imencode('.jpg', frame)
            files = {'photo': BytesIO(buffer.tobytes())}
            data = {'chat_id': CHAT_ID}
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                         files=files, data=data)
            break
    
    time.sleep(1)

cap.release()
