from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister
from app.security.hash import hash_password, verify_password


def register_user(db: Session, data: UserRegister) -> User:
    user = User(
        username=data.username.strip(),
        password=hash_password(data.password),
        is_admin=data.is_admin,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está registrado.",
        ) from None
    db.refresh(user)
    return user


def login_user(db: Session, data: UserLogin) -> User:
    user = db.query(User).filter(User.username == data.username.strip()).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )
    return user
