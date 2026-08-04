import os
import time

import cv2
from flask import Flask, Response, jsonify

app = Flask(__name__)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def camera_candidates() -> list[int]:
    configured = os.getenv("CAMERA_INDEX", "").strip()
    if configured:
        return [int(value.strip()) for value in configured.split(",") if value.strip()]
    # La Dell suele ocupar el índice 1; una webcam única normalmente usa el 0.
    return [1, 0, 2, 3]


def open_camera():
    for camera_index in camera_candidates():
        print(f"[*] Probando cámara {camera_index}...", flush=True)
        candidate = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not candidate.isOpened():
            candidate.release()
            continue
        candidate.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        for _ in range(5):
            success, frame = candidate.read()
            if success and frame is not None:
                print(f"[OK] Cámara {camera_index} lista.", flush=True)
                return candidate, camera_index
            time.sleep(0.1)
        candidate.release()
    print("[ERROR] Ninguna cámara disponible. Cierra Cámara/Teams/Zoom y reintenta.", flush=True)
    return None, None


cap, selected_camera_index = open_camera()


def generate():
    global cap, selected_camera_index
    while True:
        if cap is None or not cap.isOpened():
            print("[REINTENTO] Intentando reconectar cámara...", flush=True)
            cap, selected_camera_index = open_camera()
            time.sleep(1)
            continue
        success, frame = cap.read()
        if not success or frame is None:
            cap.release()
            cap = None
            continue
        encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if encoded:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"


@app.route("/")
def index():
    status = "Activo" if cap and cap.isOpened() else "Error de cámara"
    camera = selected_camera_index if selected_camera_index is not None else "NA"
    return f"""
    <html><head><title>VISIOFLOW Camera Bridge</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:50px">
      <h1>VISIOFLOW Camera Bridge</h1><p>Estado: <strong>{status}</strong></p>
      <p>Cámara seleccionada: {camera}</p><a href="/video">Ver streaming</a>
    </body></html>
    """


@app.route("/video")
def video_feed():
    if not cap or not cap.isOpened():
        return "Cámara no disponible", 503
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/health")
def health():
    return jsonify(status="online", camera_open=bool(cap and cap.isOpened()), camera_index=selected_camera_index)


if __name__ == "__main__":
    try:
        print("[*] Servidor Flask iniciando en puerto 5001...", flush=True)
        app.run(host="0.0.0.0", port=5001, threaded=True, debug=False)
    finally:
        if cap:
            cap.release()
