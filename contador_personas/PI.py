import cv2, csv, time, numpy as np
import argparse, os, sys
import threading
import customtkinter as ctk
from PIL import Image

try:
    import mysql.connector as mysql_connector
except Exception:
    mysql_connector = None
    print("[DB] Advertencia: mysql-connector-python no está instalado. No se registrarán datos en MySQL.")

from ultralytics import YOLO  # type: ignore
from deep_sort_realtime.deepsort_tracker import DeepSort


MAX_DISPLAY_W = 960
MAX_DISPLAY_H = 540
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "visionflow.jpg")


def create_capture():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=str, default=os.environ.get("DROIDCAM_SOURCE", ""))
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--list-cams", action="store_true")
    args, _ = parser.parse_known_args()
    source = (args.source or "").strip()
    explicit_source = bool(source)

    cap = None

    def try_open(src):
        if isinstance(src, int) or (isinstance(src, str) and src.isdigit()):
            idx = int(src)
            c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if c is not None and c.isOpened():
                print(f"Usando cámara por índice: {idx}")
                return c
            return None
        s = str(src)
        if s.startswith("http://") or s.startswith("https://") or s.startswith("rtsp://"):
            c = cv2.VideoCapture(s, cv2.CAP_FFMPEG)
            if c is not None and c.isOpened():
                print(f"Usando fuente por URL: {s}")
                return c
            c = cv2.VideoCapture(s)
            if c is not None and c.isOpened():
                print(f"Usando fuente por URL (fallback): {s}")
                return c
            return None
        c = cv2.VideoCapture(s)
        if c is not None and c.isOpened():
            print(f"Usando fuente: {s}")
            return c
        return None

    if args.list_cams:
        print("Probando dispositivos de cámara (índices 0..10, backend DirectShow):")
        opened = []
        for idx in range(0, 11):
            c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if c is not None and c.isOpened():
                width = int(c.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                fps = c.get(cv2.CAP_PROP_FPS) or 0
                print(f" - Index {idx}: abierto ({width}x{height} @ {fps:.2f}fps)")
                opened.append(idx)
                c.release()
        if not opened:
            print("No se encontraron cámaras por índice.")
        else:
            print("Consejo: ejecuta con --source <indice> --source-only para fijar la cámara.")
        sys.exit(0)

    if source:
        alternatives = [source]
        if source.endswith("/video"):
            alternatives.append(source.replace("/video", "/mjpegfeed"))
        elif source.endswith("/mjpegfeed"):
            alternatives.append(source.replace("/mjpegfeed", "/video"))
        for s in alternatives:
            cap = try_open(s)
            if cap:
                return cap
        if args.source_only or explicit_source:
            print(f"No se pudo abrir la fuente especificada: {source}", file=sys.stderr)
            sys.exit(1)

    for idx in [1, 2, 0]:
        cap = try_open(idx)
        if cap:
            return cap

    url = (os.environ.get("DROIDCAM_URL", "") or "").strip()
    if url:
        for s in [url,
                  url.replace("/video", "/mjpegfeed") if url.endswith("/video")
                  else url.replace("/mjpegfeed", "/video")]:
            cap = try_open(s)
            if cap:
                return cap

    print("No se pudo abrir la cámara. Use --source=<indice|url> o DROIDCAM_URL.", file=sys.stderr)
    sys.exit(1)


model = YOLO("yolov8n.pt")
tracker = DeepSort(max_age=40, n_init=3, max_iou_distance=0.6)
cap = create_capture()

areas, area_stats, track_area_state = [], {}, {}
drawing_area, area_start, temp_rect = False, None, None
pending_area_name = None
colors = [(255, 165, 0), (0, 255, 255), (255, 0, 255), (0, 255, 0), (0, 128, 255)]
log_buffer, last_flush = [], time.time()
db_logger = None
last_heatmap_flush = 0.0
heatmap_interval = 0.5


class MySQLLogger:
    def __init__(self, host, user, password, database, enable_heatmap=False, verbose=True):
        if not mysql_connector:
            raise RuntimeError("mysql-connector-python no está instalado.")

        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.enable_heatmap = enable_heatmap
        self.verbose = verbose
        self.conn = None

        print(f"[DB] MySQLLogger.__init__: host={host}, user={user}, db={database}, heatmap={enable_heatmap}")
        self._connect()

    def _log(self, msg):
        if self.verbose:
            print(f"[DB] {msg}")

    def _connect(self):
        self._log("Intentando crear nueva conexión MySQL...")
        if mysql_connector is None:
            raise RuntimeError("mysql-connector-python no está instalado.")
        try:
            self.conn = mysql_connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.conn.autocommit = True  # type: ignore
            self._log(f"Conexión creada correctamente a {self.host}, DB={self.database}, user={self.user}")
        except Exception as e:
            print(f"[DB] Error conectando a MySQL en _connect: {repr(e)}", file=sys.stderr)
            raise

    def _ensure_conn(self):
        """
        Verifica y reestablece la conexión si es necesario.
        """
        if self.conn is None:
            self._log("self.conn es None. Se intentará reconectar...")
            self._connect()
        else:
            try:
                if not self.conn.is_connected():
                    self._log("self.conn.is_connected() = False. Se intentará reconectar...")
                    self._connect()
            except Exception as e:
                self._log(f"Error al verificar is_connected: {repr(e)}. Se intentará reconectar...")
                self._connect()
        
        if self.conn is None:
            raise RuntimeError("No se pudo establecer la conexión a MySQL")
        return self.conn

    def insert_area(self, name, x1, y1, x2, y2):
        conn = self._ensure_conn()
        self._log(f"insert_area() -> name={name}, rect=({x1},{y1},{x2},{y2})")
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO areas (name, x1, y1, x2, y2) VALUES (%s,%s,%s,%s,%s)",
                (name, int(x1), int(y1), int(x2), int(y2)),
            )
            area_id = cur.lastrowid
            cur.close()
            self._log(f"Area creada id={area_id} name='{name}' rect=({x1},{y1},{x2},{y2})")
            return area_id
        except Exception as e:
            self._log(f"insert_area() falló: {repr(e)}")
            raise

    def rename_area(self, area_id, new_name):
        conn = self._ensure_conn()
        self._log(f"rename_area() -> area_id={area_id}, new_name={new_name}")
        try:
            cur = conn.cursor()
            cur.execute("UPDATE areas SET name=%s WHERE id=%s", (new_name, int(area_id)))
            cur.close()
            self._log(f"Area renombrada id={area_id} nuevo_nombre='{new_name}'")
        except Exception as e:
            self._log(f"rename_area() falló: {repr(e)}")
            raise

    def insert_event(self, ts_str, area_id, track_id, event, dwell):
        conn = self._ensure_conn()
        self._log(f"insert_event() -> ts={ts_str}, area_id={area_id}, track_id={track_id}, event={event}, dwell={dwell}")
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO area_events (timestamp, area_id, track_id, event, dwell) VALUES (%s,%s,%s,%s,%s)",
                (ts_str, int(area_id), int(track_id), str(event), float(dwell)),
            )
            cur.close()
            self._log("insert_event() completado")
        except Exception as e:
            self._log(f"insert_event() falló: {repr(e)}")
            raise

    def upsert_area_state(self, area_id, people_count):
        conn = self._ensure_conn()
        self._log(f"upsert_area_state() -> area_id={area_id}, people_count={people_count}")
        try:
            cur = conn.cursor()
            cur.execute("SELECT area_id FROM area_state WHERE area_id=%s", (int(area_id),))
            exists = cur.fetchone()
            if exists:
                cur.execute(
                    "UPDATE area_state SET people_count=%s, last_update=NOW() WHERE area_id=%s",
                    (int(people_count), int(area_id)),
                )
                op = "update"
            else:
                cur.execute(
                    "INSERT INTO area_state (area_id, people_count) VALUES (%s,%s)",
                    (int(area_id), int(people_count)),
                )
                op = "insert"
            cur.close()
            self._log(f"Area_state {op} area_id={area_id} people_count={people_count}")
        except Exception as e:
            self._log(f"upsert_area_state() falló: {repr(e)}")
            raise

    def insert_heatmap_point(self, ts_str, area_id_or_none, track_id, cx, cy):
        if not self.enable_heatmap:
            return
        conn = self._ensure_conn()
        self._log(
            f"insert_heatmap_point() -> ts={ts_str}, area_id={area_id_or_none}, "
            f"track_id={track_id}, cx={cx}, cy={cy}"
        )
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO heatmap_points (timestamp, area_id, track_id, cx, cy) VALUES (%s,%s,%s,%s,%s)",
                (ts_str, area_id_or_none, int(track_id), int(cx), int(cy)),
            )
            cur.close()
            self._log("insert_heatmap_point() completado")
        except Exception as e:
            self._log(f"insert_heatmap_point() falló: {repr(e)}")
            raise

    def close(self):
        try:
            if self.conn is not None and self.conn.is_connected():
                self._log("Cerrando conexión MySQL...")
                self.conn.close()
        except Exception as e:
            self._log(f"Error al cerrar conexión: {repr(e)}")


