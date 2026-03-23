from datetime import UTC, date, datetime, timedelta

from database.relational_db import UoW, UserInterface
from domain.statistics import RegistrationsGraph, UserStatsSummary


class StatService:
    def __init__(
        self,
        uow: UoW,
        user_repo: UserInterface,
    ):
        self.uow = uow
        self.user_repo = user_repo

    async def users_summary(self) -> UserStatsSummary:
        now = datetime.now(UTC)
        since_24h = now - timedelta(hours=24)

        total_users = await self.user_repo.count_users()
        banned_users = await self.user_repo.count_users(banned=True)
        registered_last_24h = await self.user_repo.count_registered_since(since_24h)

        return UserStatsSummary(
            generated_at=now,
            total_users=total_users,
            banned_users=banned_users,
            registered_last_24h=registered_last_24h,
        )

    async def new_registrations(self, days: int) -> list[RegistrationsGraph]:
        raw_rows = await self.user_repo.registrations_by_days(days)

        graphs: list[RegistrationsGraph] = []
        for row in raw_rows:
            raw_day = row.get("day")
            if isinstance(raw_day, datetime):
                normalized_day = raw_day.date()
            elif isinstance(raw_day, date):
                normalized_day = raw_day
            else:
                normalized_day = date.fromisoformat(str(raw_day))

            graphs.append(
                RegistrationsGraph(
                    day=normalized_day,
                    count=int(row.get("count", 0)),
                )
            )

        return graphs
