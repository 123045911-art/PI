"""
detect_camera.py — Autodetección de índice de cámara funcional.

Prueba los índices 0, 1, 2 y 3 con OpenCV. Imprime al stdout el primer
índice que entrega imagen y sale con exit code 0. Si ninguno funciona,
sale con exit code 1.

Uso:
    python detect_camera.py
    CAMERA_INDEX=$(python detect_camera.py)
"""
import sys
import cv2


def probe_camera(index: int) -> bool:
    """Intenta abrir una cámara y leer un frame. Libera inmediatamente."""
    print(f"  Probando índice {index}...", end=" ", flush=True)
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print("no se pudo abrir.")
        cap.release()
        return False
    ok, frame = cap.read()
    if not ok or frame is None:
        print("abierta pero sin imagen.")
        cap.release()
        return False
    h, w = frame.shape[:2]
    print(f"OK — resolución {w}x{h}")
    cap.release()
    return True


def main() -> None:
    print("[detect_camera] Buscando cámara funcional (índices 0-3)...")
    for index in range(4):
        if probe_camera(index):
            print(f"[detect_camera] Cámara funcional encontrada: índice {index}")
            # Imprimir SOLO el índice al stdout para captura en scripts
            print(index)
            sys.exit(0)
    print("[detect_camera] ERROR: Ninguna cámara respondió en los índices 0-3.")
    sys.exit(1)


if __name__ == "__main__":
    main()
