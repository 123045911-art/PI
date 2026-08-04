from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class AlertStore:
    def __init__(self, data_root: Path) -> None:
        self.path = data_root / "alerts.json"
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write(self, alerts: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list(self, site_id: str) -> list[dict]:
        with self.lock:
            return [dict(a) for a in self._read() if a.get("siteId") == site_id]

    def create(self, site_id: str, payload: dict) -> dict:
        required = ("areaId", "areaName", "type", "thresholdPeople")
        if any(payload.get(key) is None for key in required):
            raise ValueError("Faltan areaId, areaName, type o thresholdPeople.")
        if payload["type"] not in ("crowding", "low_flow"):
            raise ValueError("Tipo de alerta no compatible.")
        with self.lock:
            alerts = self._read()
            alert_id = str(payload.get("id") or f"alert-{uuid4().hex[:12]}")
            alert_type = str(payload["type"])
            threshold = max(1, int(payload["thresholdPeople"]))
            generated_reason = (
                f"Avisar cuando haya {threshold} personas o mas."
                if alert_type == "crowding"
                else f"Avisar cuando haya {threshold} personas o menos."
            )
            alert = {
                "id": alert_id,
                "siteId": site_id,
                "areaId": str(payload["areaId"]),
                "areaName": str(payload["areaName"]),
                "type": alert_type,
                "reason": str(payload.get("reason") or generated_reason),
                "status": str(payload.get("status") or "watching"),
                "thresholdPeople": threshold,
                "scheduleMode": str(payload.get("scheduleMode") or "all_days"),
                "scheduleDay": payload.get("scheduleDay"),
                "scheduleDate": payload.get("scheduleDate"),
                "peopleCountSnapshot": max(0, int(payload.get("peopleCountSnapshot", 0))),
                "createdBy": str(payload.get("createdBy") or "operador"),
                "createdAt": str(payload.get("createdAt") or datetime.now(timezone.utc).isoformat()),
            }
            alerts = [a for a in alerts if a.get("id") != alert_id]
            alerts.insert(0, alert)
            self._write(alerts[:200])
            return dict(alert)

    def update(self, site_id: str, alert_id: str, payload: dict) -> dict | None:
        with self.lock:
            alerts = self._read()
            alert = next((a for a in alerts if a.get("siteId") == site_id and a.get("id") == alert_id), None)
            if not alert:
                return None
            for key in ("areaId", "areaName", "type", "reason", "status", "thresholdPeople", "scheduleMode", "scheduleDay", "scheduleDate", "peopleCountSnapshot"):
                if key in payload:
                    alert[key] = payload[key]
            alert["thresholdPeople"] = max(1, int(alert["thresholdPeople"]))
            self._write(alerts)
            return dict(alert)

    def delete(self, site_id: str, alert_id: str) -> bool:
        with self.lock:
            alerts = self._read()
            remaining = [a for a in alerts if not (a.get("siteId") == site_id and a.get("id") == alert_id)]
            if len(remaining) == len(alerts):
                return False
            self._write(remaining)
            return True

    def delete_for_area(self, site_id: str, area_id: str) -> int:
        with self.lock:
            alerts = self._read()
            remaining = [a for a in alerts if not (a.get("siteId") == site_id and a.get("areaId") == area_id)]
            removed = len(alerts) - len(remaining)
            if removed:
                self._write(remaining)
            return removed

    def evaluate(self, site_id: str, counts: dict[str, int], now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        with self.lock:
            alerts = self._read()
            changed = False
            for alert in alerts:
                if alert.get("siteId") != site_id:
                    continue
                mode = alert.get("scheduleMode", "all_days")
                applies = mode == "all_days"
                if mode == "weekly":
                    applies = int(alert.get("scheduleDay", -1)) == now.weekday()
                elif mode == "date":
                    applies = alert.get("scheduleDate") == now.date().isoformat()
                count = int(counts.get(str(alert.get("areaId")), 0))
                threshold = int(alert.get("thresholdPeople", 1))
                met = count >= threshold if alert.get("type") == "crowding" else count <= threshold
                status = "triggered" if applies and met else "watching"
                if alert.get("status") != status or alert.get("peopleCountSnapshot") != count:
                    alert["status"] = status
                    alert["peopleCountSnapshot"] = count
                    changed = True
            if changed:
                self._write(alerts)
            return [dict(a) for a in alerts if a.get("siteId") == site_id]
