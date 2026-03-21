from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel

class Base(DeclarativeBase):
    def __repr__(self):
        cls_name = self.__class__.__name__
        column_names = self.__mapper__.columns.keys()
        
        values = ', '.join(f"{name}={getattr(self, name)!r}" for name in column_names)
        return f"<{cls_name}({values})>"
    
    
    # TODO: Add automatic pydantic schema generation
    
    # @classmethod
    # def pydantic_model(cls) -> type[BaseModel]:
    #     if hasattr(cls, "_pydantic_model"):
    #         return cls._pydantic_model

    #     fields: dict[str, tuple[type, object]] = {}
    #     for col in cls.__table__.columns:
    #         python_type = col.type.python_type
    #         default = ...
    #         if col.nullable or col.default is not None:
    #             python_type = python_type | None
    #             default = None if col.nullable else (
    #                 col.default.arg() if callable(col.default.arg) else col.default.arg
    #             )
    #         fields[col.name] = (python_type, default)
    
    
    # def __init_subclass__(cls, **kwargs):
    #     super().__init_subclass__(**kwargs)
    #     if hasattr(cls, "__table__"):
    #         cls.Schema = cls.pydantic_model()
