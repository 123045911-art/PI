import os
from typing import Any, Optional


class MySQLLogger:
    def __init__(self) -> None:
        self.enabled = os.getenv("MYSQL_ENABLED", "0") == "1"
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "contador_personas")
        self.conn = None

        try:
            import mysql.connector  # type: ignore

            self.mysql_connector = mysql.connector
        except Exception:
            self.mysql_connector = None
            if self.enabled:
                print("[WARN] mysql-connector-python no disponible. Se usara solo CSV.")

        if self.enabled:
            self.connect()

    def connect(self) -> None:
        if not self.enabled or self.mysql_connector is None:
            return

        try:
            self.conn = self.mysql_connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True,
            )
            print("[INFO] Conexion MySQL establecida.")
        except Exception as exc:
            self.conn = None
            print(f"[WARN] No se pudo conectar a MySQL: {exc}. Se continua con CSV.")

    def _cursor(self) -> Optional[Any]:
        if not self.enabled:
            return None
        if self.conn is None:
            self.connect()
        if self.conn is None:
            return None
        try:
            return self.conn.cursor()
        except Exception as exc:
            print(f"[WARN] Error creando cursor MySQL: {exc}")
            self.conn = None
            return None

    def insert_area(self, area: dict) -> None:
        cursor = self._cursor()
        if cursor is None:
            return
        try:
            cursor.execute(
                """
                INSERT INTO areas (id, name, x1, y1, x2, y2, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    x1 = VALUES(x1),
                    y1 = VALUES(y1),
                    x2 = VALUES(x2),
                    y2 = VALUES(y2)
                """,
                (
                    area["id"],
                    area["name"],
                    area["x1"],
                    area["y1"],
                    area["x2"],
                    area["y2"],
                ),
            )
            cursor.close()
        except Exception as exc:
            print(f"[WARN] Error insertando area en MySQL: {exc}")
            self.conn = None

    def insert_event(self, event: dict) -> None:
        cursor = self._cursor()
        if cursor is None:
            return
        try:
            cursor.execute(
                """
                INSERT INTO area_events
                (track_id, area_id, area_name, event_type, event_time, dwell_seconds)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event["track_id"],
                    event["area_id"],
                    event["area_name"],
                    event["event_type"],
                    event["event_time"],
                    event["dwell_seconds"],
                ),
            )
            cursor.close()
        except Exception as exc:
            print(f"[WARN] Error insertando evento en MySQL: {exc}")
            self.conn = None

    def upsert_area_status(self, area: dict) -> None:
        cursor = self._cursor()
        if cursor is None:
            return
        try:
            cursor.execute(
                """
                INSERT INTO area_status
                (area_id, area_name, current_count, total_entries, total_exits, total_dwell_seconds, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    area_name = VALUES(area_name),
                    current_count = VALUES(current_count),
                    total_entries = VALUES(total_entries),
                    total_exits = VALUES(total_exits),
                    total_dwell_seconds = VALUES(total_dwell_seconds),
                    updated_at = NOW()
                """,
                (
                    area["id"],
                    area["name"],
                    area["current_count"],
                    area["total_entries"],
                    area["total_exits"],
                    area["total_dwell_seconds"],
                ),
            )
            cursor.close()
        except Exception as exc:
            print(f"[WARN] Error actualizando estado de area en MySQL: {exc}")
            self.conn = None
