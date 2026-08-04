from __future__ import annotations

from threading import RLock
from typing import Any

import cv2
import numpy as np

from .config import VisionConfig
from .geometry import IMAGE_COORDINATE_SYSTEM, CoordinateTransformer
from .repositories import CalibrationRepository


class IntrinsicCalibrationService:
    """Asistente ChArUco en memoria; no conserva las imagenes capturadas."""

    def __init__(self, config: VisionConfig, repository: CalibrationRepository) -> None:
        self.config = config
        self.repository = repository
        self._samples: list[tuple[np.ndarray, np.ndarray]] = []
        self._image_size: tuple[int, int] | None = None
        self._lock = RLock()

    def _dictionary(self):
        name = self.config.charuco.dictionary
        dictionary_id = getattr(cv2.aruco, name, None)
        if dictionary_id is None:
            raise ValueError(f"Diccionario ArUco no soportado: {name}")
        return cv2.aruco.getPredefinedDictionary(dictionary_id)

    def board(self):
        cfg = self.config.charuco
        return cv2.aruco.CharucoBoard(
            (cfg.squares_x, cfg.squares_y),
            cfg.square_length_meters,
            cfg.marker_length_meters,
            self._dictionary(),
        )

    def capture(self, frame: np.ndarray) -> dict[str, Any]:
        if frame is None or frame.ndim not in (2, 3):
            raise ValueError("Se requiere un frame valido")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        image_size = (int(gray.shape[1]), int(gray.shape[0]))
        detector = cv2.aruco.CharucoDetector(self.board())
        charuco_corners, charuco_ids, marker_corners, marker_ids = detector.detectBoard(gray)
        corner_count = 0 if charuco_corners is None else int(len(charuco_corners))
        marker_count = 0 if marker_ids is None else int(len(marker_ids))
        if charuco_ids is None or charuco_corners is None or corner_count < 4:
            return {
                "accepted": False,
                "coordinateSystem": IMAGE_COORDINATE_SYSTEM,
                "cornerCount": corner_count,
                "markerCount": marker_count,
                "captureCount": len(self._samples),
                "warning": "No se detectaron al menos cuatro esquinas ChArUco.",
            }
        with self._lock:
            if self._image_size is not None and self._image_size != image_size:
                raise ValueError(
                    "La resolucion cambio durante la captura; reinicia la calibracion."
                )
            self._image_size = image_size
            self._samples.append(
                (
                    np.asarray(charuco_corners, dtype=np.float32).copy(),
                    np.asarray(charuco_ids, dtype=np.int32).copy(),
                )
            )
            count = len(self._samples)
        return {
            "accepted": True,
            "coordinateSystem": IMAGE_COORDINATE_SYSTEM,
            "cornerCount": corner_count,
            "markerCount": marker_count,
            "captureCount": count,
            "imageWidth": image_size[0],
            "imageHeight": image_size[1],
        }

    def reset_captures(self) -> None:
        with self._lock:
            self._samples.clear()
            self._image_size = None

    def solve(self) -> dict[str, Any]:
        with self._lock:
            samples = list(self._samples)
            image_size = self._image_size
        minimum = self.config.charuco.minimum_captures
        if image_size is None or len(samples) < minimum:
            raise ValueError(
                f"Se requieren al menos {minimum} capturas ChArUco aceptadas."
            )
        corners = [sample[0] for sample in samples]
        ids = [sample[1] for sample in samples]
        rms, camera_matrix, distortion, _, _ = cv2.aruco.calibrateCameraCharuco(
            charucoCorners=corners,
            charucoIds=ids,
            board=self.board(),
            imageSize=image_size,
            cameraMatrix=None,
            distCoeffs=None,
        )
        rms = float(rms)
        if not np.isfinite(rms):
            raise ValueError("La calibracion produjo un error no finito")
        if rms > self.config.max_reprojection_error_px:
            raise ValueError(
                f"Error RMS {rms:.3f}px excede el limite "
                f"{self.config.max_reprojection_error_px:.3f}px. Capture mejores vistas."
            )
        saved = self.repository.save_intrinsics(
            {
                "imageWidth": image_size[0],
                "imageHeight": image_size[1],
                "cameraMatrix": np.asarray(camera_matrix).tolist(),
                "distortionCoefficients": np.asarray(distortion).reshape(-1).tolist(),
                "reprojectionErrorPx": rms,
                "coordinateSystem": IMAGE_COORDINATE_SYSTEM,
                "board": {
                    "dictionary": self.config.charuco.dictionary,
                    "squaresX": self.config.charuco.squares_x,
                    "squaresY": self.config.charuco.squares_y,
                    "squareLengthMeters": self.config.charuco.square_length_meters,
                    "markerLengthMeters": self.config.charuco.marker_length_meters,
                },
            }
        )
        self.reset_captures()
        return saved

    def status(self) -> dict[str, Any]:
        with self._lock:
            capture_count = len(self._samples)
            capture_size = self._image_size
        return {
            "captureCount": capture_count,
            "captureImageSize": list(capture_size) if capture_size else None,
            "minimumCaptures": self.config.charuco.minimum_captures,
        }


