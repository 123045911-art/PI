from fastapi import APIRouter, Depends, status, Query, Header, HTTPException
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.auth import UserOut, UserRegister
from app.schemas.user import UserUpdate, UserPatch
from app.services import user_service, auth_service
from app.security.auth import verify_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_user(payload: UserRegister, db: Session = Depends(get_db)):
    # Reutilizamos el servicio de registro para mantener consistencia (hash de contraseña, etc.)
    return auth_service.register_user(db, payload)


@router.get("/", response_model=list[UserOut], dependencies=[Depends(verify_admin)])
def list_users(
    username: str | None = Query(None, alias="name"), 
    db: Session = Depends(get_db)
):
    """Consultar todos o filtrar por nombre."""
    return user_service.list_users(db, username)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(verify_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)):
    return user_service.get_user(db, user_id)


@router.put("/{user_id}", response_model=UserOut, dependencies=[Depends(verify_admin)])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    """Editar todo (username, password, is_admin)."""
    return user_service.update_user(db, user_id, payload)


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(verify_admin)])
def patch_user(user_id: int, payload: UserPatch, db: Session = Depends(get_db)):
    """Edición parcial."""
    return user_service.patch_user(db, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user_service.delete_user(db, user_id)
