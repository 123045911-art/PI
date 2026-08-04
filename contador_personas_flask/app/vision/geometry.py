from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import cv2
import numpy as np

from .config import VisionConfig
from .repositories import CalibrationRepository


IMAGE_COORDINATE_SYSTEM = {
    "name": "image",
    "unit": "pixel",
    "uAxis": "right",
    "vAxis": "down",
}
CAMERA_COORDINATE_SYSTEM = {
    "name": "camera",
    "unit": "meter",
    "xAxis": "right",
    "yAxis": "down",
    "zAxis": "forward",
}
WORLD_COORDINATE_SYSTEM = {
    "name": "world_ground",
    "unit": "meter",
    "origin": "camera_floor_projection",
    "xAxis": "right",
    "yAxis": "forward",
    "zAxis": "up",
}


def _matrix(value: Any, shape: tuple[int, int], name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{name} debe tener forma {shape} y valores finitos")
    return result


def point_in_polygon(point: tuple[float, float], polygon: Iterable[Iterable[float]]) -> bool:
    vertices = np.asarray(list(polygon), dtype=np.float64)
    if vertices.ndim != 2 or vertices.shape[0] < 3 or vertices.shape[1] != 2:
        return False
    contour = vertices.astype(np.float32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0


def bbox_foot_point(bbox: Iterable[float]) -> tuple[float, float]:
    left, top, right, bottom = [float(value) for value in bbox]
    if right < left or bottom < top:
        raise ValueError("bbox debe usar el orden left, top, right, bottom")
    return (left + right) / 2.0, bottom


@dataclass(frozen=True)
class SpatialPoint:
    x: float
    y: float
    z: float
    depth_method: str
    approximate: bool
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "z": round(self.z, 6),
            "coordinateSystem": WORLD_COORDINATE_SYSTEM,
            "depthMethod": self.depth_method,
            "approximate": self.approximate,
            "confidence": round(self.confidence, 4),
        }


class CoordinateTransformer:
    """Transformaciones geometricas; nunca estima profundidad por su cuenta."""

    def __init__(self, config: VisionConfig, repository: CalibrationRepository) -> None:
        self.config = config
        self.repository = repository

    @staticmethod
    def deproject_rgbd(
        u: float, v: float, depth_meters: float, camera_matrix: Any
    ) -> np.ndarray:
        if not np.isfinite(depth_meters) or depth_meters <= 0:
            raise ValueError("La profundidad debe ser positiva y finita")
        k = _matrix(camera_matrix, (3, 3), "cameraMatrix")
        fx, fy = k[0, 0], k[1, 1]
        cx, cy = k[0, 2], k[1, 2]
        if fx <= 0 or fy <= 0:
            raise ValueError("fx y fy deben ser positivos")
        return np.array(
            [
                (float(u) - cx) * depth_meters / fx,
                (float(v) - cy) * depth_meters / fy,
                depth_meters,
            ],
            dtype=np.float64,
        )

    @staticmethod
    def camera_to_world(
        point_camera: Any, rotation_camera_to_world: Any, translation_meters: Any
    ) -> np.ndarray:
        point = np.asarray(point_camera, dtype=np.float64).reshape(3)
        rotation = _matrix(rotation_camera_to_world, (3, 3), "rotationMatrix")
        translation = np.asarray(translation_meters, dtype=np.float64).reshape(3)
        if not np.isfinite(point).all() or not np.isfinite(translation).all():
            raise ValueError("Los puntos y la traslacion deben ser finitos")
        return rotation @ point + translation

    @staticmethod
    def image_to_ground(u: float, v: float, homography: Any) -> np.ndarray:
        h = _matrix(homography, (3, 3), "imageToGroundHomography")
        projected = h @ np.array([float(u), float(v), 1.0], dtype=np.float64)
        if abs(projected[2]) < 1e-12:
            raise ValueError("El punto no tiene una proyeccion valida sobre el suelo")
        return np.array(
            [projected[0] / projected[2], projected[1] / projected[2], 0.0],
            dtype=np.float64,
        )

    @staticmethod
    def ground_to_image(x: float, y: float, homography: Any) -> np.ndarray:
        h = _matrix(homography, (3, 3), "groundToImageHomography")
        projected = h @ np.array([float(x), float(y), 1.0], dtype=np.float64)
        if abs(projected[2]) < 1e-12:
            raise ValueError("El punto del mundo no se proyecta en la imagen")
        return np.array([projected[0] / projected[2], projected[1] / projected[2]])

    def image_ground_point(self, u: float, v: float) -> SpatialPoint:
        world = self.repository.load_world()
        if not world:
            raise ValueError("No existe calibracion del mundo")
        point = self.image_to_ground(u, v, world["imageToGroundHomography"])
        return SpatialPoint(
            x=float(point[0]),
            y=float(point[1]),
            z=0.0,
            depth_method="ground_plane",
            approximate=True,
            confidence=max(0.0, 1.0 - float(world.get("validationErrorMeters", 0.0))),
        )

    def metric_point_from_depth(
        self, u: float, v: float, depth_meters: float, confidence: float = 1.0
    ) -> SpatialPoint:
        intrinsics = self.repository.load_intrinsics()
        world = self.repository.load_world()
        if not intrinsics or not world:
            raise ValueError("Se requieren calibraciones intrinseca y del mundo")
        point_camera = self.deproject_rgbd(
            u, v, depth_meters, intrinsics["cameraMatrix"]
        )
        point_world = self.camera_to_world(
            point_camera,
            world["rotationMatrix"],
            world["translationVectorMeters"],
        )
        return SpatialPoint(
            x=float(point_world[0]),
            y=float(point_world[1]),
            z=float(point_world[2]),
            depth_method=self.config.sensor_mode,
            approximate=False,
            confidence=float(np.clip(confidence, 0.0, 1.0)),
        )

    def field_of_view_polygon(self, image_width: int, image_height: int) -> list[list[float]]:
        world = self.repository.load_world()
        if not world:
            return []
        corners = [
            (0, image_height - 1),
            (image_width - 1, image_height - 1),
            (image_width - 1, 0),
            (0, 0),
        ]
        result: list[list[float]] = []
        for u, v in corners:
            point = self.image_to_ground(u, v, world["imageToGroundHomography"])
            if np.isfinite(point).all():
                result.append([round(float(point[0]), 6), round(float(point[1]), 6)])
        return result
