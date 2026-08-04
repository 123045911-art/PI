from __future__ import annotations

from typing import Any


class PersonTrackingAdapter:
    """Contrato minimo para detectores/trackers de personas."""

    def track(self, frame) -> list[dict[str, Any]]:
        raise NotImplementedError


class YoloDeepSortPersonTrackingAdapter(PersonTrackingAdapter):
    """Conserva YOLOv8 (clase 0/person) y DeepSORT del proyecto original."""

    def __init__(self, model, tracker, confidence_threshold: float = 0.35) -> None:
        self.model = model
        self.tracker = tracker
        self.confidence_threshold = confidence_threshold

    def track(self, frame) -> list[dict[str, Any]]:
        results = self.model.predict(
            source=frame,
            verbose=False,
            classes=[0],
            conf=self.confidence_threshold,
        )
        detections = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = float(box.conf[0].item())
                detections.append(
                    ([x1, y1, x2 - x1, y2 - y1], confidence, "person")
                )
        tracks = self.tracker.update_tracks(detections, frame=frame)
        output: list[dict[str, Any]] = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            left, top, right, bottom = track.to_ltrb()
            confidence = getattr(track, "det_conf", None)
            output.append(
                {
                    "trackId": int(track.track_id),
                    "bbox": [float(left), float(top), float(right), float(bottom)],
                    "confidence": float(confidence) if confidence is not None else 0.0,
                }
            )
        return output
