from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import Settings, get_settings
from database.relational_db import RolesInterface, User, UserInterface, get_session_factory


logger = logging.getLogger(__name__)

SEED_LOCK_KEY = 0x434C495053  # "CLIPS"


@dataclass(slots=True)
class SeedStepResult:
    name: str
    changed: bool = False
    details: str | None = None


class StartupSeedStep:
    name = "unnamed"

    async def run(self, session: AsyncSession, settings: Settings) -> SeedStepResult:
        raise NotImplementedError


class BootstrapAdminSeedStep(StartupSeedStep):
    name = "bootstrap_admin_roles"

    async def run(self, session: AsyncSession, settings: Settings) -> SeedStepResult:
        admin_ids = settings.bootstrap_admin_telegram_ids
        if not admin_ids:
            return SeedStepResult(
                name=self.name,
                changed=False,
                details="No bootstrap admin Telegram IDs configured.",
            )

        role_repo = RolesInterface(session)
        user_repo = UserInterface(session)

        admin_role = await role_repo.get_by_slug("admin")
        if admin_role is None:
            raise RuntimeError("Required role 'admin' is missing. Run migrations before seeding.")

        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.telegram_id.in_(admin_ids))
        )
        users = list(await session.scalars(stmt))

        changed = False
        assigned_count = 0
        present_ids: set[int] = set()

        for user in users:
            if user.telegram_id is None:
                continue

            present_ids.add(int(user.telegram_id))
            existing_slugs = set(user.role_slugs)
            if "admin" in existing_slugs:
                continue

            next_roles = list(user.roles) + [admin_role]
            await user_repo.assign_roles(user, next_roles)
            user.bump_auth_version()
            changed = True
            assigned_count += 1

        missing_ids = sorted(set(admin_ids) - present_ids)
        if missing_ids:
            logger.info(
                "Bootstrap admin Telegram IDs are configured but not present in users yet: %s",
                ",".join(map(str, missing_ids)),
            )

        if assigned_count:
            details = f"Assigned admin role to {assigned_count} bootstrap user(s)."
        elif missing_ids:
            details = "No matching users found yet for configured bootstrap admin Telegram IDs."
        else:
            details = "Bootstrap admin roles already up to date."

        return SeedStepResult(name=self.name, changed=changed, details=details)


class StartupSeedRunner:
    def __init__(self, settings: Settings, steps: list[StartupSeedStep] | None = None) -> None:
        self.settings = settings
        self.steps = steps or [BootstrapAdminSeedStep()]

    async def run(self) -> list[SeedStepResult]:
        session_factory = get_session_factory(self.settings)

        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_key)"),
                    {"lock_key": SEED_LOCK_KEY},
                )

                results: list[SeedStepResult] = []
                for step in self.steps:
                    result = await step.run(session, self.settings)
                    results.append(result)

        changed_steps = [result.name for result in results if result.changed]
        if changed_steps:
            logger.info("Startup seeders applied changes: %s", ", ".join(changed_steps))
        else:
            logger.info("Startup seeders completed without changes.")

        for result in results:
            if result.details:
                logger.info("Seeder '%s': %s", result.name, result.details)

        return results


async def run_startup_seeders(settings: Settings) -> list[SeedStepResult]:
    runner = StartupSeedRunner(settings)
    return await runner.run()


def main() -> None:
    settings = get_settings()
    from core.config import configure_logging

    configure_logging(settings)
    asyncio.run(run_startup_seeders(settings))


if __name__ == "__main__":
    main()
