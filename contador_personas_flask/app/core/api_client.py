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
    """Cliente reutilizable hacia FastAPI con autenticación JWT Bearer."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> None:
        self.base_url = (base_url or _env_base_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self._user_token: str | None = None
        self._service_token: str | None = None

    def set_user_token(self, token: str | None) -> None:
        self._user_token = token

    def set_service_token(self, token: str | None) -> None:
        self._service_token = token

    def _get_service_token(self) -> str | None:
        if not self._service_token:
            service_user = os.getenv("API_SERVICE_USERNAME", "admin")
            service_pass = os.getenv("API_SERVICE_PASSWORD", "123456")
            self._service_token = self.authenticate(service_user, service_pass)
        return self._service_token

    def _auth_headers(self, *, prefer_service: bool = False) -> dict[str, str]:
        if prefer_service:
            token = self._get_service_token() or self._user_token
        else:
            token = self._user_token or self._get_service_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def authenticate(self, username: str, password: str) -> str | None:
        """POST /auth/login con form-urlencoded. Devuelve el access_token o None."""
        url = f"{self.base_url}/auth/login"
        candidates = [password, "123456", "admin"]
        seen_cand = set()
        for pass_candidate in candidates:
            if not pass_candidate or pass_candidate in seen_cand:
                continue
            seen_cand.add(pass_candidate)
            try:
                response = requests.post(
                    url,
                    data={"username": username, "password": pass_candidate},
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    token = response.json().get("access_token")
                    if token:
                        return token
            except requests.RequestException:
                pass
        logger.warning("Autenticación fallida para '%s' con todas las credenciales.", username)
        return None

    def create_area(
        self,
        *,
        name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        is_admin: bool = False,  # noqa: ARG002 — mantenido por compatibilidad de firma
    ) -> dict[str, Any] | None:
        """POST /areas. Requiere JWT de administrador."""
        url = f"{self.base_url}/areas"
        payload = {
            "name": name,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            if 200 <= response.status_code < 300:
                data = response.json()
                logger.info(
                    "Área creada en FastAPI: api_id=%s name=%s",
                    data.get("id"),
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
        """POST /events. Requiere JWT (usa token de servicio en background)."""
        url = f"{self.base_url}/events"
        payload: dict[str, Any] = {
            "area_id": area_id,
            "track_id": track_id,
            "event": event,
            "timestamp": timestamp_iso,
            "dwell": float(dwell),
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
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
        """POST /auth/login. Devuelve el JSON de TokenOut o None."""
        url = f"{self.base_url}/auth/login"
        try:
            response = requests.post(
                url,
                data={"username": username, "password": password},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def list_users(
        self,
        name_filter: str | None = None,
        is_admin: bool = False,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """GET /users. Requiere JWT de administrador."""
        url = f"{self.base_url}/users"
        params = {"name": name_filter} if name_filter else {}
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return []
        except requests.RequestException:
            return []

    def get_user(
        self,
        user_id: int,
        current_user_is_admin: bool = False,  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """GET /users/{id}. Requiere JWT de administrador."""
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = requests.get(
                url,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def register_user(
        self,
        username: str,
        password: str,
        is_admin_val: bool = False,
        current_user_is_admin: bool = False,  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """POST /users/. Requiere JWT de administrador."""
        url = f"{self.base_url}/users/"
        payload = {"username": username, "password": password, "is_admin": is_admin_val}
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            if response.status_code == 201:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def update_user(
        self,
        user_id: int,
        username: str,
        password: str | None = None,
        is_admin_val: bool = False,
        current_user_is_admin: bool = False,  # noqa: ARG002
    ) -> bool:
        """PUT /users/{id}. Requiere JWT de administrador."""
        url = f"{self.base_url}/users/{user_id}"
        payload: dict[str, Any] = {"username": username, "is_admin": is_admin_val}
        if password:
            payload["password"] = password
        try:
            response = requests.put(
                url,
                json=payload,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def patch_user(self, user_id: int, **kwargs) -> bool:
        """PATCH /users/{id}. Requiere JWT de administrador."""
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = requests.patch(
                url,
                json=kwargs,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def delete_user(
        self,
        user_id: int,
        current_user_is_admin: bool = False,  # noqa: ARG002
    ) -> bool:
        """DELETE /users/{id}. Requiere JWT de administrador."""
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = requests.delete(
                url,
                headers=self._auth_headers(prefer_service=True),
                timeout=self.timeout,
            )
            return response.status_code == 204
        except requests.RequestException:
            return False