def setup_db():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db-host", type=str, default=os.environ.get("DB_HOST", "srv1282.hstgr.io"))
    parser.add_argument("--db-user", type=str, default=os.environ.get("DB_USER", "u412005698_vision"))
    parser.add_argument("--db-pass", type=str, default=os.environ.get("DB_PASS", "visionFlow3"))
    parser.add_argument("--db-name", type=str, default=os.environ.get("DB_NAME", "u412005698_contador_P"))
    parser.add_argument("--db-disable", action="store_true")
    parser.add_argument("--db-heatmap", action="store_true")
    parser.add_argument("--db-quiet", action="store_true")
    args, _ = parser.parse_known_args()

    print(
        f"[DB] setup_db(): host={args.db_host}, user={args.db_user}, "
        f"db={args.db_name}, disable={args.db_disable}, heatmap={args.db_heatmap}"
    )

    if args.db_disable:
        print("[DB] Base de datos deshabilitada por --db-disable.")
        return None

    if not mysql_connector:
        print("[DB] mysql-connector-python no disponible, no se creará db_logger.")
        return None

    try:
        logger = MySQLLogger(
            host=args.db_host,
            user=args.db_user,
            password=args.db_pass,
            database=args.db_name,
            enable_heatmap=args.db_heatmap,
            verbose=(not args.db_quiet),
        )
        print("[DB] db_logger inicializado correctamente.")
        return logger
    except Exception as e:
        print(f"[DB] No se pudo conectar a MySQL en setup_db(): {repr(e)}", file=sys.stderr)
        return None


