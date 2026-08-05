from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

import numpy as np


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


class BrowserPushCameraProvider(CameraProvider):
    """Proveedor alimentado por frames que el navegador de un visitante sube
    via HTTP (ver POST /api/live/push-frame). No hay hilo lector ni stream de
    red que mantener: el ultimo frame recibido es la fuente de verdad, y
    "gana" siempre el dispositivo mas reciente en empujar una imagen.
    """

    STALE_AFTER_SECONDS = 8.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._last_push_at: float = 0.0

    def push_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._latest_frame = frame
            self._last_push_at = time.monotonic()

    def read(self):
        with self._lock:
            if not self._last_push_at:
                return False, None
            if time.monotonic() - self._last_push_at > self.STALE_AFTER_SECONDS:
                return False, None
            return True, self._latest_frame.copy()

    def latest_frame(self):
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def isOpened(self) -> bool:  # noqa: N802
        # Siempre True: TrackerService solo revisa esto una vez al arrancar
        # para decidir si el pipeline queda "initialized". La disponibilidad
        # real de imagen la reporta read() en cada tick (con recuperacion
        # automatica ya manejada por TrackerService.process_frame()).
        return True

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            last_push_at = self._last_push_at
        return {
            **super().status(),
            "source": "browser-push",
            "lastFrameAgeSeconds": (
                round(now - last_push_at, 2) if last_push_at else None
            ),
        }

    def release(self) -> None:
        with self._lock:
            self._latest_frame = None
            self._last_push_at = 0.0
