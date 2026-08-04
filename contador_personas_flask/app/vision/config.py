from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_SENSOR_MODES = {"rgbd", "stereo", "monocular"}
DEFAULT_OBJECT_TYPES = (
    "wall",
    "table",
    "shelf",
    "rack",
    "display",
    "checkout",
    "bench",
    "column",
    "other",
)


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class CharucoConfig:
    dictionary: str = "DICT_5X5_100"
    squares_x: int = 7
    squares_y: int = 5
    square_length_meters: float = 0.04
    marker_length_meters: float = 0.02
    minimum_captures: int = 5


@dataclass(frozen=True)
class VisionConfig:
    camera_id: str
    sensor_mode: str
    data_root: Path
    grid_resolution_meters: float = 0.10
    max_reprojection_error_px: float = 1.5
    max_world_validation_error_meters: float = 0.15
    min_depth_meters: float = 0.20
    max_depth_meters: float = 20.0
    scan_frame_count: int = 40
    scan_detection_rate: float = 0.65
    scan_position_tolerance_meters: float = 0.20
    scan_dimension_tolerance_meters: float = 0.25
    scan_cluster_distance_meters: float = 0.50
    scene_model_path: str | None = None
    scene_class_map: dict[str, str] = field(default_factory=dict)
    object_types: tuple[str, ...] = DEFAULT_OBJECT_TYPES
    calibration_invalidated: bool = False
    charuco: CharucoConfig = field(default_factory=CharucoConfig)

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "VisionConfig":
        project_root = project_root or Path(__file__).resolve().parents[2]
        mode = os.getenv("SENSOR_MODE", "monocular").strip().lower()
        if mode not in SUPPORTED_SENSOR_MODES:
            raise ValueError(
                f"SENSOR_MODE debe ser uno de {sorted(SUPPORTED_SENSOR_MODES)}; recibido: {mode!r}"
            )

        raw_map = os.getenv("SCENE_CLASS_MAP", "{}")
        try:
            class_map = json.loads(raw_map)
        except json.JSONDecodeError as exc:
            raise ValueError("SCENE_CLASS_MAP debe ser un objeto JSON valido") from exc
        if not isinstance(class_map, dict):
            raise ValueError("SCENE_CLASS_MAP debe ser un objeto JSON")

        data_root = Path(os.getenv("VISIOFLOW_DATA_DIR", str(project_root / "data")))
        frame_count = max(30, min(100, _int("SCAN_FRAME_COUNT", 40)))
        return cls(
            camera_id=os.getenv("CAMERA_ID", "cam-01").strip() or "cam-01",
            sensor_mode=mode,
            data_root=data_root,
            grid_resolution_meters=_float("SCENE_GRID_RESOLUTION_METERS", 0.10),
            max_reprojection_error_px=_float("MAX_REPROJECTION_ERROR_PX", 1.5),
            max_world_validation_error_meters=_float(
                "MAX_WORLD_VALIDATION_ERROR_METERS", 0.15
            ),
            min_depth_meters=_float("MIN_DEPTH_METERS", 0.20),
            max_depth_meters=_float("MAX_DEPTH_METERS", 20.0),
            scan_frame_count=frame_count,
            scan_detection_rate=_float("SCAN_MIN_DETECTION_RATE", 0.65),
            scan_position_tolerance_meters=_float(
                "SCAN_POSITION_TOLERANCE_METERS", 0.20
            ),
            scan_dimension_tolerance_meters=_float(
                "SCAN_DIMENSION_TOLERANCE_METERS", 0.25
            ),
            scan_cluster_distance_meters=_float(
                "SCAN_CLUSTER_DISTANCE_METERS", 0.50
            ),
            scene_model_path=os.getenv("SCENE_MODEL_PATH") or None,
            scene_class_map={str(k): str(v) for k, v in class_map.items()},
            calibration_invalidated=os.getenv("CALIBRATION_INVALIDATED", "0") == "1",
            charuco=CharucoConfig(
                dictionary=os.getenv("CHARUCO_DICTIONARY", "DICT_5X5_100"),
                squares_x=_int("CHARUCO_SQUARES_X", 7),
                squares_y=_int("CHARUCO_SQUARES_Y", 5),
                square_length_meters=_float("CHARUCO_SQUARE_LENGTH_METERS", 0.04),
                marker_length_meters=_float("CHARUCO_MARKER_LENGTH_METERS", 0.02),
                minimum_captures=max(3, _int("CHARUCO_MIN_CAPTURES", 5)),
            ),
        )

    def public_dict(self) -> dict:
        return {
            "cameraId": self.camera_id,
            "sensorMode": self.sensor_mode,
            "gridResolutionMeters": self.grid_resolution_meters,
            "objectTypes": list(self.object_types),
            "calibrationInvalidated": self.calibration_invalidated,
            "charuco": {
                "dictionary": self.charuco.dictionary,
                "squaresX": self.charuco.squares_x,
                "squaresY": self.charuco.squares_y,
                "squareLengthMeters": self.charuco.square_length_meters,
                "markerLengthMeters": self.charuco.marker_length_meters,
                "minimumCaptures": self.charuco.minimum_captures,
            },
        }
