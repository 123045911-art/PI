from __future__ import annotations

import os
from dataclasses import replace

import cv2
import pytest

from app.vision.config import CharucoConfig, VisionConfig


@pytest.fixture
def vision_config(tmp_path):
    base = VisionConfig.from_env()
    return replace(
        base,
        camera_id="cam-test",
        sensor_mode="monocular",
        data_root=tmp_path,
        max_reprojection_error_px=2.0,
        max_world_validation_error_meters=0.20,
        charuco=CharucoConfig(
            dictionary="DICT_5X5_100",
            squares_x=7,
            squares_y=5,
            square_length_meters=0.04,
            marker_length_meters=0.02,
            minimum_captures=3,
        ),
    )


@pytest.fixture
def charuco_frame(vision_config):
    dictionary_id = getattr(cv2.aruco, vision_config.charuco.dictionary)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    board = cv2.aruco.CharucoBoard(
        (vision_config.charuco.squares_x, vision_config.charuco.squares_y),
        vision_config.charuco.square_length_meters,
        vision_config.charuco.marker_length_meters,
        dictionary,
    )
    gray = board.generateImage((1400, 1000), marginSize=80, borderBits=1)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


@pytest.fixture(autouse=True)
def safe_environment(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-not-for-production")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("VISIOFLOW_START_BACKGROUND", "0")
    monkeypatch.delenv("API_SERVICE_USERNAME", raising=False)
    monkeypatch.delenv("API_SERVICE_PASSWORD", raising=False)
