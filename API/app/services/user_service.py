from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.schemas.user import UserUpdate, UserPatch
from app.security.hash import hash_password


def list_users(db: Session, username: str | None = None) -> list[User]:
    query = db.query(User)
    if username:
        query = query.filter(User.username.ilike(f"%{username}%"))
    return query.all()


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con id {user_id} no encontrado."
        )
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    
    user.username = data.username.strip()
    if data.password:
        user.password = hash_password(data.password)
    user.is_admin = data.is_admin
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso."
        ) from None
    
    db.refresh(user)
    return user


def patch_user(db: Session, user_id: int, data: UserPatch) -> User:
    user = get_user(db, user_id)
    
    if data.username is not None:
        user.username = data.username.strip()
    if data.password is not None:
        user.password = hash_password(data.password)
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso."
        ) from None
    
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    db.delete(user)
    db.commit()
