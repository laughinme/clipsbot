from pydantic import BaseModel, Field


class LanguageModel(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    name_ru: str = Field(...)
    name_en: str = Field(...)
