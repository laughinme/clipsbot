from datetime import date
from pydantic import BaseModel, Field

class ActiveUsersGraph(BaseModel):
    day: date = Field(...)
    count: int = Field(...)

class RegistrationsGraph(BaseModel):
    day: date = Field(...)
    count: int = Field(...)
