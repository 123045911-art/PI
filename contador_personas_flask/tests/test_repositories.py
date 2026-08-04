from __future__ import annotations

from app.vision.repositories import CalibrationRepository, SceneRepository


def test_calibration_serialization_and_versioning(vision_config):
    repository = CalibrationRepository(vision_config)
    first = repository.save_intrinsics(
        {
            "imageWidth": 640,
            "imageHeight": 480,
            "cameraMatrix": [[500, 0, 320], [0, 500, 240], [0, 0, 1]],
            "distortionCoefficients": [],
            "reprojectionErrorPx": 0.4,
        }
    )
    second = repository.save_intrinsics({**first, "reprojectionErrorPx": 0.3})
    assert first["version"] == 1
    assert second["version"] == 2
    assert repository.load_intrinsics()["cameraId"] == "cam-test"


def test_scene_serialization_uses_expected_coordinate_system(vision_config):
    repository = SceneRepository(vision_config)
    saved = repository.save(repository.empty_scene(calibration_version=3))
    assert saved["version"] == 1
    assert saved["calibrationVersion"] == 3
    assert saved["coordinateSystem"]["unit"] == "meter"
