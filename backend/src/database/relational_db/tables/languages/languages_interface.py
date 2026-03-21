from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from .languages_table import Language


class LanguagesInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, search: str, limit: int) -> list[Language]:
        stmt = select(Language)

        if search:
            stmt = (
                stmt.where(
                    or_(
                        Language.name_ru.ilike(f"%{search}%"),
                        Language.name_en.ilike(f"%{search}%"),
                    )
                )
                .order_by(func.char_length(Language.name_ru))
            )

        stmt = stmt.limit(limit)

        languages = await self.session.scalars(stmt)
        return list(languages.all())
