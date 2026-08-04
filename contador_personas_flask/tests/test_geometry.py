from __future__ import annotations

import numpy as np

from app.vision.geometry import (
    CoordinateTransformer,
    bbox_foot_point,
    point_in_polygon,
)


def test_rgbd_deprojection_with_known_intrinsics():
    k = [[100.0, 0.0, 50.0], [0.0, 200.0, 40.0], [0.0, 0.0, 1.0]]
    point = CoordinateTransformer.deproject_rgbd(60, 60, 2.0, k)
    assert np.allclose(point, [0.2, 0.2, 2.0])


def test_image_to_ground_homography():
    homography = [[0.01, 0, -1], [0, 0.02, -2], [0, 0, 1]]
    point = CoordinateTransformer.image_to_ground(200, 150, homography)
    assert np.allclose(point, [1.0, 1.0, 0.0])


def test_camera_to_world_transform():
    rotation = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    translation = [10, 20, 1]
    point = CoordinateTransformer.camera_to_world([2, 3, 4], rotation, translation)
    assert np.allclose(point, [7, 22, 5])


def test_point_inside_polygon_includes_boundary():
    polygon = [[0, 0], [2, 0], [2, 2], [0, 2]]
    assert point_in_polygon((1, 1), polygon)
    assert point_in_polygon((0, 1), polygon)
    assert not point_in_polygon((3, 1), polygon)


def test_bbox_position_uses_bottom_center_of_feet():
    assert bbox_foot_point([10, 20, 50, 100]) == (30.0, 100.0)
