from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

import cv2
import numpy as np

from .config import VisionConfig


@dataclass(frozen=True)
class DepthSample:
    meters: float
    confidence: float
    method: str


class DepthProvider:
    mode = "unknown"

    def sample(self, u: float, v: float) -> DepthSample | None:
        return None

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "available": False,
            "validPointPercentage": 0.0,
            "warning": "Proveedor de profundidad no configurado.",
        }


class MonocularDepthProvider(DepthProvider):
    mode = "monocular"

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "available": True,
            "metricDepthAvailable": False,
            "validPointPercentage": 0.0,
            "method": "ground_plane",
            "approximate": True,
            "warning": (
                "El modo monocular solo obtiene coordenadas metricas para puntos "
                "confirmados sobre el plano del suelo."
            ),
        }


class ArrayDepthProvider(DepthProvider):
    def __init__(self, config: VisionConfig, mode: str) -> None:
        self.config = config
        self.mode = mode
        self._depth: np.ndarray | None = None
        self._confidence: np.ndarray | None = None
        self._lock = RLock()

    def update_depth_map(
        self, depth_meters: np.ndarray, confidence: np.ndarray | None = None
    ) -> None:
        depth = np.asarray(depth_meters, dtype=np.float32)
        if depth.ndim != 2:
            raise ValueError("El mapa de profundidad debe tener dos dimensiones")
        if confidence is not None and np.asarray(confidence).shape != depth.shape:
            raise ValueError("El mapa de confianza debe coincidir con profundidad")
        with self._lock:
            self._depth = depth.copy()
            self._confidence = (
                np.asarray(confidence, dtype=np.float32).copy()
                if confidence is not None
                else None
            )

    def _valid(self, values: np.ndarray) -> np.ndarray:
        return np.isfinite(values) & (values >= self.config.min_depth_meters) & (
            values <= self.config.max_depth_meters
        )

    def sample(self, u: float, v: float) -> DepthSample | None:
        with self._lock:
            if self._depth is None:
                return None
            x, y = int(round(u)), int(round(v))
            height, width = self._depth.shape
            if not (0 <= x < width and 0 <= y < height):
                return None
            x1, x2 = max(0, x - 2), min(width, x + 3)
            y1, y2 = max(0, y - 2), min(height, y + 3)
            patch = self._depth[y1:y2, x1:x2]
            valid = self._valid(patch)
            if not valid.any():
                return None
            meters = float(np.median(patch[valid]))
            valid_ratio = float(valid.mean())
            if self._confidence is None:
                confidence = valid_ratio
            else:
                conf_patch = self._confidence[y1:y2, x1:x2]
                confidence = float(np.clip(np.median(conf_patch[valid]), 0.0, 1.0))
            return DepthSample(meters=meters, confidence=confidence, method=self.mode)

    def depth_map(self) -> np.ndarray | None:
        with self._lock:
            return self._depth.copy() if self._depth is not None else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._depth is None:
                return {
                    "mode": self.mode,
                    "available": False,
                    "validPointPercentage": 0.0,
                    "warning": "No se ha recibido un mapa de profundidad alineado.",
                }
            valid = self._valid(self._depth)
            percentage = round(float(valid.mean() * 100.0), 2)
            return {
                "mode": self.mode,
                "available": bool(valid.any()),
                "validPointPercentage": percentage,
                "method": self.mode,
                "approximate": False,
            }


class RGBDDepthProvider(ArrayDepthProvider):
    def __init__(self, config: VisionConfig) -> None:
        super().__init__(config, "rgbd")


class StereoDepthProvider(ArrayDepthProvider):
    def __init__(
        self,
        config: VisionConfig,
        focal_length_px: float | None,
        baseline_meters: float | None,
    ) -> None:
        super().__init__(config, "stereo")
        self.focal_length_px = focal_length_px
        self.baseline_meters = baseline_meters
        self.matcher = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=16 * 8,
            blockSize=5,
            P1=8 * 3 * 5 * 5,
            P2=32 * 3 * 5 * 5,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=2,
        )

    def update_stereo_pair(self, left: np.ndarray, right: np.ndarray) -> None:
        if not self.focal_length_px or not self.baseline_meters:
            raise ValueError("Estereo requiere focal_length_px y baseline_meters calibrados")
        if left.shape[:2] != right.shape[:2]:
            raise ValueError("Las imagenes estereo rectificadas deben tener la misma resolucion")
        left_gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if left.ndim == 3 else left
        right_gray = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if right.ndim == 3 else right
        disparity = self.matcher.compute(left_gray, right_gray).astype(np.float32) / 16.0
        valid = disparity > 0.5
        depth = np.full(disparity.shape, np.nan, dtype=np.float32)
        depth[valid] = (
            float(self.focal_length_px) * float(self.baseline_meters) / disparity[valid]
        )
        confidence = valid.astype(np.float32)
        self.update_depth_map(depth, confidence)

    def status(self) -> dict[str, Any]:
        if not self.focal_length_px or not self.baseline_meters:
            return {
                "mode": self.mode,
                "available": False,
                "validPointPercentage": 0.0,
                "warning": "Faltan STEREO_FOCAL_LENGTH_PX o STEREO_BASELINE_METERS.",
            }
        return super().status()


def create_depth_provider(config: VisionConfig) -> DepthProvider:
    if config.sensor_mode == "monocular":
        return MonocularDepthProvider()
    if config.sensor_mode == "rgbd":
        return RGBDDepthProvider(config)
    import os

    focal = os.getenv("STEREO_FOCAL_LENGTH_PX")
    baseline = os.getenv("STEREO_BASELINE_METERS")
    return StereoDepthProvider(
        config,
        float(focal) if focal else None,
        float(baseline) if baseline else None,
    )