db_logger = setup_db()


def normalize_rect(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    return (x1, y1, x2, y2)


def point_in_rect(px, py, rect):
    x1, y1, x2, y2 = rect
    return x1 <= px <= x2 and y1 <= py <= y2


def log_event(ts, aid, event, tid, count, dwell):
    log_buffer.append([ts, aid, event, tid, count, round(dwell, 2)])
    if db_logger:
        try:
            db_area_id = None
            if 0 <= aid < len(areas):
                db_area_id = areas[aid].get("db_id")
            if db_area_id:
                db_logger.insert_event(ts, db_area_id, tid, event, dwell)
                db_logger.upsert_area_state(db_area_id, count)
            else:
                print(f"[DB] log_event(): area {aid} no tiene db_id, no se inserta en DB.")
        except Exception as e:
            print(f"[DB] Error registrando evento: {repr(e)}", file=sys.stderr)


def flush_log():
    global log_buffer, last_flush
    if log_buffer and time.time() - last_flush > 5:
        with open("areas_log.csv", "a", newline="") as f:
            csv.writer(f).writerows(log_buffer)
        try:
            print(f"[CSV] {len(log_buffer)} filas escritas en areas_log.csv")
        except Exception:
            pass
        log_buffer.clear()
        last_flush = time.time()


class VisionApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.COLOR_BG = "#050509"
        self.COLOR_HEADER = "#0D47A1"
        self.COLOR_PANEL = "#0B1020"
        self.COLOR_ACCENT = "#FF9800"
        self.COLOR_TEXT = "#FFFFFF"

        self.title("Sistema de Vision Computarizada")
        self.configure(fg_color=self.COLOR_BG)
        self.geometry("1200x700")
        self.resizable(False, False)

        # referencias del logo
        self.logo_pil = None
        self.logo_img = None

        self.modo_edicion = ctk.BooleanVar(value=True)
        self.fps = 0.0
        self.last_time = time.time()
        self.frame_count = 0

        self.ctk_frame_image = None

        self.crear_layout()
        self.bind_events()

        self.after(10, self.loop_video)

    def crear_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color=self.COLOR_HEADER, corner_radius=0, height=60)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_rowconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)

        # LOGO EN EL HEADER
        try:
            self.logo_pil = Image.open(LOGO_PATH)
            self.logo_img = ctk.CTkImage(
                light_image=self.logo_pil,
                dark_image=self.logo_pil,
                size=(48, 48)
            )
            lbl_logo = ctk.CTkLabel(
                header,
                text="",
                image=self.logo_img
            )
            lbl_logo.grid(row=0, column=0, padx=(16, 8), pady=6, sticky="w")
        except Exception as e:
            print(f"[UI] No se pudo cargar el logo desde {LOGO_PATH}: {e}")

        self.lbl_titulo = ctk.CTkLabel(
            header,
            text="Sistema de Vision Computarizada",
            font=("Segoe UI Semibold", 18),
            text_color=self.COLOR_TEXT
        )
        self.lbl_titulo.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.lbl_estado = ctk.CTkLabel(
            header,
            text="Modo: Edicion de areas",
            font=("Segoe UI", 13),
            text_color=self.COLOR_ACCENT
        )
        self.lbl_estado.grid(row=0, column=2, padx=20, pady=10, sticky="e")

        side = ctk.CTkFrame(self, fg_color=self.COLOR_PANEL, corner_radius=18, width=240)
        side.grid(row=1, column=0, padx=12, pady=12, sticky="nsew")
        side.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            side, text="Controles", font=("Segoe UI Semibold", 14),
            text_color=self.COLOR_TEXT
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        self.switch_modo = ctk.CTkSwitch(
            side, text="Modo edicion", variable=self.modo_edicion,
            font=("Segoe UI", 12), text_color=self.COLOR_TEXT,
            progress_color=self.COLOR_ACCENT, fg_color="#1a2233",
            command=self.cambiar_modo
        )
        self.switch_modo.grid(row=1, column=0, padx=16, pady=(4, 12), sticky="w")

        ctk.CTkLabel(
            side, text="Nombre del area:", font=("Segoe UI", 12),
            text_color=self.COLOR_TEXT
        ).grid(row=2, column=0, padx=16, pady=(4, 2), sticky="w")

        self.area_name_var = ctk.StringVar()
        self.entry_area = ctk.CTkEntry(
            side, textvariable=self.area_name_var,
            font=("Segoe UI", 12), width=200
        )
        self.entry_area.grid(row=3, column=0, padx=16, pady=(0, 6), sticky="ew")

        self.btn_dibujar = ctk.CTkButton(
            side, text="Dibujar area",
            fg_color=self.COLOR_ACCENT, hover_color="#ffb74d",
            text_color="#000000", corner_radius=10,
            command=self.activar_dibujo
        )
        self.btn_dibujar.grid(row=4, column=0, padx=16, pady=6, sticky="ew")

        self.lbl_areas = ctk.CTkLabel(
            side, text="Areas definidas: 0",
            font=("Segoe UI", 12), text_color=self.COLOR_TEXT
        )
        self.lbl_areas.grid(row=5, column=0, padx=16, pady=(10, 4), sticky="w")

        self.lbl_hint = ctk.CTkLabel(
            side,
            text="Edicion:\n• Click y arrastrar en el video\n  para crear el rectangulo.",
            font=("Segoe UI", 11), text_color="#B0BEC5", justify="left"
        )
        self.lbl_hint.grid(row=6, column=0, padx=16, pady=(8, 8), sticky="w")

        main = ctk.CTkFrame(self, fg_color=self.COLOR_BG, corner_radius=18)
        main.grid(row=1, column=1, padx=(0, 12), pady=12, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.label_video = ctk.CTkLabel(main, text="", fg_color=self.COLOR_BG)
        self.label_video.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        status = ctk.CTkFrame(self, fg_color="#050812", corner_radius=12, height=40)
        status.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="nsew")
        status.grid_columnconfigure(0, weight=1)

        self.lbl_fps = ctk.CTkLabel(
            status, text="FPS: 0.0",
            font=("Segoe UI", 11), text_color=self.COLOR_TEXT
        )
        self.lbl_fps.grid(row=0, column=0, padx=16, pady=6, sticky="w")

    def bind_events(self):
        self.label_video.bind("<ButtonPress-1>", self.on_mouse_down)
        self.label_video.bind("<B1-Motion>", self.on_mouse_move)
        self.label_video.bind("<ButtonRelease-1>", self.on_mouse_up)

    def cambiar_modo(self):
        if self.modo_edicion.get():
            self.switch_modo.configure(text="Modo edicion")
            self.lbl_estado.configure(text="Modo: Edicion de areas", text_color=self.COLOR_ACCENT)
        else:
            self.switch_modo.configure(text="Modo monitoreo")
            self.lbl_estado.configure(text="Modo: Monitoreo", text_color="#80DEEA")

    def activar_dibujo(self):
        global drawing_area, pending_area_name
        pending_area_name = self.area_name_var.get().strip()
        drawing_area = True        
        print(f"[UI] activar_dibujo(): pending_area_name='{pending_area_name}'")

    def on_mouse_down(self, event):
        global drawing_area, area_start, temp_rect
        if not self.modo_edicion.get() or not drawing_area:
            return
        area_start = (event.x, event.y)
        temp_rect = (event.x, event.y, event.x, event.y)
        print(f"[UI] on_mouse_down(): inicio rect en {area_start}")

    def on_mouse_move(self, event):
        global drawing_area, area_start, temp_rect
        if not self.modo_edicion.get() or not drawing_area or area_start is None:
            return
        temp_rect = normalize_rect(area_start, (event.x, event.y))

    def on_mouse_up(self, event):
        global drawing_area, area_start, temp_rect, pending_area_name, areas, area_stats
        if not self.modo_edicion.get() or not drawing_area or area_start is None:
            drawing_area = False
            area_start = None
            temp_rect = None
            return
        rect = normalize_rect(area_start, (event.x, event.y))
        print(f"[UI] on_mouse_up(): rect final={rect}")
        if rect[2] - rect[0] > 5 and rect[3] - rect[1] > 5:
            aid = len(areas)
            name = (pending_area_name or "").strip()
            if not name:
                name = f"Area {aid+1}"
            print(f"[UI] Creando area local id={aid} name='{name}' rect={rect}")
            areas.append({"id": aid, "rect": rect, "name": name})
            area_stats[aid] = {"current_ids": set(), "total_dwell": 0.0, "avg_dwell": 0.0}
            pending_area_name = None
            if db_logger:
                try:
                    x1, y1, x2, y2 = rect
                    print("[DB] on_mouse_up(): intentando insertar area en MySQL...")
                    db_id = db_logger.insert_area(name, x1, y1, x2, y2)
                    areas[-1]["db_id"] = db_id
                    print(f"[DB] on_mouse_up(): area insertada con db_id={db_id}")
                    db_logger.upsert_area_state(db_id, 0)
                except Exception as e:
                    print(f"[DB] Error insertando area: {repr(e)}", file=sys.stderr)
        else:
            print("[UI] on_mouse_up(): rect demasiado pequeño, no se crea área.")

        drawing_area = False
        area_start = None
        temp_rect = None
        self.lbl_areas.configure(text=f"Areas definidas: {len(areas)}")

    def loop_video(self):
        global temp_rect, last_heatmap_flush

        ok, frame = cap.read()
        if not ok:
            self.lbl_titulo.configure(text="Error: camara no disponible")
            self.after(200, self.loop_video)
            return

        h0, w0 = frame.shape[:2]
        scale = min(MAX_DISPLAY_W / w0, MAX_DISPLAY_H / h0)
        disp_w = int(w0 * scale)
        disp_h = int(h0 * scale)
        frame = cv2.resize(frame, (disp_w, disp_h))

        if temp_rect is not None and self.modo_edicion.get():
            x1, y1, x2, y2 = temp_rect
            cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), 1)

        results = model.predict(source=frame, conf=0.35, classes=[0], verbose=False)
        dets = []
        for r in results:
            if r.boxes is None:
                continue
            b = r.boxes
            xyxy = b.xyxy.cpu().numpy()  # type: ignore
            conf = b.conf.cpu().numpy()  # type: ignore
            for (x1, y1, x2, y2), s in zip(xyxy, conf):
                dets.append(([x1, y1, x2 - x1, y2 - y1], s, "person"))

        tracks = tracker.update_tracks(dets, frame=frame)

        for i, a in enumerate(areas):
            x1, y1, x2, y2 = a["rect"]
            c = colors[i % len(colors)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
            st = area_stats[a["id"]]
            label = f'{a["name"]}: {len(st["current_ids"])} | t={int(st["total_dwell"])}s'
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)

        active = set()
        now = time.time()

        for t in tracks:
            if not t.is_confirmed():
                continue
            tid = t.track_id
            active.add(tid)
            x1, y1, x2, y2 = map(int, t.to_ltrb())
            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, str(tid), (x1, max(15, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

            per_tid = track_area_state.setdefault(tid, {})
            inside_area_for_heatmap = None

            for a in areas:
                aid = a["id"]
                rect = a["rect"]
                inside = point_in_rect(cx, cy, rect)
                st = per_tid.setdefault(aid, {"inside": False, "enter": None})

                if inside and not st["inside"]:
                    st["inside"] = True
                    st["enter"] = now
                    area_stats[aid]["current_ids"].add(tid)
                    log_event(time.strftime("%Y-%m-%d %H:%M:%S"), aid, "enter",
                              tid, len(area_stats[aid]["current_ids"]), 0)

                elif not inside and st["inside"]:
                    dwell = max(0, now - (st["enter"] or now))
                    st["inside"] = False
                    st["enter"] = None
                    if tid in area_stats[aid]["current_ids"]:
                        area_stats[aid]["current_ids"].remove(tid)
                    area_stats[aid]["total_dwell"] += dwell
                    n = len(area_stats[aid]["current_ids"])
                    area_stats[aid]["avg_dwell"] = area_stats[aid]["total_dwell"] / max(1, n + 1)
                    log_event(time.strftime("%Y-%m-%d %H:%M:%S"), aid, "exit",
                              tid, n, dwell)

                if inside and inside_area_for_heatmap is None:
                    inside_area_for_heatmap = a

            if db_logger and db_logger.enable_heatmap and (now - last_heatmap_flush) >= heatmap_interval:
                try:
                    db_area_id = None
                    if inside_area_for_heatmap and "db_id" in inside_area_for_heatmap:
                        db_area_id = inside_area_for_heatmap["db_id"]
                    db_logger.insert_heatmap_point(
                        time.strftime("%Y-%m-%d %H:%M:%S"), db_area_id, tid, cx, cy
                    )
                except Exception as e:
                    print(f"[DB] Error heatmap: {repr(e)}", file=sys.stderr)

        if db_logger and db_logger.enable_heatmap and (now - last_heatmap_flush) >= heatmap_interval:
            last_heatmap_flush = now

        vanished = [tid for tid in track_area_state if tid not in active]
        for tid in vanished:
            for aid, st in track_area_state[tid].items():
                if st["inside"]:
                    dwell = max(0, now - (st["enter"] or now))
                    st["inside"] = False
                    st["enter"] = None
                    if aid in area_stats and tid in area_stats[aid]["current_ids"]:
                        area_stats[aid]["current_ids"].remove(tid)
                        area_stats[aid]["total_dwell"] += dwell
                        log_event(time.strftime("%Y-%m-%d %H:%M:%S"), aid, "exit",
                                  tid, len(area_stats[aid]["current_ids"]), dwell)
            del track_area_state[tid]

        flush_log()

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)

        self.ctk_frame_image = ctk.CTkImage(
            light_image=img,
            dark_image=img,
            size=(disp_w, disp_h)
        )
        self.label_video.configure(image=self.ctk_frame_image)

        self.frame_count += 1
        t_now = time.time()
        if t_now - self.last_time >= 1.0:
            self.fps = self.frame_count / (t_now - self.last_time)
            self.lbl_fps.configure(text=f"FPS: {self.fps:.1f}")
            self.last_time = t_now
            self.frame_count = 0

        self.after(1, self.loop_video)

    def on_closing(self):
        print("[APP] Cerrando aplicación...")
        cap.release()
        cv2.destroyAllWindows()
        flush_log()
        if db_logger:
            try:
                db_logger.close()
            except Exception as e:
                print(f"[DB] Error al cerrar db_logger: {repr(e)}", file=sys.stderr)
        self.destroy()


if __name__ == "__main__":
    app = VisionApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
