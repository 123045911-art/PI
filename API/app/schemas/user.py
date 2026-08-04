from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import validated_password, validated_username


def optional_username(value: str | None) -> str | None:
    return validated_username(value) if value is not None else None


def optional_password(value: str | None) -> str | None:
    return validated_password(value) if value is not None else None


class UserUpdate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str | None = Field(None, min_length=8, max_length=255)
    is_admin: bool = False

    _username = field_validator("username")(validated_username)
    _password = field_validator("password")(optional_password)


class UserPatch(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=8, max_length=255)
    is_admin: bool | None = None

    _username = field_validator("username")(optional_username)
    _password = field_validator("password")(optional_password)
