"""
Módulo de manejo JWT para Visio Flow API.
- Crea access_tokens firmados con HS256.
- Verifica y decodifica tokens en cada request.
- El secret se lee desde variable de entorno JWT_SECRET_KEY.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

# ── Configuración ──────────────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("JWT_EXPIRE_MINUTES", "60")
)

if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY no está definida. "
        "Añade JWT_SECRET_KEY en tu archivo .env antes de iniciar la API."
    )

# ── Creación ───────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    is_admin: bool = False,
    expires_delta: timedelta | None = None,
) -> str:
    """Genera un JWT firmado con el user id (sub) y rol admin."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "is_admin": is_admin,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Verificación ───────────────────────────────────────────────────────────────

def decode_access_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza HTTPException si es inválido/expirado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
