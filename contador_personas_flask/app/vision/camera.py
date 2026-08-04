from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Any

import cv2


logger = logging.getLogger("visioflow.camera")


class CameraProvider:
    """Abstraccion de captura. Un proveedor RGB no promete profundidad."""

    sensor_capabilities: tuple[str, ...] = ("color",)

    def read(self):
        raise NotImplementedError

    def isOpened(self) -> bool:  # noqa: N802 - compatibilidad OpenCV
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {
            "opened": self.isOpened(),
            "capabilities": list(self.sensor_capabilities),
        }


class OpenCVCameraProvider(CameraProvider):
    """Proveedor asincrono RGB para indices locales, archivos o streams."""

    def __init__(self, src=None) -> None:
        if src is None:
            src = os.environ.get(
                "CAMERA_SOURCE", "http://host.docker.internal:5001/video"
            )
            if str(src).isdigit():
                src = int(src)
        self.source = src
        self.cap = self._open_capture()
        self.last_frame_at = 0.0
        self.last_frame_change_at = 0.0
        self.reconnect_count = 0
        self._last_signature = None
        self._latest_frame = None
        self._latest_frame_lock = threading.Lock()
        if self.cap and self.cap.isOpened():
            logger.info("Conectado al stream/camara en %s", src)
        else:
            logger.error("No se pudo conectar al stream/camara en %s", src)
            if self.cap:
                self.cap.release()
            self.cap = None
        self.q: queue.Queue = queue.Queue(maxsize=2)
        self.stopped = False
        self.t = threading.Thread(target=self._reader, daemon=True)
        self.t.start()

    def _open_capture(self):
        cap = cv2.VideoCapture(self.source)
        if cap and cap.isOpened():
            # Mantener poca cola evita mostrar cuadros viejos cuando YOLO tarda.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _reconnect(self, reason: str) -> None:
        logger.warning("Reabriendo camara %s: %s", self.source, reason)
        if self.cap:
            self.cap.release()
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        time.sleep(0.25)
        self.cap = self._open_capture()
        self.reconnect_count += 1
        self._last_signature = None
        self.last_frame_change_at = time.monotonic()

    def _reader(self) -> None:
        failures = 0
        next_reconnect_at = 0.0
        while not self.stopped:
            if self.cap is None or not self.cap.isOpened():
                now = time.monotonic()
                if now >= next_reconnect_at:
                    self._reconnect("fuente no disponible durante el arranque")
                    next_reconnect_at = now + 2.0
                time.sleep(0.25)
                continue
            ok, frame = self.cap.read()
            if not ok:
                failures += 1
                if failures > 30:
                    self._reconnect("30 lecturas consecutivas fallaron")
                    failures = 0
                continue
            failures = 0
            now = time.monotonic()
            self.last_frame_at = now
            signature = cv2.resize(
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (32, 18)
            )
            if self._last_signature is None:
                self.last_frame_change_at = now
            else:
                change = float(cv2.mean(cv2.absdiff(signature, self._last_signature))[0])
                if change >= 0.08:
                    self.last_frame_change_at = now
                elif now - self.last_frame_change_at > 4.0:
                    self._reconnect("la fuente repitio el mismo cuadro por 4 segundos")
                    continue
            self._last_signature = signature
            with self._latest_frame_lock:
                self._latest_frame = frame
            if not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
            self.q.put(frame)

    def read(self):
        try:
            return True, self.q.get(timeout=0.5)
        except queue.Empty:
            return False, None

    def latest_frame(self):
        with self._latest_frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def isOpened(self) -> bool:  # noqa: N802
        return self.cap is not None and self.cap.isOpened()

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            **super().status(),
            "source": str(self.source),
            "lastFrameAgeSeconds": (
                round(now - self.last_frame_at, 2) if self.last_frame_at else None
            ),
            "lastFrameChangeAgeSeconds": (
                round(now - self.last_frame_change_at, 2)
                if self.last_frame_change_at
                else None
            ),
            "reconnectCount": self.reconnect_count,
        }

    def release(self) -> None:
        self.stopped = True
        if self.t.is_alive():
            self.t.join(timeout=1.0)
        if self.cap:
            self.cap.release()
