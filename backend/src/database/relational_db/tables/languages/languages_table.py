from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Index

from ..table_base import Base


class Language(Base):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    
    __table_args__ = (
        # GIN trigram indexes for fast text search
        Index(
            'languages_name_ru_trgm',
            'name_ru',
            postgresql_using='gin',
            postgresql_ops={'name_ru': 'gin_trgm_ops'}
        ),
        Index(
            'languages_name_en_trgm',
            'name_en',
            postgresql_using='gin',
            postgresql_ops={'name_en': 'gin_trgm_ops'}
        ),
    )
