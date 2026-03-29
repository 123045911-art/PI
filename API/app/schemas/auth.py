from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)
    is_admin: bool = False


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    user: UserOut
    detail: str = (
        "Autenticación sin JWT por ahora; se puede añadir Bearer token en una iteración futura."
    )
