from typing import Generic, TypeVar, Any, Self
from pydantic import BaseModel, Field, TypeAdapter

T = TypeVar('T')

class CursorPage(BaseModel, Generic[T]):
    items: list[T] = Field(...)
    next_cursor: str | None = Field(None)

    # @classmethod
    # def from_list(cls, items: list[Any], next_cursor: str | None) -> Self:
    #     adapter = TypeAdapter(cls)
    #     return adapter.validate_python(
    #         {'items': items, 'next_cursor': next_cursor},
    #         from_attributes=True,
    #     )
