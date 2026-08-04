from __future__ import annotations

from dataclasses import replace

from app.vision.scene import SceneAggregator, generate_fixed_point_matrix


def test_fixed_point_matrix_marks_occupied_points(vision_config):
    scene = {
        "fieldOfViewPolygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "objects": [
            {
                "id": "obj-table-01",
                "type": "table",
                "confidence": 0.9,
                "footprint": [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]],
            }
        ],
    }
    matrix = generate_fixed_point_matrix(scene, 0.5)
    assert len(matrix) == 9
    occupied = [point for point in matrix if point["occupied"]]
    assert occupied
    assert all(point["objectId"] == "obj-table-01" for point in occupied)


def test_scene_aggregation_fuses_stable_repeated_objects(vision_config):
    config = replace(
        vision_config,
        scan_detection_rate=0.60,
        scan_cluster_distance_meters=0.5,
        scan_position_tolerance_meters=0.2,
        scan_dimension_tolerance_meters=0.2,
    )
    observations = []
    for frame_index, x in enumerate([1.00, 1.02, 0.99]):
        observations.append(
            {
                "frameIndex": frame_index,
                "objectType": "table",
                "footprint": [[x, 1], [x + 1, 1], [x + 1, 2], [x, 2]],
                "center": [x + 0.5, 1.5, 0],
                "widthMeters": 1.0,
                "depthMeters": 1.0,
                "heightMeters": 0.8,
                "depthMethod": "rgbd",
                "approximate": False,
                "confidence": 0.9,
            }
        )
    result = SceneAggregator(config).aggregate(observations, total_frames=3)
    assert len(result) == 1
    assert result[0]["framesObserved"] == 3
    assert result[0]["detectionRate"] == 1.0
    assert result[0]["type"] == "table"


def test_scene_aggregation_rejects_unstable_detection(vision_config):
    observations = [
        {
            "frameIndex": 0,
            "objectType": "rack",
            "footprint": [[0, 0], [1, 0], [1, 1]],
            "center": [0.5, 0.5, 0],
            "widthMeters": 1,
            "depthMeters": 1,
            "heightMeters": None,
            "depthMethod": "ground_plane",
            "approximate": True,
            "confidence": 0.8,
        }
    ]
    assert SceneAggregator(vision_config).aggregate(observations, total_frames=10) == []
