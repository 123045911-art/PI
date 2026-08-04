from __future__ import annotations

import math
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np

from .config import VisionConfig
from .depth import DepthProvider
from .geometry import CoordinateTransformer, point_in_polygon
from .repositories import CalibrationRepository, SceneRepository, utc_now_iso


class ObjectSegmentationProvider:
    name = "manual_only"

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        return []

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "available": False,
            "warning": (
                "No hay modelo de segmentacion de escena configurado; use la "
                "herramienta manual."
            ),
        }


class UltralyticsSegmentationProvider(ObjectSegmentationProvider):
    name = "ultralytics_segmentation"

    def __init__(self, model_path: str, config: VisionConfig) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path, task="segment")
        self.config = config

    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "available": True, "warning": None}

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        results = self.model.predict(source=frame, verbose=False)
        if not results:
            return []
        result = results[0]
        if result.boxes is None or result.masks is None:
            return []
        detections: list[dict[str, Any]] = []
        for index, box in enumerate(result.boxes):
            source_name = str(result.names[int(box.cls[0].item())])
            object_type = self.config.scene_class_map.get(source_name, source_name)
            if object_type not in self.config.object_types:
                continue
            polygon = result.masks.xy[index]
            if polygon is None or len(polygon) < 3:
                continue
            detections.append(
                {
                    "objectType": object_type,
                    "confidence": float(box.conf[0].item()),
                    "imagePolygon": np.asarray(polygon, dtype=float).tolist(),
                    # El contacto debe confirmarlo el modelo personalizado o el usuario.
                    "groundContactConfirmed": False,
                }
            )
        return detections


def create_segmentation_provider(config: VisionConfig) -> ObjectSegmentationProvider:
    if not config.scene_model_path:
        return ObjectSegmentationProvider()
    return UltralyticsSegmentationProvider(config.scene_model_path, config)


class ObjectSpatialProjector:
    def __init__(
        self,
        config: VisionConfig,
        transformer: CoordinateTransformer,
        depth_provider: DepthProvider,
    ) -> None:
        self.config = config
        self.transformer = transformer
        self.depth_provider = depth_provider

    def project(self, detection: dict[str, Any]) -> dict[str, Any] | None:
        object_type = detection.get("objectType")
        confidence = float(detection.get("confidence", 0.0))
        if object_type not in self.config.object_types:
            return None
        if self.config.sensor_mode == "monocular":
            contacts = detection.get("groundContactPoints")
            if not detection.get("groundContactConfirmed") or not contacts or len(contacts) < 3:
                return None
            footprint = []
            for point in contacts:
                projected = self.transformer.image_ground_point(point[0], point[1])
                footprint.append([projected.x, projected.y])
            return self._observation(
                object_type,
                footprint,
                confidence,
                height=detection.get("heightMeters"),
                depth_method="ground_plane",
                approximate=True,
            )

        pixels = detection.get("maskPixels")
        if not pixels:
            polygon = detection.get("imagePolygon") or []
            if len(polygon) >= 3:
                contour = np.asarray(polygon, dtype=np.int32)
                min_x, min_y = contour.min(axis=0)
                max_x, max_y = contour.max(axis=0)
                mask = np.zeros((max_y - min_y + 1, max_x - min_x + 1), np.uint8)
                cv2.fillPoly(mask, [(contour - [min_x, min_y])], 255)
                ys, xs = np.where(mask > 0)
                pixels = np.column_stack([xs + min_x, ys + min_y]).tolist()
        if not pixels:
            return None
        step = max(1, int(math.ceil(len(pixels) / 1500)))
        world_points: list[np.ndarray] = []
        confidences: list[float] = []
        for u, v in pixels[::step]:
            sample = self.depth_provider.sample(float(u), float(v))
            if not sample:
                continue
            point = self.transformer.metric_point_from_depth(
                float(u), float(v), sample.meters, sample.confidence
            )
            world_points.append(np.array([point.x, point.y, point.z]))
            confidences.append(sample.confidence)
        if len(world_points) < 10:
            return None
        points = np.asarray(world_points)
        median = np.median(points, axis=0)
        distances = np.linalg.norm(points - median, axis=1)
        mad = np.median(np.abs(distances - np.median(distances)))
        keep = distances <= np.median(distances) + max(0.05, 3.0 * mad)
        points = points[keep]
        if len(points) < 6:
            return None
        hull = cv2.convexHull(points[:, :2].astype(np.float32)).reshape((-1, 2))
        height = float(max(0.0, points[:, 2].max() - points[:, 2].min()))
        valid_ratio = len(world_points) / max(1, len(pixels[::step]))
        return self._observation(
            object_type,
            hull.tolist(),
            confidence * valid_ratio * float(np.mean(confidences)),
            height=height,
            depth_method=self.config.sensor_mode,
            approximate=False,
        )

    @staticmethod
    def _observation(
        object_type: str,
        footprint: list[list[float]],
        confidence: float,
        height: float | None,
        depth_method: str,
        approximate: bool,
    ) -> dict[str, Any]:
        points = np.asarray(footprint, dtype=float)
        center = points.mean(axis=0)
        width = float(points[:, 0].max() - points[:, 0].min())
        depth = float(points[:, 1].max() - points[:, 1].min())
        return {
            "objectType": object_type,
            "footprint": points.tolist(),
            "center": [float(center[0]), float(center[1]), 0.0],
            "widthMeters": width,
            "depthMeters": depth,
            "heightMeters": float(height) if height is not None else None,
            "depthMethod": depth_method,
            "approximate": approximate,
            "confidence": float(np.clip(confidence, 0.0, 1.0)),
        }


