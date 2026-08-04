from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .config import VisionConfig


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class JsonRepository:
    def __init__(self) -> None:
        self._lock = RLock()

    def _read(self, path: Path) -> dict[str, Any] | None:
        with self._lock:
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    def _write_versioned(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = self._read(path)
            result = deepcopy(payload)
            result["version"] = int((previous or {}).get("version", 0)) + 1
            result["createdAt"] = utc_now_iso()
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            return deepcopy(result)


class CalibrationRepository(JsonRepository):
    def __init__(self, config: VisionConfig) -> None:
        super().__init__()
        self.config = config
        self.directory = config.data_root / "calibration" / config.camera_id

    @property
    def intrinsics_path(self) -> Path:
        return self.directory / "intrinsics.json"

    @property
    def world_path(self) -> Path:
        return self.directory / "world.json"

    def load_intrinsics(self) -> dict[str, Any] | None:
        return self._read(self.intrinsics_path)

    def load_world(self) -> dict[str, Any] | None:
        return self._read(self.world_path)

    def save_intrinsics(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, "cameraId": self.config.camera_id}
        return self._write_versioned(self.intrinsics_path, payload)

    def save_world(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, "cameraId": self.config.camera_id}
        return self._write_versioned(self.world_path, payload)


class SceneRepository(JsonRepository):
    def __init__(self, config: VisionConfig) -> None:
        super().__init__()
        self.config = config
        self.path = config.data_root / "scenes" / config.camera_id / "scene.json"

    def empty_scene(self, calibration_version: int = 0) -> dict[str, Any]:
        return {
            "cameraId": self.config.camera_id,
            "coordinateSystem": {
                "name": "world_ground",
                "unit": "meter",
                "origin": "camera_floor_projection",
                "xAxis": "right",
                "yAxis": "forward",
                "zAxis": "up",
            },
            "calibrationVersion": calibration_version,
            "fieldOfViewPolygon": [],
            "objects": [],
            "operationalAreas": [],
            "fixedPointMatrix": [],
            "version": 0,
            "createdAt": None,
        }

    def load(self) -> dict[str, Any] | None:
        return self._read(self.path)

    def load_or_empty(self, calibration_version: int = 0) -> dict[str, Any]:
        return self.load() or self.empty_scene(calibration_version)

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(payload)
        result["cameraId"] = self.config.camera_id
        result.setdefault("coordinateSystem", self.empty_scene()["coordinateSystem"])
        result.setdefault("calibrationVersion", 0)
        result.setdefault("fieldOfViewPolygon", [])
        result.setdefault("objects", [])
        result.setdefault("operationalAreas", [])
        result.setdefault("fixedPointMatrix", [])
        return self._write_versioned(self.path, result)
