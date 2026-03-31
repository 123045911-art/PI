import cv2
import sys
import time
from flask import Flask, Response, jsonify

app = Flask(__name__)

# --- CONFIGURACIÓN ---
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Intentar abrir la cámara con DirectShow (CAP_DSHOW) para Windows
print(f"[*] Iniciando cámara {CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("[ERROR] No se pudo acceder a la cámara física.")
    # No salimos para que el servidor Flask al menos responda con el error
else:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    print(f"[OK] Cámara lista: {FRAME_WIDTH}x{FRAME_HEIGHT}")

def generate():
    """Generador de frames para MJPEG."""
    while True:
        if cap is None or not cap.isOpened():
            print("[REINTENTO] Intentando reconectar cámara...")
            time.sleep(1)
            continue

        success, frame = cap.read()
        if not success:
            print("[ERROR] Error al leer frame.")
            continue
        
        # Codificación JPG optimizada
        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

@app.route("/")
def index():
    status = "Activo" if cap and cap.isOpened() else "Error de Cámara"
    return f"""
    <html>
        <head><title>VISIOFLOW Camera Bridge</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #2c3e50;">VISIOFLOW Camera Bridge</h1>
            <p>Estado: <strong>{status}</strong></p>
            <div style="margin: 20px;">
                <a href="/video" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Ver Streaming</a>
            </div>
            <p style="color: #7f8c8d; font-size: 0.8em;">URL para Docker: http://host.docker.internal:5001/video</p>
        </body>
    </html>
    """

@app.route("/video")
def video_feed():
    if not cap or not cap.isOpened():
        return "Cámara no disponible", 503
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "camera_open": cap.isOpened() if cap else False
    })

if __name__ == "__main__":
    try:
        # Iniciamos Flask en 0.0.0.0
        print("[*] Servidor Flask iniciando en puerto 5001...")
        app.run(host="0.0.0.0", port=5001, threaded=True, debug=False)
    finally:
        if cap:
            print("[*] Liberando cámara...")
            cap.release()