@dataclass
class _Cluster:
    observations: list[dict[str, Any]]


class SceneAggregator:
    def __init__(self, config: VisionConfig) -> None:
        self.config = config

    def aggregate(
        self, observations: list[dict[str, Any]], total_frames: int
    ) -> list[dict[str, Any]]:
        clusters: list[_Cluster] = []
        for observation in observations:
            center = np.asarray(observation["center"][:2], dtype=float)
            selected = None
            selected_distance = float("inf")
            for cluster in clusters:
                if cluster.observations[0]["objectType"] != observation["objectType"]:
                    continue
                mean = np.mean([item["center"][:2] for item in cluster.observations], axis=0)
                distance = float(np.linalg.norm(center - mean))
                if distance < self.config.scan_cluster_distance_meters and distance < selected_distance:
                    selected, selected_distance = cluster, distance
            if selected is None:
                clusters.append(_Cluster([observation]))
            else:
                selected.observations.append(observation)

        accepted: list[dict[str, Any]] = []
        for index, cluster in enumerate(clusters, start=1):
            items = cluster.observations
            frames_observed = len({item.get("frameIndex", id(item)) for item in items})
            detection_rate = frames_observed / max(1, total_frames)
            centers = np.asarray([item["center"][:2] for item in items], dtype=float)
            dimensions = np.asarray(
                [[item["widthMeters"], item["depthMeters"]] for item in items],
                dtype=float,
            )
            position_std = float(np.linalg.norm(np.std(centers, axis=0)))
            dimension_std = float(np.linalg.norm(np.std(dimensions, axis=0)))
            if detection_rate < self.config.scan_detection_rate:
                continue
            if position_std > self.config.scan_position_tolerance_meters:
                continue
            if dimension_std > self.config.scan_dimension_tolerance_meters:
                continue
            representative = deepcopy(items[len(items) // 2])
            object_type = representative["objectType"]
            confidence = float(np.median([item["confidence"] for item in items]))
            representative.update(
                {
                    "id": f"obj-{object_type}-{index:02d}",
                    "name": f"{object_type.title()} {index:02d}",
                    "type": object_type,
                    "confidence": round(confidence * detection_rate, 4),
                    "framesObserved": frames_observed,
                    "detectionRate": round(detection_rate, 4),
                    "positionStdMeters": round(position_std, 6),
                    "dimensionStdMeters": round(dimension_std, 6),
                }
            )
            representative.pop("objectType", None)
            representative.pop("frameIndex", None)
            accepted.append(representative)
        return accepted


def normalize_scene_object(payload: dict[str, Any], config: VisionConfig) -> dict[str, Any]:
    result = deepcopy(payload)
    object_type = str(result.get("type", "other"))
    if object_type not in config.object_types:
        raise ValueError(f"Tipo de objeto no permitido: {object_type}")
    footprint = np.asarray(result.get("footprint", []), dtype=float)
    if footprint.ndim != 2 or footprint.shape[0] < 3 or footprint.shape[1] != 2:
        raise ValueError("footprint debe contener al menos tres puntos [x,y]")
    if not np.isfinite(footprint).all():
        raise ValueError("footprint contiene coordenadas no finitas")
    center = footprint.mean(axis=0)
    result["id"] = str(result.get("id") or f"obj-{object_type}-{uuid.uuid4().hex[:8]}")
    result["name"] = str(result.get("name") or object_type.title())
    result["type"] = object_type
    result["footprint"] = np.round(footprint, 6).tolist()
    result["center"] = {"x": float(center[0]), "y": float(center[1]), "z": 0.0}
    result["widthMeters"] = float(
        result.get("widthMeters", footprint[:, 0].max() - footprint[:, 0].min())
    )
    result["depthMeters"] = float(
        result.get("depthMeters", footprint[:, 1].max() - footprint[:, 1].min())
    )
    height = result.get("heightMeters")
    result["heightMeters"] = None if height in (None, "") else float(height)
    result["depthMethod"] = str(
        result.get("depthMethod", "ground_plane" if config.sensor_mode == "monocular" else config.sensor_mode)
    )
    if result["depthMethod"] not in {"rgbd", "stereo", "ground_plane", "manual"}:
        raise ValueError("depthMethod no es valido")
    result["approximate"] = bool(
        result.get("approximate", result["depthMethod"] == "ground_plane")
    )
    result["confidence"] = float(np.clip(float(result.get("confidence", 1.0)), 0, 1))
    return result


def generate_fixed_point_matrix(
    scene: dict[str, Any], resolution_meters: float
) -> list[dict[str, Any]]:
    if resolution_meters <= 0:
        raise ValueError("La resolucion de la matriz debe ser positiva")
    fov = scene.get("fieldOfViewPolygon") or []
    if len(fov) < 3:
        return []
    polygon = np.asarray(fov, dtype=float)
    min_x, min_y = polygon.min(axis=0)
    max_x, max_y = polygon.max(axis=0)
    objects = scene.get("objects") or []
    points: list[dict[str, Any]] = []
    x_values = np.arange(min_x, max_x + resolution_meters * 0.5, resolution_meters)
    y_values = np.arange(min_y, max_y + resolution_meters * 0.5, resolution_meters)
    if len(x_values) * len(y_values) > 100_000:
        raise ValueError(
            "La matriz excederia 100000 puntos; limite el campo de vision o aumente la resolucion."
        )
    for x in x_values:
        for y in y_values:
            if not point_in_polygon((float(x), float(y)), fov):
                continue
            occupant = next(
                (
                    item
                    for item in objects
                    if point_in_polygon((float(x), float(y)), item.get("footprint", []))
                ),
                None,
            )
            points.append(
                {
                    "x": round(float(x), 6),
                    "y": round(float(y), 6),
                    "z": 0.0,
                    "coordinateSystem": "world_ground",
                    "occupied": occupant is not None,
                    "objectId": occupant.get("id") if occupant else None,
                    "objectType": occupant.get("type") if occupant else None,
                    "confidence": float(occupant.get("confidence", 1.0)) if occupant else 1.0,
                }
            )
    return points


class SceneScanner:
    def __init__(
        self,
        config: VisionConfig,
        calibration_repository: CalibrationRepository,
        scene_repository: SceneRepository,
        transformer: CoordinateTransformer,
        depth_provider: DepthProvider,
        segmentation_provider: ObjectSegmentationProvider,
        frame_provider: Callable[[], np.ndarray | None],
    ) -> None:
        self.config = config
        self.calibration_repository = calibration_repository
        self.scene_repository = scene_repository
        self.transformer = transformer
        self.depth_provider = depth_provider
        self.segmentation_provider = segmentation_provider
        self.frame_provider = frame_provider
        self.projector = ObjectSpatialProjector(config, transformer, depth_provider)
        self.aggregator = SceneAggregator(config)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "state": "idle",
            "coordinateSystem": "world_ground_meters",
            "framesTarget": config.scan_frame_count,
            "framesCaptured": 0,
            "proposals": [],
            "warnings": [],
        }

    def _preflight(self) -> tuple[int, int]:
        if self.config.calibration_invalidated:
            raise ValueError(
                "La calibracion fue invalidada por movimiento o cambio de optica"
            )
        intrinsics = self.calibration_repository.load_intrinsics()
        world = self.calibration_repository.load_world()
        if not intrinsics:
            raise ValueError("El escaneo requiere calibracion intrinseca")
        if not world:
            raise ValueError("El escaneo requiere calibracion del mundo")
        if float(intrinsics.get("reprojectionErrorPx", 999)) > self.config.max_reprojection_error_px:
            raise ValueError("El error de calibracion intrinseca excede el limite")
        if float(world.get("validationErrorMeters", 999)) > self.config.max_world_validation_error_meters:
            raise ValueError("El error de calibracion del mundo excede el limite")
        if self.config.sensor_mode in {"rgbd", "stereo"} and not self.depth_provider.status()["available"]:
            raise ValueError(
                f"SENSOR_MODE={self.config.sensor_mode} no entrega profundidad valida"
            )
        return int(intrinsics["imageWidth"]), int(intrinsics["imageHeight"])

    def start(self) -> dict[str, Any]:
        expected_resolution = self._preflight()
        frame = self.frame_provider()
        if frame is None:
            raise ValueError("La camara no tiene un frame disponible")
        actual_resolution = (int(frame.shape[1]), int(frame.shape[0]))
        if actual_resolution != expected_resolution:
            raise ValueError(
                f"La resolucion actual {actual_resolution} no coincide con {expected_resolution}"
            )
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("Ya existe un escaneo en curso")
            self._stop.clear()
            self._status = {
                "state": "running",
                "coordinateSystem": "world_ground_meters",
                "startedAt": utc_now_iso(),
                "framesTarget": self.config.scan_frame_count,
                "framesCaptured": 0,
                "detectionsObserved": 0,
                "proposals": [],
                "warnings": [],
                "segmentation": self.segmentation_provider.status(),
                "depth": self.depth_provider.status(),
            }
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return deepcopy(self._status)

    def _run(self) -> None:
        observations: list[dict[str, Any]] = []
        warnings: list[str] = []
        try:
            for frame_index in range(self.config.scan_frame_count):
                if self._stop.is_set():
                    break
                frame = self.frame_provider()
                if frame is None:
                    time.sleep(0.05)
                    continue
                detections = self.segmentation_provider.detect(frame)
                for detection in detections:
                    if detection.get("objectType") == "person":
                        continue
                    observation = self.projector.project(detection)
                    if observation is None:
                        continue
                    observation["frameIndex"] = frame_index
                    observations.append(observation)
                with self._lock:
                    self._status["framesCaptured"] = frame_index + 1
                    self._status["detectionsObserved"] = len(observations)
                time.sleep(0.04)
            proposals = self.aggregator.aggregate(
                observations, max(1, self._status["framesCaptured"])
            )
            if not self.segmentation_provider.status()["available"]:
                warnings.append(
                    "No se generaron objetos automaticos: configure SCENE_MODEL_PATH o dibujelos manualmente."
                )
            elif not proposals:
                warnings.append(
                    "Ninguna deteccion cumplio estabilidad, profundidad y contacto con el suelo."
                )
            with self._lock:
                self._status.update(
                    {
                        "state": "stopped" if self._stop.is_set() else "completed",
                        "finishedAt": utc_now_iso(),
                        "proposals": proposals,
                        "warnings": warnings,
                    }
                )
        except Exception as exc:
            with self._lock:
                self._status.update(
                    {"state": "failed", "finishedAt": utc_now_iso(), "error": str(exc)}
                )

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            return deepcopy(self._status)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._status)
