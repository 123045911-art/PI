from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.auth import LoginResponse, TokenOut, UserOut, UserRegister
from app.security.auth import require_admin
from app.security.jwt_handler import create_access_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201,
             dependencies=[Depends(require_admin)],
             summary="Crear nuevo usuario (solo admin)")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Registra un usuario nuevo. Requiere token JWT de administrador."""
    user = auth_service.register_user(db, payload)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut,
             summary="Autenticación — retorna JWT Bearer token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica con username/password y retorna un JWT access_token.
    Usar el token en el header: Authorization: Bearer <token>
    """
    from app.schemas.auth import UserLogin
    user = auth_service.login_user(db, UserLogin(
        username=form_data.username,
        password=form_data.password,
    ))
    token = create_access_token(subject=user.id, is_admin=user.is_admin)
    return TokenOut(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )
