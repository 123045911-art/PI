from __future__ import annotations
import logging
import os
from typing import Any
import requests

logger = logging.getLogger("visioflow.api")

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = (3.0, 10.0)


def _env_base_url() -> str:
    raw = (
        os.getenv("VISIOFLOW_API_BASE_URL")
        or os.getenv("API_BASE_URL")
        or DEFAULT_BASE_URL
    )
    return raw.rstrip("/")


class VisioFlowApiClient:
    """Cliente reutilizable: áreas y eventos hacia FastAPI."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> None:
        self.base_url = (base_url or _env_base_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    def create_area(
        self,
        *,
        name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        is_admin: bool = False,
    ) -> dict[str, Any] | None:
        """
        POST /areas. Devuelve el JSON del área creado (incluye id de PostgreSQL) o None si falla.
        """
        url = f"{self.base_url}/areas"
        headers = {"X-Is-Admin": str(is_admin).lower()}
        payload = {
            "name": name,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if 200 <= response.status_code < 300:
                data = response.json()
                rid = data.get("id")
                logger.info(
                    "Área creada en FastAPI: api_id=%s name=%s",
                    rid,
                    name,
                )
                return data
            logger.warning(
                "FastAPI /areas respondió %s: %s | payload=%s",
                response.status_code,
                (response.text or "")[:400],
                payload,
            )
            return None
        except requests.RequestException as exc:
            logger.warning(
                "Error de red llamando a FastAPI /areas: %s | url=%s",
                exc,
                url,
            )
            return None

    def post_event(
        self,
        *,
        area_id: int,
        track_id: int,
        event: str,
        timestamp_iso: str,
        dwell: float = 0.0,
    ) -> bool:
        """
        POST /events.
        area_id debe ser el ID de PostgreSQL (api_id), no el id local del tracker.
        """
        return self.send_event(
            area_id=area_id,
            track_id=track_id,
            event=event,
            timestamp_iso=timestamp_iso,
            dwell=dwell,
        )

    def send_event(
        self,
        *,
        area_id: int,
        track_id: int,
        event: str,
        timestamp_iso: str,
        dwell: float = 0.0,
    ) -> bool:
        """
        Envía un evento a POST /events.
        Devuelve True si la API respondió 2xx; False en cualquier otro caso.
        """
        url = f"{self.base_url}/events"
        payload: dict[str, Any] = {
            "area_id": area_id,
            "track_id": track_id,
            "event": event,
            "timestamp": timestamp_iso,
            "dwell": float(dwell),
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if 200 <= response.status_code < 300:
                logger.info(
                    "Evento enviado a FastAPI: area_id=%s track_id=%s event=%s",
                    area_id,
                    track_id,
                    event,
                )
                return True
            logger.warning(
                "FastAPI /events respondió %s: %s | payload=%s",
                response.status_code,
                (response.text or "")[:400],
                payload,
            )
            return False
        except requests.RequestException as exc:
            logger.warning(
                "Error de red llamando a FastAPI /events: %s | url=%s payload=%s",
                exc,
                url,
                payload,
            )
            return False
    def login(self, username: str, password: str) -> dict[str, Any] | None:
        """POST /auth/login. Devuelve el JSON de LoginResponse o None."""
        url = f"{self.base_url}/auth/login"
        payload = {"username": username, "password": password}
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def list_users(self, name_filter: str | None = None, is_admin: bool = False) -> list[dict[str, Any]]:
        """GET /users."""
        url = f"{self.base_url}/users"
        params = {"name": name_filter} if name_filter else {}
        headers = {"X-Is-Admin": str(is_admin).lower()}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.RequestException:
            return []

    def get_user(self, user_id: int, current_user_is_admin: bool = False) -> dict[str, Any] | None:
        """GET /users/{id}."""
        url = f"{self.base_url}/users/{user_id}"
        headers = {"X-Is-Admin": str(current_user_is_admin).lower()}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def register_user(self, username: str, password: str, is_admin_val: bool = False, current_user_is_admin: bool = False) -> dict[str, Any] | None:
        """POST /users/."""
        url = f"{self.base_url}/users/"
        payload = {"username": username, "password": password, "is_admin": is_admin_val}
        headers = {"X-Is-Admin": str(current_user_is_admin).lower()}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if response.status_code == 201:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def update_user(self, user_id: int, username: str, password: str | None = None, is_admin_val: bool = False, current_user_is_admin: bool = False) -> bool:
        """PUT /users/{id}."""
        url = f"{self.base_url}/users/{user_id}"
        payload = {"username": username, "is_admin": is_admin_val}
        headers = {"X-Is-Admin": str(current_user_is_admin).lower()}
        if password:
            payload["password"] = password
        try:
            response = requests.put(url, json=payload, headers=headers, timeout=self.timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def patch_user(self, user_id: int, **kwargs) -> bool:
        """PATCH /users/{id}."""
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = requests.patch(url, json=kwargs, timeout=self.timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def delete_user(self, user_id: int, current_user_is_admin: bool = False) -> bool:
        """DELETE /users/{id}."""
        url = f"{self.base_url}/users/{user_id}"
        headers = {"X-Is-Admin": str(current_user_is_admin).lower()}
        try:
            response = requests.delete(url, headers=headers, timeout=self.timeout)
            return response.status_code == 204
        except requests.RequestException:
            return False
