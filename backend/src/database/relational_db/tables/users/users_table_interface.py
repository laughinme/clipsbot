from uuid import UUID
from datetime import UTC, datetime, timedelta
from sqlalchemy import select, and_, or_, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .users_table import User
from ..roles import Role, UserRole


class UserInterface:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, user: User) -> User:
        self.session.add(user)
        return user
    
    async def get_by_id(self, id: UUID | str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == id)
        )
        user = await self.session.scalar(stmt)
        
        return user
    
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(
            select(User)
            .options(selectinload(User.roles))
            .where(User.telegram_id == telegram_id)
        )

    async def admin_list_users(
        self,
        *,
        banned: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> list[User]:
        stmt = select(User).options(
            selectinload(User.roles)
        )

        if banned is not None:
            stmt = stmt.where(User.banned == banned)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(pattern),
                    User.telegram_username.ilike(pattern),
                )
            )

        # Cursor pagination (created_at desc, id desc)
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    User.created_at < cursor_created_at,
                    and_(User.created_at == cursor_created_at, User.id < cursor_id),
                )
            )

        stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit)

        rows = await self.session.scalars(stmt)
        return list(rows.all())

    async def assign_roles(self, user: User, roles: list[Role]) -> User:
        await self.session.execute(
            delete(UserRole).where(UserRole.user_id == user.id)
        )
        
        if roles:
            role_data = [
                {"user_id": user.id, "role_id": role.id} 
                for role in roles
            ]
            await self.session.execute(
                insert(UserRole).values(role_data)
            )
        
        await self.session.flush()
        return user

    async def registrations_by_days(self, days: int):
        day = func.date_trunc('day', User.created_at)
        result = await self.session.execute(
            select(
                day.label('day'),
                func.count(func.distinct(User.id)).label('count')
            )
            .group_by(day)
            .order_by(day)
            .where(User.created_at >= datetime.now(UTC) - timedelta(days=days))
        )
        
        return result.mappings().all()

    async def count_users(
        self,
        *,
        banned: bool | None = None,
    ) -> int:
        stmt = select(func.count(User.id))
        if banned is not None:
            stmt = stmt.where(User.banned == banned)

        result = await self.session.scalar(stmt)
        return int(result or 0)

    async def count_registered_since(self, since: datetime) -> int:
        stmt = (
            select(func.count(User.id))
            .where(User.created_at >= since)
        )
        result = await self.session.scalar(stmt)
        return int(result or 0)
