from pydantic import BaseModel, Field, field_validator
import re


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=50,
                          description="Entre 1 y 50 caracteres")
    password: str = Field(..., min_length=1, max_length=255,
                          description="Mínimo 1 caracter")
    is_admin: bool = False


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    """Respuesta del endpoint /auth/login con JWT Bearer token."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginResponse(BaseModel):
    """Mantenido por compatibilidad; el flujo principal usa TokenOut."""
    user: UserOut
    detail: str = "Usa /auth/login para obtener un Bearer token JWT."