class WorldCalibrationService:
    def __init__(
        self,
        config: VisionConfig,
        repository: CalibrationRepository,
        transformer: CoordinateTransformer,
    ) -> None:
        self.config = config
        self.repository = repository
        self.transformer = transformer

    @staticmethod
    def _marker_correspondences(payload: dict[str, Any]) -> tuple[list, list] | None:
        corners = payload.get("markerImageCorners")
        size = payload.get("markerSizeMeters")
        if corners is None or size is None:
            return None
        if len(corners) != 4 or float(size) <= 0:
            raise ValueError("El marcador requiere cuatro esquinas y un tamano positivo")
        position = payload.get("markerWorldPosition", {"x": 0.0, "y": 0.0, "z": 0.0})
        cx, cy = float(position.get("x", 0.0)), float(position.get("y", 0.0))
        half = float(size) / 2.0
        world = [
            [cx - half, cy - half, 0.0],
            [cx + half, cy - half, 0.0],
            [cx + half, cy + half, 0.0],
            [cx - half, cy + half, 0.0],
        ]
        return corners, world

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        intrinsics = self.repository.load_intrinsics()
        if not intrinsics:
            raise ValueError("Primero debe completarse la calibracion intrinseca")
        image_points = payload.get("imagePoints")
        world_points = payload.get("worldPoints")
        marker = self._marker_correspondences(payload)
        if (image_points is None or world_points is None) and marker:
            image_points, world_points = marker
        if image_points is None or world_points is None:
            raise ValueError("Se requieren imagePoints y worldPoints, o un marcador conocido")

        image = np.asarray(image_points, dtype=np.float64)
        world = np.asarray(world_points, dtype=np.float64)
        if image.ndim != 2 or image.shape[1] != 2 or len(image) < 4:
            raise ValueError("imagePoints debe contener al menos cuatro puntos [u,v]")
        if world.ndim != 2 or world.shape[0] != image.shape[0] or world.shape[1] not in (2, 3):
            raise ValueError("worldPoints debe corresponder a imagePoints y usar [x,y] o [x,y,z]")
        if world.shape[1] == 2:
            world3 = np.column_stack([world, np.zeros(len(world))])
        else:
            world3 = world.copy()
        if np.max(np.abs(world3[:, 2])) > 1e-6:
            raise ValueError("La homografia de suelo solo acepta puntos con Z=0")

        image_to_ground, mask = cv2.findHomography(image, world3[:, :2], method=0)
        if image_to_ground is None or abs(np.linalg.det(image_to_ground)) < 1e-12:
            raise ValueError("No fue posible calcular una homografia estable")
        ground_to_image = np.linalg.inv(image_to_ground)

        k = np.asarray(intrinsics["cameraMatrix"], dtype=np.float64)
        distortion = np.asarray(
            intrinsics.get("distortionCoefficients", []), dtype=np.float64
        )
        ok, rvec, tvec = cv2.solvePnP(
            world3,
            image,
            k,
            distortion,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            raise ValueError("No fue posible calcular la pose de la camara")
        rotation_world_to_camera, _ = cv2.Rodrigues(rvec)
        rotation_camera_to_world = rotation_world_to_camera.T
        translation_camera_to_world = -rotation_camera_to_world @ tvec.reshape(3)

        projected = cv2.perspectiveTransform(
            image.reshape((-1, 1, 2)).astype(np.float64), image_to_ground
        ).reshape((-1, 2))
        errors = np.linalg.norm(projected - world3[:, :2], axis=1)
        validation_error = float(np.sqrt(np.mean(errors**2)))
        if validation_error > self.config.max_world_validation_error_meters:
            raise ValueError(
                f"Error de validacion {validation_error:.3f}m excede el limite "
                f"{self.config.max_world_validation_error_meters:.3f}m."
            )

        supplied_height = payload.get("cameraHeightMeters")
        estimated_height = abs(float(translation_camera_to_world[2]))
        camera_height = float(supplied_height) if supplied_height is not None else estimated_height
        if camera_height <= 0:
            raise ValueError("cameraHeightMeters debe ser positivo")

        return self.repository.save_world(
            {
                "originDefinition": payload.get(
                    "originDefinition", "camera_floor_projection"
                ),
                "rotationMatrix": rotation_camera_to_world.tolist(),
                "translationVectorMeters": translation_camera_to_world.tolist(),
                "imageToGroundHomography": image_to_ground.tolist(),
                "groundToImageHomography": ground_to_image.tolist(),
                "cameraHeightMeters": camera_height,
                "validationErrorMeters": validation_error,
                "validationPointCount": int(len(image)),
                "imageWidth": intrinsics["imageWidth"],
                "imageHeight": intrinsics["imageHeight"],
                "coordinateSystem": {
                    "unit": "meter",
                    "origin": payload.get(
                        "originDefinition", "camera_floor_projection"
                    ),
                    "xAxis": "right",
                    "yAxis": "forward",
                    "zAxis": "up",
                },
            }
        )

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        image_point = payload.get("imagePoint")
        world_point = payload.get("worldPoint")
        if not image_point or not world_point:
            raise ValueError("Se requieren imagePoint y worldPoint")
        measured = self.transformer.image_ground_point(
            float(image_point["u"]), float(image_point["v"])
        )
        expected = np.array([float(world_point["x"]), float(world_point["y"])])
        error = float(np.linalg.norm(np.array([measured.x, measured.y]) - expected))
        return {
            "valid": error <= self.config.max_world_validation_error_meters,
            "errorMeters": error,
            "maximumErrorMeters": self.config.max_world_validation_error_meters,
            "measuredWorldPoint": measured.as_dict(),
        }


class CalibrationStatusService:
    def __init__(
        self,
        config: VisionConfig,
        repository: CalibrationRepository,
        intrinsic_service: IntrinsicCalibrationService,
    ) -> None:
        self.config = config
        self.repository = repository
        self.intrinsic_service = intrinsic_service

    def get(self, resolution: tuple[int, int] | None = None) -> dict[str, Any]:
        intrinsics = self.repository.load_intrinsics()
        world = self.repository.load_world()
        blockers: list[str] = []
        warnings: list[str] = []
        if self.config.calibration_invalidated:
            blockers.append("camera_moved_or_optics_changed")
        if not intrinsics:
            blockers.append("missing_intrinsics")
        if not world:
            blockers.append("missing_world_pose")
        if intrinsics and float(intrinsics.get("reprojectionErrorPx", 999)) > self.config.max_reprojection_error_px:
            blockers.append("intrinsic_error_exceeded")
        if world and float(world.get("validationErrorMeters", 999)) > self.config.max_world_validation_error_meters:
            blockers.append("world_error_exceeded")
        if resolution and intrinsics:
            expected = (int(intrinsics["imageWidth"]), int(intrinsics["imageHeight"]))
            if tuple(resolution) != expected:
                blockers.append("resolution_mismatch")
        if intrinsics:
            warnings.append(
                "Recalibre si cambia resolucion, enfoque, zoom o posicion de la optica."
            )
        return {
            "cameraId": self.config.camera_id,
            "sensorMode": self.config.sensor_mode,
            "coordinateSystems": {
                "intrinsics": "image_pixels",
                "world": "world_ground_meters",
            },
            "scanReady": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "intrinsics": intrinsics,
            "world": world,
            "assistant": self.intrinsic_service.status(),
        }
