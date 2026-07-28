from pydantic import BaseModel, Field, field_validator
import re


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50,
                          description="Entre 3 y 50 caracteres")
    password: str = Field(..., min_length=8, max_length=255,
                          description="Mínimo 8 caracteres")
    is_admin: bool = False

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Valida que la contraseña tenga al menos una letra y un número."""
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("La contraseña debe contener al menos una letra.")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número.")
        return v


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
