from typing_extensions import Self
from pydantic import BaseModel, Field, EmailStr, model_validator


class UserRegister(BaseModel):
    """Data required for user registration."""

    email: EmailStr = Field(..., description="User e-mail")
    password: str = Field(..., description="User password")
    
    username: str | None = Field(None, description="User's display name")
    

class UserLogin(BaseModel):
    """Credentials used for user login."""

    email: EmailStr = Field(..., description="User e-mail")
    password: str = Field(..., description='User password')
