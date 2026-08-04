from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.models.user import User
from app.security.jwt_handler import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Requiere JWT válido y un usuario que todavía exista en PostgreSQL."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = decode_access_token(token)
    try:
        user_id = int(token_data["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de usuario inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ya no corresponde a un usuario activo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def verify_admin(current_user: User = Depends(get_current_user)) -> User:
    """Comprueba el rol administrador actual almacenado en PostgreSQL."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: solo para administradores.",
        )
    return current_user


require_admin = verify_admin
