import csv
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
from ultralytics.models.yolo import YOLO
import queue
import os

from app.core.api_client import VisioFlowApiClient

logger = logging.getLogger("visioflow.api")

class AsyncVideoCapture:
    def __init__(self, src=None):
        if src is None:
            src = os.environ.get("CAMERA_SOURCE", "http://host.docker.internal:5001/video")
            if str(src).isdigit():
                src = int(src)
                
        self.cap = cv2.VideoCapture(src)
        
        if self.cap and self.cap.isOpened():
            logger.info(f"VISIOFLOW: Conectado con éxito al stream/camara en {src}")
        else:
            logger.error(f"VISIOFLOW: No se pudo conectar al stream/camara en {src}")
            if self.cap:
                self.cap.release()
            self.cap = None


        self.q = queue.Queue(maxsize=2)
        self.stopped = False
        
        self.t = threading.Thread(target=self._reader, args=(), daemon=True)
        self.t.start()
        
    def _reader(self):
        consecutive_failures = 0
        while not self.stopped:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(1.0)
                continue
            
            ret, frame = self.cap.read()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures > 30:
                    logger.error("Cámara desconectada o fallando persistentemente.")
                    # Opcional: intentar reabrir
                    time.sleep(1.0)
                continue
            
            consecutive_failures = 0
            if not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
            self.q.put(frame)
            
    def read(self):
        try:
            return True, self.q.get(timeout=0.5)
        except queue.Empty:
            return False, None
        
    def isOpened(self):
        return self.cap is not None and self.cap.isOpened()
        
    def release(self):
        self.stopped = True
        if self.t.is_alive():
            self.t.join(timeout=1.0)
        if self.cap:
            self.cap.release()



class TrackerService:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.conf_threshold = 0.35
        self.flush_interval_seconds = 5.0
        self.max_track_inactive_seconds = 2.0

        self.project_root = Path(__file__).resolve().parents[2]
        self.csv_path = self.project_root / "areas_log.csv"

        self.api_client = VisioFlowApiClient()
        
        # LAZY INITIALIZATION: No cargamos el modelo ni abrimos la camara aqui para no bloquear Flask
        self.model: Optional[YOLO] = None
        self.tracker: Optional[DeepSort] = None
        self.capture: Optional[AsyncVideoCapture] = None
        self.initialized = False

        self.areas: Dict[int, dict] = {}
        self.next_area_id = 1
        self.track_states: Dict[int, dict] = {}
        self.event_buffer: List[dict] = []
        self.last_flush_ts = time.time()

        # Frame de carga inicial
        self.latest_encoded_frame = self._create_status_frame("Cargando VisioFlow...")
        
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()

    def _create_status_frame(self, text: str) -> bytes:
        """Crea un frame negro con el texto indicado codificado en JPEG."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, text, (50, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        _, enc = cv2.imencode(".jpg", frame)
        return enc.tobytes()


    def _initialize_visioflow_engine(self):
        import torch
        import psutil
        logger.info("Initializing VISIOFLOW HW Engine...")
        model_path = "yolov8n.pt"
        
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
        # Forzar threads a OMP y backend torch
        torch.set_num_threads(psutil.cpu_count(logical=False) or 4)
        cv2.setNumThreads(psutil.cpu_count(logical=False) or 4)
        model = YOLO(model_path, task="detect")
        model.to("cpu")
        tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
        return model, tracker

    def add_area(self, name: str, x1: int, y1: int, x2: int, y2: int, is_admin: bool = False) -> dict:
        if not name:
            raise ValueError("El nombre del area es obligatorio.")

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
            return self.areas[area_id]

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
        if not self.initialized or self.capture is None or self.model is None or self.tracker is None:
            return None

        # 1. Captura de frame (Sincronizada solo para el objeto capture)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            with self.lock:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(frame, "Cámara activa, pero no entrega imagen...", (40, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                self._flush_events_to_csv_if_needed()
                return frame

        # 2. Inferencia (FUERA DEL LOCK, esta es la parte lenta que queremos paralelizar)
        results = self.model.predict(
            source=frame,
            verbose=False,
            classes=[0],
            conf=self.conf_threshold,
        )

        if not results:
            with self.lock:
                self._handle_stale_tracks(time.time())
                self._update_current_counts()
                self._draw_areas(frame)
                self._flush_events_to_csv_if_needed()
            return frame

        result = results[0]
        boxes = result.boxes
        if boxes is None:
            with self.lock:
                self._handle_stale_tracks(time.time())
                self._update_current_counts()
                self._draw_areas(frame)
                self._flush_events_to_csv_if_needed()
            return frame

        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            detections.append(([x1, y1, x2 - x1, y2 - y1], conf, "person"))

        tracks = self.tracker.update_tracks(detections, frame=frame)
        
        # 3. Actualización de Estados y Dibujo (DENTRO DEL LOCK)
        with self.lock:
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
                cv2.putText(frame, f"ID {track_id}", (x1, max(20, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (34, 197, 94), 2)

            for track_id, state in self.track_states.items():
                if track_id not in active_track_ids:
                    state["last_seen"] = min(state["last_seen"], now - 0.001)

            self._handle_stale_tracks(now)
            self._update_current_counts()
            self._draw_areas(frame)
            self._flush_events_to_csv_if_needed()
            
        return frame

    def _processing_loop(self):
        """Hebra que procesa el video continuamente, arrancando el motor de forma diferida."""
        try:
            print("VISIOFLOW: Entrando en hebra de procesamiento...")
            time.sleep(2) # Dar un respiro al arranque de Flask
            print("VISIOFLOW: Iniciando carga de motor YOLO (OpenVINO/CPU)...")
            self.model, self.tracker = self._initialize_visioflow_engine()
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
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Error en loop de procesamiento: {e}")
                time.sleep(1.0)

    def generate_mjpeg_stream(self):
        """Sirve el ultimo frame procesado a los clientes MJPEG."""
        while True:
            if self.latest_encoded_frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + self.latest_encoded_frame + b"\r\n"
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
            time.sleep(0.06) # ~15 FPS

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
