import re

from pydantic import BaseModel, Field, field_validator


def validated_username(value: str) -> str:
    value = value.strip()
    if len(value) < 3:
        raise ValueError("El usuario debe tener entre 3 y 50 caracteres.")
    return value


def validated_password(value: str) -> str:
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("La contraseña debe tener al menos 8 caracteres, una letra y un número.")
    return value


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=255)
    is_admin: bool = False

    _username = field_validator("username")(validated_username)
    _password = field_validator("password")(validated_password)


class UserLogin(BaseModel):
    # El login mantiene compatibilidad con la cuenta demo existente.
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginResponse(BaseModel):
    user: UserOut
    detail: str = "Usa /auth/login para obtener un Bearer token JWT."
