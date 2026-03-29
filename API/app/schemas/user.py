from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str | None = Field(None, min_length=1, max_length=255)
    is_admin: bool = False


class UserPatch(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=1, max_length=255)
    is_admin: bool | None = None
