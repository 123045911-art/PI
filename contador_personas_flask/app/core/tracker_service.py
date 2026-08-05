import csv
import logging
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from ultralytics.models.yolo import YOLO
import os

from app.core.api_client import VisioFlowApiClient
from app.vision.camera import BrowserPushCameraProvider
from app.vision.depth import DepthProvider, MonocularDepthProvider
from app.vision.geometry import (
    IMAGE_COORDINATE_SYSTEM,
    WORLD_COORDINATE_SYSTEM,
    CoordinateTransformer,
    bbox_foot_point,
)
from app.vision.repositories import SceneRepository
from app.vision.tracking import YoloDeepSortPersonTrackingAdapter

logger = logging.getLogger("visioflow.api")

AsyncVideoCapture = BrowserPushCameraProvider



class TrackerService:
    def __init__(
        self,
        api_client: VisioFlowApiClient | None = None,
        *,
        coordinate_transformer: CoordinateTransformer | None = None,
        depth_provider: DepthProvider | None = None,
        scene_repository: SceneRepository | None = None,
        camera_id: str = "cam-01",
        start_background: bool = True,
    ) -> None:
        self.lock = threading.RLock()
        self.conf_threshold = 0.35
        self.flush_interval_seconds = 5.0
        self.max_track_inactive_seconds = 2.0

        self.project_root = Path(__file__).resolve().parents[2]
        self.csv_path = self.project_root / "areas_log.csv"

        self.api_client = api_client or VisioFlowApiClient()
        self.coordinate_transformer = coordinate_transformer
        self.depth_provider = depth_provider or MonocularDepthProvider()
        self.scene_repository = scene_repository
        self.camera_id = camera_id
        
        # LAZY INITIALIZATION: No cargamos el modelo ni abrimos la camara aqui para no bloquear Flask
        self.model: Optional[YOLO] = None
        self.tracker: Optional[DeepSort] = None
        self.capture: Optional[AsyncVideoCapture] = None
        self.tracking_adapter: Optional[YoloDeepSortPersonTrackingAdapter] = None
        self.initialized = False

        self.areas: Dict[int, dict] = {}
        self.next_area_id = 1
        data_root = scene_repository.config.data_root if scene_repository else self.project_root / "data"
        self.local_areas_path = data_root / "areas" / f"{self.camera_id}.json"
        self.track_states: Dict[int, dict] = {}
        self.event_buffer: List[dict] = []
        self.last_flush_ts = time.time()
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.latest_tracks: List[dict] = []
        self.last_heatmap_sent: Dict[int, float] = {}
        self.frame_id = 0
        self.last_captured_at: Optional[str] = None
        self._load_local_areas()

        # Frame de carga inicial
        self.latest_encoded_frame = self._create_status_frame("Cargando VisioFlow...")
        
        self.processing_thread: Optional[threading.Thread] = None
        if start_background:
            self.processing_thread = threading.Thread(
                target=self._processing_loop, daemon=True
            )
            self.processing_thread.start()

    def _create_status_frame(self, text: str) -> bytes:
        """Crea un frame negro con el texto indicado codificado en JPEG."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, text, (50, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        _, enc = cv2.imencode(".jpg", frame)
        return enc.tobytes()

    def _load_local_areas(self) -> None:
        if not self.local_areas_path.exists():
            return
        try:
            payload = json.loads(self.local_areas_path.read_text(encoding="utf-8"))
            for item in payload.get("areas", []):
                area_id = int(item["id"])
                self.areas[area_id] = {
                    "id": area_id,
                    "api_id": item.get("api_id"),
                    "external_id": str(item.get("external_id") or f"area-local-{area_id}"),
                    "name": str(item["name"]),
                    "x1": int(item["x1"]), "y1": int(item["y1"]),
                    "x2": int(item["x2"]), "y2": int(item["y2"]),
                    "current_count": 0, "total_entries": 0, "total_exits": 0,
                    "total_dwell_seconds": 0.0,
                }
            self.next_area_id = max(self.areas, default=0) + 1
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("No se pudieron cargar las areas locales: %s", exc)

    def _save_local_areas(self) -> None:
        with self.lock:
            payload = {
                "cameraId": self.camera_id,
                "areas": [
                    {key: area.get(key) for key in ("id", "api_id", "external_id", "name", "x1", "y1", "x2", "y2")}
                    for area in self.areas.values()
                ],
            }
        self.local_areas_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.local_areas_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.local_areas_path)


    def _initialize_visioflow_engine(self):
        import torch
        import psutil
        logger.info("Initializing VISIOFLOW HW Engine...")
        model_path = str(self.project_root / "yolov8n.pt")
        
        # 1. Detectar NVIDIA CUDA
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"VISIOFLOW Engine: Detectado y utilizando [Aceleración Dedicada (CUDA): {device_name}]")
            model = YOLO(model_path, task="detect")
            model.to("cuda:0")
            tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
            return model, tracker

        # Posible NVIDIA GPU detectada en SO pero no configurada en Docker
        # Chequeo genérico leyendo PCI (esto es simulado ya que lspci puede no estar)
        # Vamos a invocar un chequeo rápido si el path driver/nvidia existe
        import os
        if os.path.exists("/proc/driver/nvidia/version"):
            print("VISIOFLOW Engine: NVIDIA CUDA no detectado, aunque hay GPU NVIDIA presente en el Host.")
            print("         * RECOMENDACIÓN *" )
            print("Para lograr máximos FPS sin cuellos de botella mediante Hardware NVIDIA en este equipo,")
            print("proceda a instalar NVIDIA Container Toolkit del siguiente enlace:")
            print("-> https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html")

        # 2. Intentar OpenVINO / DirectX Indirects (Intel/AMD) 
        # Si corremos YOLO usando openvino export se optimiza fuertemente.
        # En la primera corrida esto tardará exportando el PT a OpenVINO
        can_use_openvino_or_dml = True
        if can_use_openvino_or_dml:
            try:
                # El formato de YOLO soporta exportación dinámica openvino
                # pero para fiabilidad 'multi-target' exporta si no existe y lo carga
                print("VISIOFLOW Engine: Detectado y utilizando [Aceleración Universal OpenVINO/ONNX]")
                model = YOLO(model_path, task="detect")
                try:
                    # Inicia un try export a openvino
                    export_dir = "yolov8n_openvino_model"
                    if not os.path.exists(export_dir):
                       logger.info("VISIOFLOW: Exportando base a OpenVINO/ONNX por primera vez...")
                       model.export(format="openvino", half=True, dynamic=True)
                    # Cargar Openvino 
                    ov_model = YOLO("yolov8n_openvino_model/", task="detect") # Carga IR openvino 
                    tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
                    cv2.setNumThreads(psutil.cpu_count(logical=False) or 2)
                    return ov_model, tracker
                except Exception as e:
                    print(f"VISIOFLOW Warning: OpenVINO / ONNX Export fallido, fallback a CPU OMP. ({e})")
            except Exception as e:
                pass

        # 3. CPU Fallback Óptima
        print("VISIOFLOW Engine: Detectado y utilizando [Inferencia en CPU Optimizada (Multi-threading)]")
        # Limitar hilos a máximo 4 para evitar sobrecarga en procesadores multinúcleo
        max_threads = min(4, psutil.cpu_count(logical=False) or 4)
        torch.set_num_threads(max_threads)
        cv2.setNumThreads(max_threads)
        model = YOLO(model_path, task="detect")
        model.to("cpu")
        tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
        return model, tracker

    def add_area(self, name: str, x1: int, y1: int, x2: int, y2: int, is_admin: bool = False) -> dict:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError("El nombre del área debe tener entre 1 y 100 caracteres.")
        if min(x1, y1, x2, y2) < 0:
            raise ValueError("Las coordenadas del área no pueden ser negativas.")

        rx1, rx2 = sorted((x1, x2))
        ry1, ry2 = sorted((y1, y2))
        if rx1 == rx2 or ry1 == ry2:
            raise ValueError(
                "El rectangulo del area no puede tener lados de longitud cero."
            )

        with self.lock:
            area_id = self.next_area_id
            self.next_area_id += 1

            area = {
                "id": area_id,
                "api_id": None,
                "external_id": f"area-local-{area_id}",
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
            is_admin=is_admin
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
            result = dict(self.areas[area_id])
        api_id = result.get("api_id")
        if api_id is not None:
            self.api_client.update_area(int(api_id), name=result["name"], x1=rx1, y1=ry1, x2=rx2, y2=ry2)
        self.api_client.sync_alert_area(str(result["external_id"]), name=result["name"])
        self._save_local_areas()
        return result

    def update_area(self, area_id: int, *, name: str, x1: int, y1: int, x2: int, y2: int) -> dict:
        name = name.strip()
        rx1, rx2 = sorted((int(x1), int(x2)))
        ry1, ry2 = sorted((int(y1), int(y2)))
        if min(rx1, ry1, rx2, ry2) < 0:
            raise ValueError("Las coordenadas del área no pueden ser negativas.")
        if not name or len(name) > 100 or rx1 == rx2 or ry1 == ry2:
            raise ValueError("El area requiere nombre y un rectangulo valido.")
        with self.lock:
            if area_id not in self.areas:
                raise KeyError(area_id)
            self.areas[area_id].update(
                {"name": name, "x1": rx1, "y1": ry1, "x2": rx2, "y2": ry2}
            )
            result = dict(self.areas[area_id])
        self._save_local_areas()
        return result

    def delete_area(self, area_id: int) -> bool:
        with self.lock:
            if area_id not in self.areas:
                return False
            removed = self.areas.pop(area_id)
            for state in self.track_states.values():
                state.get("inside_areas", set()).discard(area_id)
                state.get("entry_times", {}).pop(area_id, None)
        if removed.get("api_id") is not None:
            self.api_client.delete_area(int(removed["api_id"]))
        self.api_client.sync_alert_area(str(removed["external_id"]), delete=True)
        self._save_local_areas()
        return True

    def add_local_area(
        self,
        name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        external_id: str,
    ) -> dict:
        """Register a demo area without requiring the unfinished remote server."""
        rx1, rx2 = sorted((int(x1), int(x2)))
        ry1, ry2 = sorted((int(y1), int(y2)))
        if not name or rx1 == rx2 or ry1 == ry2:
            raise ValueError("El area local requiere nombre y un rectangulo valido.")
        with self.lock:
            existing = next(
                (item for item in self.areas.values() if item.get("external_id") == external_id),
                None,
            )
            if existing:
                return existing
            area_id = self.next_area_id
            self.next_area_id += 1
            area = {
                "id": area_id,
                "api_id": None,
                "external_id": external_id,
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
            result = dict(area)
        self._save_local_areas()
        return result

    def sync_area(self, area_id: int) -> dict:
        with self.lock:
            area = self.areas.get(area_id)
            if area is None:
                raise KeyError(area_id)
            if area.get("api_id") is not None:
                return dict(area)
            payload = dict(area)
        created = self.api_client.create_area(
            name=payload["name"], x1=payload["x1"], y1=payload["y1"],
            x2=payload["x2"], y2=payload["y2"], is_admin=True,
        )
        if created and created.get("id") is not None:
            with self.lock:
                self.areas[area_id]["api_id"] = int(created["id"])
                payload = dict(self.areas[area_id])
            self._save_local_areas()
        return payload

    def _point_in_area(self, cx: int, cy: int, area: dict) -> bool:
        return area["x1"] <= cx <= area["x2"] and area["y1"] <= cy <= area["y2"]

    def _log_event(
        self, track_id: int, area: dict, event_type: str, dwell_seconds: float
    ) -> None:
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

    def _handle_transitions(
        self, track_id: int, inside_now: Set[int], timestamp: float
    ) -> None:
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
            cv2.rectangle(
                frame, (area["x1"], area["y1"]), (area["x2"], area["y2"]), color, 2
            )
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

    def process_frame(self) -> Optional[np.ndarray]:
        if (
            not self.initialized
            or self.capture is None
            or self.tracking_adapter is None
        ):
            return None

        # 1. Captura de frame (Sincronizada solo para el objeto capture)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            with self.lock:
                # Debe coincidir con la resolucion real de captura del navegador
                # (640x480, ver getUserMedia en app.js). Si difiere, cualquier
                # area dibujada mientras se mostraba este relleno queda
                # calibrada contra el tamano equivocado y nunca vuelve a
                # coincidir con las detecciones reales.
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "Camara activa, sin imagen...", (30, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                self._flush_events_to_csv_if_needed()
                return frame

        captured_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        with self.lock:
            self.latest_raw_frame = frame.copy()
            self.frame_id += 1
            frame_id = self.frame_id
            self.last_captured_at = captured_at

        # 2. Inferencia fuera del lock. El adaptador conserva YOLOv8 + DeepSORT.
        tracks = self.tracking_adapter.track(frame)
        
        # 3. Actualización de Estados y Dibujo (DENTRO DEL LOCK)
        with self.lock:
            now = time.time()
            active_track_ids = set()
            live_tracks: List[dict] = []
            heatmap_samples: List[dict] = []

            for track in tracks:
                track_id = int(track["trackId"])
                active_track_ids.add(track_id)
                x1, y1, x2, y2 = [int(round(value)) for value in track["bbox"]]
                confidence = float(track.get("confidence", 0.0))

                try:
                    foot_u, foot_v = bbox_foot_point((x1, y1, x2, y2))
                except ValueError as exc:
                    # DeepSort a veces entrega una caja momentaneamente invertida
                    # (prediccion de Kalman entre detecciones). Se descarta solo
                    # este track en este frame en vez de abortar el conteo de
                    # areas completo para todos los demas.
                    logger.warning("Track %s con bbox invalido, se omite este frame: %s", track_id, exc)
                    continue

                # Si la persona esta demasiado cerca de la camara (o la camara
                # esta encuadrada muy arriba), sus pies reales quedan fuera del
                # cuadro y la caja detectada termina cortada justo en el borde
                # inferior de la imagen. Usar ese borde como "punto de los pies"
                # es enganoso: nunca coincidira con areas que no lleguen hasta
                # el borde. En ese caso usamos el centro vertical del cuerpo
                # visible, mucho mas estable.
                frame_height = frame.shape[0]
                if y2 >= frame_height - 2:
                    foot_v = (y1 + y2) / 2.0

                inside_now = {
                    area_id
                    for area_id, area in self.areas.items()
                    if self._point_in_area(int(foot_u), int(foot_v), area)
                }

                self._handle_transitions(track_id, inside_now, now)

                live_track = {
                    "trackerId": f"trk-{track_id}",
                    "capturedAt": captured_at,
                    "imagePoint": {
                        "u": round(float(foot_u), 3),
                        "v": round(float(foot_v), 3),
                        "coordinateSystem": IMAGE_COORDINATE_SYSTEM,
                    },
                    "bbox": {
                        "left": x1,
                        "top": y1,
                        "right": x2,
                        "bottom": y2,
                        "coordinateSystem": IMAGE_COORDINATE_SYSTEM,
                    },
                    "confidence": round(confidence, 4),
                    "calibrationVersion": 0,
                    "positionValid": False,
                    "worldPoint": None,
                }
                try:
                    if self.coordinate_transformer is None:
                        raise ValueError("Transformador de coordenadas no configurado")
                    if self.depth_provider.mode == "monocular":
                        world_point = self.coordinate_transformer.image_ground_point(
                            foot_u, foot_v
                        )
                    else:
                        depth = self.depth_provider.sample(foot_u, foot_v)
                        if depth is None:
                            raise ValueError("Profundidad invalida en el punto de los pies")
                        world_point = self.coordinate_transformer.metric_point_from_depth(
                            foot_u, foot_v, depth.meters, depth.confidence
                        )
                    calibration = self.coordinate_transformer.repository.load_world() or {}
                    live_track.update(
                        {
                            "calibrationVersion": int(calibration.get("version", 0)),
                            "positionValid": True,
                            "worldPoint": world_point.as_dict(),
                            "x": round(world_point.x, 6),
                            "y": round(world_point.y, 6),
                            "z": round(world_point.z, 6),
                        }
                    )
                except (ValueError, KeyError) as exc:
                    height, width = frame.shape[:2]
                    live_track.update(
                        {
                            "x": round(max(0.0, min(1.75, float(foot_u) / max(width, 1) * 1.75)), 6),
                            "y": round(max(0.0, min(4.5, (height - float(foot_v)) / max(height, 1) * 4.5)), 6),
                            "z": 0.0,
                            "positionSource": "image_approximation",
                            "positionWarning": str(exc),
                        }
                    )
                live_tracks.append(live_track)

                if now - self.last_heatmap_sent.get(track_id, 0.0) >= 1.0:
                    containing = next((self.areas[item] for item in inside_now if self.areas[item].get("api_id") is not None), None)
                    heatmap_samples.append({
                        "track_id": track_id, "cx": int(round(foot_u)), "cy": int(round(foot_v)),
                        "timestamp_iso": captured_at,
                        "area_id": int(containing["api_id"]) if containing else None,
                    })
                    self.last_heatmap_sent[track_id] = now

                cv2.rectangle(frame, (x1, y1), (x2, y2), (34, 197, 94), 2)
                cv2.circle(frame, (int(foot_u), int(foot_v)), 4, (234, 179, 8), -1)
                cv2.putText(frame, f"ID {track_id}", (x1, max(20, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (34, 197, 94), 2)

            for track_id, state in self.track_states.items():
                if track_id not in active_track_ids:
                    state["last_seen"] = min(state["last_seen"], now - 0.001)

            self._handle_stale_tracks(now)
            self._update_current_counts()
            self._draw_areas(frame)
            self._flush_events_to_csv_if_needed()
            self.latest_tracks = live_tracks

        for sample in heatmap_samples:
            self.api_client.send_heatmap_point(**sample)
        return frame

    def _processing_loop(self):
        """Hebra que procesa el video continuamente, arrancando el motor de forma diferida."""
        try:
            print("VISIOFLOW: Entrando en hebra de procesamiento...")
            time.sleep(2) # Dar un respiro al arranque de Flask
            print("VISIOFLOW: Iniciando carga de motor YOLO (OpenVINO/CPU)...")
            self.model, self.tracker = self._initialize_visioflow_engine()
            self.tracking_adapter = YoloDeepSortPersonTrackingAdapter(
                self.model, self.tracker, self.conf_threshold
            )
            print("VISIOFLOW: Motor de IA cargado con éxito.")
            
            logger.info("VISIOFLOW: Intentando conectar al stream MJPEG (Network Bypass)...")
            self.latest_encoded_frame = self._create_status_frame("Iniciando stream...")
            self.capture = AsyncVideoCapture()
            
            if self.capture.isOpened():
                self.initialized = True
                logger.info("VISIOFLOW: Sistema COMPLETAMENTE INICIALIZADO. Procesando stream...")
            else:
                logger.error("VISIOFLOW: No se pudo conectar al stream MJPEG. Asegúrate de que el Host de Windows esté transmitiendo en el puerto 5001.")
                self.latest_encoded_frame = self._create_status_frame("Error: Link MJPEG fail")
                # No detenemos la hebra para que Flask siga vivo y permita ver el mensaje en el stream
        except Exception as e:
            logger.error(f"Error CRÍTICO en inicialización: {e}", exc_info=True)
            self.latest_encoded_frame = self._create_status_frame(f"ERROR: {str(e)[:25]}...")
            # No retornamos aquí, dejamos que el loop inferior ruede avisando del error

        while True:
            try:
                frame = self.process_frame()
                if frame is not None:
                    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ok:
                        self.latest_encoded_frame = encoded.tobytes()
                time.sleep(0.06)  # ~15 FPS; suficiente para rastreo y libera >50% de CPU
            except Exception as e:
                logger.error(f"Error en loop de procesamiento: {e}")
                time.sleep(1.0)

    def generate_mjpeg_stream(self):
        """Vista fluida de camara con las detecciones procesadas mas recientes."""
        while True:
            preview = self.capture.latest_frame() if self.capture else None
            encoded_bytes = self.latest_encoded_frame
            if preview is not None:
                with self.lock:
                    for track in self.latest_tracks:
                        bbox = track.get("bbox") or {}
                        try:
                            x1, y1, x2, y2 = (
                                int(bbox["left"]), int(bbox["top"]),
                                int(bbox["right"]), int(bbox["bottom"]),
                            )
                        except (KeyError, TypeError, ValueError):
                            continue
                        cv2.rectangle(preview, (x1, y1), (x2, y2), (34, 197, 94), 2)
                        cv2.putText(
                            preview, str(track.get("trackerId", "")),
                            (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (34, 197, 94), 2,
                        )
                    self._draw_areas(preview)
                ok, encoded = cv2.imencode(
                    ".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                if ok:
                    encoded_bytes = encoded.tobytes()
            if encoded_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + encoded_bytes + b"\r\n"
                )
            else:
                # Frame de espera si aún no hay proceso
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(black_frame, "Iniciando camara...", (100, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                _, enc = cv2.imencode(".jpg", black_frame)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + enc.tobytes() + b"\r\n"
                )
            
            # FPS capping para el stream (no para el procesamiento)
            # Esto ahorra ancho de banda y CPU en los sockets
            time.sleep(0.10) # ~10 FPS; mantiene margen de CPU para YOLO

    def ingest_pushed_frame(self, frame: np.ndarray) -> bool:
        """Entrega un frame subido por el navegador de un visitante a la
        fuente de video activa. Devuelve False si el pipeline aun no ha
        terminado de inicializar (self.capture todavia es None)."""
        if self.capture is None:
            return False
        self.capture.push_frame(frame)
        return True

    def get_latest_raw_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            return self.latest_raw_frame.copy() if self.latest_raw_frame is not None else None

    def get_latest_jpeg(self) -> bytes:
        with self.lock:
            return bytes(self.latest_encoded_frame)

    def get_resolution(self) -> tuple[int, int] | None:
        with self.lock:
            if self.latest_raw_frame is None:
                return None
            return int(self.latest_raw_frame.shape[1]), int(self.latest_raw_frame.shape[0])

    def get_live_tracks(self) -> dict:
        with self.lock:
            calibration_version = max(
                [int(item.get("calibrationVersion", 0)) for item in self.latest_tracks]
                or [0]
            )
            scene = self.scene_repository.load() if self.scene_repository else None
            return {
                "cameraId": self.camera_id,
                "frameId": self.frame_id,
                "capturedAt": self.last_captured_at,
                "coordinateSystem": WORLD_COORDINATE_SYSTEM,
                "imageCoordinateSystem": IMAGE_COORDINATE_SYSTEM,
                "sensorMode": self.depth_provider.mode,
                "calibrationVersion": calibration_version,
                "sceneVersion": int((scene or {}).get("version", 0)),
                "tracks": deepcopy_tracks(self.latest_tracks),
            }

    def health_status(self) -> dict:
        return {
            "engineReady": self.initialized,
            "cameraReady": bool(self.capture and self.capture.isOpened()),
            "frameId": self.frame_id,
            "camera": self.capture.status() if self.capture else None,
            "depth": self.depth_provider.status(),
        }

    def get_stats(self) -> dict:
        with self.lock:
            areas = []
            for area in self.areas.values():
                total_entries = area["total_entries"]
                avg_dwell = (
                    area["total_dwell_seconds"] / total_entries
                    if total_entries > 0
                    else 0.0
                )
                areas.append(
                    {
                        "id": area["id"],
                        "api_id": area.get("api_id"),
                        "external_id": area.get("external_id"),
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


def deepcopy_tracks(tracks: List[dict]) -> List[dict]:
    """Copia JSON-safe sin exponer el estado mutable del hilo de tracking."""
    import copy

    return copy.deepcopy(tracks)
