import csv
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from ultralytics import YOLO

from app.core.api_client import VisioFlowApiClient

logger = logging.getLogger("visioflow.api")


class TrackerService:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.camera_index = 1
        self.conf_threshold = 0.35
        self.flush_interval_seconds = 5.0
        self.max_track_inactive_seconds = 2.0

        self.project_root = Path(__file__).resolve().parents[2]
        self.csv_path = self.project_root / "areas_log.csv"

        self.api_client = VisioFlowApiClient()

        self.model = YOLO("yolov8n.pt")
        self.tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
        self.capture = cv2.VideoCapture(self.camera_index)

        self.areas: Dict[int, dict] = {}
        self.next_area_id = 1
        self.track_states: Dict[int, dict] = {}
        self.event_buffer: List[dict] = []
        self.last_flush_ts = time.time()

    def add_area(self, name: str, x1: int, y1: int, x2: int, y2: int) -> dict:
        if not name:
            raise ValueError("El nombre del area es obligatorio.")

        rx1, rx2 = sorted((x1, x2))
        ry1, ry2 = sorted((y1, y2))
        if rx1 == rx2 or ry1 == ry2:
            raise ValueError("El rectangulo del area no puede tener lados de longitud cero.")

        with self.lock:
            area_id = self.next_area_id
            self.next_area_id += 1

            area = {
                "id": area_id,
                "api_id": None,
                "name": name,
                "x1": rx1,
                "y1": ry1,
                "x2": rx2,
                "y2": ry2,
                "current_count": 0,
                "total_entries": 0,
                "total_exits": 0,
                "total_dwell_seconds": 0.0,
            }
            self.areas[area_id] = area

        created = self.api_client.create_area(
            name=name,
            x1=rx1,
            y1=ry1,
            x2=rx2,
            y2=ry2,
        )

        with self.lock:
            if area_id in self.areas:
                if created and created.get("id") is not None:
                    self.areas[area_id]["api_id"] = int(created["id"])
                else:
                    logger.warning(
                        "Área local creada pero no hay api_id de FastAPI; "
                        "POST /events no se usará para esta área hasta que exista id remoto. "
                        "local_id=%s name=%s",
                        area_id,
                        name,
                    )
            return self.areas[area_id]

    def _point_in_area(self, cx: int, cy: int, area: dict) -> bool:
        return area["x1"] <= cx <= area["x2"] and area["y1"] <= cy <= area["y2"]

    def _log_event(self, track_id: int, area: dict, event_type: str, dwell_seconds: float) -> None:
        event_time = datetime.now().isoformat(timespec="seconds")
        dwell_rounded = round(float(dwell_seconds), 2)
        event = {
            "event_time": event_time,
            "track_id": track_id,
            "area_id": area["id"],
            "area_name": area["name"],
            "event_type": event_type,
            "dwell_seconds": dwell_rounded,
        }
        self.event_buffer.append(event)

        api_id = area.get("api_id")
        if api_id is None:
            logger.warning(
                "Evento sin api_id; no se envía a FastAPI (área no sincronizada). "
                "local_area_id=%s track_id=%s event=%s",
                area["id"],
                track_id,
                event_type,
            )
        else:
            self.api_client.send_event(
                area_id=int(api_id),
                track_id=track_id,
                event=event_type,
                timestamp_iso=event_time,
                dwell=dwell_rounded,
            )

    def _handle_transitions(self, track_id: int, inside_now: Set[int], timestamp: float) -> None:
        state = self.track_states.setdefault(
            track_id,
            {"inside_areas": set(), "entry_times": {}, "last_seen": timestamp},
        )
        inside_before = set(state["inside_areas"])

        entered = inside_now - inside_before
        exited = inside_before - inside_now

        for area_id in entered:
            area = self.areas[area_id]
            area["total_entries"] += 1
            state["entry_times"][area_id] = timestamp
            self._log_event(track_id, area, "enter", 0.0)

        for area_id in exited:
            area = self.areas[area_id]
            area["total_exits"] += 1
            started_at = state["entry_times"].pop(area_id, timestamp)
            dwell = max(0.0, timestamp - started_at)
            area["total_dwell_seconds"] += dwell
            self._log_event(track_id, area, "exit", dwell)

        state["inside_areas"] = inside_now
        state["last_seen"] = timestamp

    def _handle_stale_tracks(self, now: float) -> None:
        stale_ids = []
        for track_id, state in self.track_states.items():
            if now - state["last_seen"] <= self.max_track_inactive_seconds:
                continue

            for area_id in list(state["inside_areas"]):
                area = self.areas.get(area_id)
                if area is None:
                    continue
                area["total_exits"] += 1
                started_at = state["entry_times"].pop(area_id, now)
                dwell = max(0.0, now - started_at)
                area["total_dwell_seconds"] += dwell
                self._log_event(track_id, area, "exit", dwell)

            stale_ids.append(track_id)

        for track_id in stale_ids:
            self.track_states.pop(track_id, None)

    def _update_current_counts(self) -> None:
        for area in self.areas.values():
            area["current_count"] = 0

        for state in self.track_states.values():
            for area_id in state["inside_areas"]:
                area = self.areas.get(area_id)
                if area:
                    area["current_count"] += 1

    def _flush_events_to_csv_if_needed(self) -> None:
        now = time.time()
        if now - self.last_flush_ts < self.flush_interval_seconds:
            return

        if not self.event_buffer:
            self.last_flush_ts = now
            return

        file_exists = self.csv_path.exists()
        with self.csv_path.open("a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "event_time",
                    "track_id",
                    "area_id",
                    "area_name",
                    "event_type",
                    "dwell_seconds",
                ],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerows(self.event_buffer)

        self.event_buffer.clear()
        self.last_flush_ts = now

    def _draw_areas(self, frame: np.ndarray) -> None:
        for area in self.areas.values():
            color = (56, 189, 248)
            cv2.rectangle(frame, (area["x1"], area["y1"]), (area["x2"], area["y2"]), color, 2)
            label = f'{area["name"]} | now:{area["current_count"]}'
            cv2.putText(
                frame,
                label,
                (area["x1"], max(20, area["y1"] - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )

    def process_frame(self) -> np.ndarray:
        with self.lock:
            ok, frame = self.capture.read()
            if not ok or frame is None:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(
                    frame,
                    "No hay video disponible en la camara.",
                    (40, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )
                self._flush_events_to_csv_if_needed()
                return frame

            result = self.model.predict(
                source=frame,
                verbose=False,
                classes=[0],
                conf=self.conf_threshold,
            )[0]

            detections = []
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                detections.append(([x1, y1, x2 - x1, y2 - y1], conf, "person"))

            tracks = self.tracker.update_tracks(detections, frame=frame)
            now = time.time()
            active_track_ids = set()

            for track in tracks:
                if not track.is_confirmed():
                    continue

                track_id = int(track.track_id)
                active_track_ids.add(track_id)
                l, t, r, b = track.to_ltrb()
                x1, y1, x2, y2 = int(l), int(t), int(r), int(b)

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                inside_now = {
                    area_id
                    for area_id, area in self.areas.items()
                    if self._point_in_area(cx, cy, area)
                }

                self._handle_transitions(track_id, inside_now, now)

                cv2.rectangle(frame, (x1, y1), (x2, y2), (34, 197, 94), 2)
                cv2.circle(frame, (cx, cy), 4, (234, 179, 8), -1)
                cv2.putText(
                    frame,
                    f"ID {track_id}",
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (34, 197, 94),
                    2,
                    cv2.LINE_AA,
                )

            for track_id, state in self.track_states.items():
                if track_id not in active_track_ids:
                    state["last_seen"] = min(state["last_seen"], now - 0.001)

            self._handle_stale_tracks(now)
            self._update_current_counts()
            self._draw_areas(frame)
            self._flush_events_to_csv_if_needed()
            return frame

    def generate_mjpeg_stream(self):
        while True:
            frame = self.process_frame()
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            jpg_bytes = encoded.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n"
            )

    def get_stats(self) -> dict:
        with self.lock:
            areas = []
            for area in self.areas.values():
                total_entries = area["total_entries"]
                avg_dwell = (
                    area["total_dwell_seconds"] / total_entries if total_entries > 0 else 0.0
                )
                areas.append(
                    {
                        "id": area["id"],
                        "api_id": area.get("api_id"),
                        "name": area["name"],
                        "rect": [area["x1"], area["y1"], area["x2"], area["y2"]],
                        "current_count": area["current_count"],
                        "total_entries": area["total_entries"],
                        "total_exits": area["total_exits"],
                        "total_dwell_seconds": round(area["total_dwell_seconds"], 2),
                        "avg_dwell_seconds": round(avg_dwell, 2),
                    }
                )

            return {
                "areas": areas,
                "events_buffered": len(self.event_buffer),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
