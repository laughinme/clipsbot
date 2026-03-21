from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, SerializerFunctionWrapHandler, model_serializer


def reorder_timestamp_fields(data: dict) -> dict:
    reordered = {k: v for k, v in data.items() if k not in ("created_at", "updated_at",)}
    for key in ("created_at", "updated_at",):
        if key in data:
            reordered[key] = data[key]
    return reordered


def move_timestamps_to_bottom(schema: dict) -> None:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return

    schema["properties"] = reorder_timestamp_fields(props)


class CreatedAtModel(BaseModel):
    model_config = ConfigDict(json_schema_extra=move_timestamps_to_bottom)

    created_at: datetime = Field(...)
    
    @model_serializer(mode="wrap")
    def reorder_timestamps(
        self,
        handler: SerializerFunctionWrapHandler,
    ):
        serialized = handler(self)
        if isinstance(serialized, dict):
            return reorder_timestamp_fields(serialized)
        return serialized


class TimestampModel(CreatedAtModel):
    updated_at: datetime = Field(...)
