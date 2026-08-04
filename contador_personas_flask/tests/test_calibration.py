from __future__ import annotations

import cv2
import numpy as np

from app.vision.calibration import IntrinsicCalibrationService, WorldCalibrationService
from app.vision.geometry import CoordinateTransformer
from app.vision.repositories import CalibrationRepository


def test_charuco_fixture_is_detected_without_real_camera(vision_config, charuco_frame):
    repository = CalibrationRepository(vision_config)
    service = IntrinsicCalibrationService(vision_config, repository)
    result = service.capture(charuco_frame)
    assert result["accepted"] is True
    assert result["cornerCount"] >= 4
    assert result["captureCount"] == 1


def test_world_pose_and_homography_from_known_points(vision_config):
    repository = CalibrationRepository(vision_config)
    k = np.array([[800.0, 0, 640.0], [0, 800.0, 360.0], [0, 0, 1.0]])
    repository.save_intrinsics(
        {
            "imageWidth": 1280,
            "imageHeight": 720,
            "cameraMatrix": k.tolist(),
            "distortionCoefficients": [0, 0, 0, 0, 0],
            "reprojectionErrorPx": 0.1,
        }
    )
    world_points = np.array([[-2, 1, 0], [2, 1, 0], [2, 5, 0], [-2, 5, 0]], np.float64)
    rotation_world_to_camera = np.diag([1.0, -1.0, -1.0])
    rvec, _ = cv2.Rodrigues(rotation_world_to_camera)
    tvec = np.array([0.0, 0.0, 3.0])
    image_points, _ = cv2.projectPoints(world_points, rvec, tvec, k, np.zeros(5))
    image_points = image_points.reshape((-1, 2))
    transformer = CoordinateTransformer(vision_config, repository)
    service = WorldCalibrationService(vision_config, repository, transformer)
    result = service.solve(
        {
            "cameraHeightMeters": 3.0,
            "imagePoints": image_points.tolist(),
            "worldPoints": world_points.tolist(),
        }
    )
    assert result["version"] == 1
    assert result["validationErrorMeters"] < 1e-6
    recovered = transformer.image_ground_point(*image_points[0])
    assert np.allclose([recovered.x, recovered.y], world_points[0, :2], atol=1e-6)
