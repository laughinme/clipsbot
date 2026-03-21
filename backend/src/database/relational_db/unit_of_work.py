from sqlalchemy.ext.asyncio import AsyncSession


class UoW:
    """Unit-of-Work: single transaction, single session."""
    def __init__(self, session: AsyncSession):
        self.session = session
        self._committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, *_):
        if exc_type is None and not self._committed:
            await self.session.commit()
        elif exc_type is not None:
            await self.session.rollback()

    async def commit(self):
        """Manually commit the current transaction and start a new one."""
        await self.session.commit()
        self._committed = True
        # Start a new transaction for any subsequent operations
        await self.session.begin()
        self._committed = False

    async def savepoint(self):
        """Create a savepoint for partial rollbacks."""
        return self.session.begin_nested()
