from __future__ import annotations

import json
import threading
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


class LocalUserStore:
    """Usuarios persistentes para la demostracion sin el servidor central."""

    def __init__(self, data_root: Path) -> None:
        self.path = data_root / "users.json"
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

    def _write(self, users: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    @staticmethod
    def _public(user: dict) -> dict:
        return {
            "id": int(user["id"]),
            "username": str(user["username"]),
            "is_admin": bool(user.get("is_admin", False)),
        }

    def list(self, name_filter: str | None = None) -> list[dict]:
        with self.lock:
            users = self._read()
            if name_filter:
                needle = name_filter.casefold()
                users = [u for u in users if needle in str(u["username"]).casefold()]
            return [self._public(user) for user in users]

    def get(self, user_id: int) -> dict | None:
        with self.lock:
            user = next((u for u in self._read() if int(u["id"]) == user_id), None)
            return self._public(user) if user else None

    def create(self, username: str, password: str, is_admin: bool) -> dict | None:
        username = (username or "").strip()
        if not username or not password:
            return None
        with self.lock:
            users = self._read()
            if any(str(u["username"]).casefold() == username.casefold() for u in users):
                return None
            user = {
                "id": max((int(u["id"]) for u in users), default=0) + 1,
                "username": username,
                "password_hash": generate_password_hash(password),
                "is_admin": bool(is_admin),
            }
            users.append(user)
            self._write(users)
            return self._public(user)

    def update(
        self, user_id: int, username: str, password: str | None, is_admin: bool
    ) -> bool:
        username = (username or "").strip()
        if not username:
            return False
        with self.lock:
            users = self._read()
            user = next((u for u in users if int(u["id"]) == user_id), None)
            if not user or any(
                int(u["id"]) != user_id
                and str(u["username"]).casefold() == username.casefold()
                for u in users
            ):
                return False
            user["username"] = username
            user["is_admin"] = bool(is_admin)
            if password:
                user["password_hash"] = generate_password_hash(password)
            self._write(users)
            return True

    def delete(self, user_id: int) -> bool:
        with self.lock:
            users = self._read()
            remaining = [u for u in users if int(u["id"]) != user_id]
            if len(remaining) == len(users):
                return False
            self._write(remaining)
            return True

    def authenticate(self, username: str, password: str) -> dict | None:
        with self.lock:
            user = next(
                (
                    u
                    for u in self._read()
                    if str(u["username"]).casefold() == (username or "").casefold()
                ),
                None,
            )
            if not user or not check_password_hash(user["password_hash"], password or ""):
                return None
            return self._public(user)
