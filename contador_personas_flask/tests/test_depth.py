from __future__ import annotations

from dataclasses import replace

import numpy as np

from app.vision.depth import RGBDDepthProvider


def test_invalid_depth_is_rejected_and_valid_patch_uses_median(vision_config):
    config = replace(vision_config, sensor_mode="rgbd", min_depth_meters=0.5, max_depth_meters=5.0)
    provider = RGBDDepthProvider(config)
    depth = np.full((7, 7), np.nan, dtype=np.float32)
    depth[2:5, 2:5] = [
        [0.0, 2.0, 2.1],
        [99.0, 2.2, 2.0],
        [2.1, 2.0, -1.0],
    ]
    provider.update_depth_map(depth)
    sample = provider.sample(3, 3)
    assert sample is not None
    assert 2.0 <= sample.meters <= 2.1
    assert provider.sample(0, 0) is None


def test_rgbd_status_reports_valid_percentage(vision_config):
    provider = RGBDDepthProvider(replace(vision_config, sensor_mode="rgbd"))
    provider.update_depth_map(np.array([[1.0, np.nan], [1.5, 999.0]], dtype=np.float32))
    status = provider.status()
    assert status["available"] is True
    assert status["validPointPercentage"] == 50.0
