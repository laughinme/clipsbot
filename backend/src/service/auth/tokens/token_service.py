import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import jwt

from core.config import Settings
from database.redis import CacheRepo
from database.relational_db import User, UserInterface

config = Settings()  # pyright: ignore[reportCallIssue]
logger = logging.getLogger(__name__)
PRIVATE_KEY = config.JWT_PRIVATE_KEY.encode()
PUBLIC_KEY = config.JWT_PUBLIC_KEY.encode()


class TokenService:
    def __init__(self, repo: CacheRepo, user_repo: UserInterface):
        self.repo = repo
        self.user_repo = user_repo

    @staticmethod
    def _make_csrf(refresh_token: str) -> str:
        return hmac.new(
            config.CSRF_HMAC_KEY, refresh_token.encode(), "sha256"
        ).hexdigest()

    async def _verify_token(self, token: str) -> dict[str, int | str] | None:
        try:
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=[config.JWT_ALGO])
        except jwt.PyJWTError:
            logger.info("Failed to decode jwt")
            return None

        jti = payload["jti"]
        if await self.repo.exists(f"block:{jti}"):
            logger.info("Failed to verify JWT: this token is blocked")
            return None

        return payload

    async def issue_tokens(
        self,
        user: User,
        src: Literal["web", "mobile"] = "web",
    ) -> tuple[str, str, str]:
        user_id = str(user.id)
        now = datetime.now(UTC)
        version = int(user.auth_version)

        jti = uuid4().hex
        access_payload = {
            "sub": user_id,
            "jti": jti,
            "typ": "access",
            "src": src,
            "av": version,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=config.ACCESS_TTL)).timestamp()),
        }
        access = jwt.encode(access_payload, PRIVATE_KEY, algorithm=config.JWT_ALGO)

        refresh_payload = {
            "sub": user_id,
            "jti": jti,
            "typ": "refresh",
            "src": src,
            "av": version,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=config.REFRESH_TTL)).timestamp()),
        }
        refresh = jwt.encode(refresh_payload, PRIVATE_KEY, algorithm=config.JWT_ALGO)

        csrf = self._make_csrf(refresh)

        return access, refresh, csrf

    async def refresh_tokens(
        self,
        refresh_token: str,
        csrf: str | None = None,
    ) -> tuple[str, str, str] | None:
        payload = await self._verify_token(refresh_token)
        if payload is None or payload["typ"] != "refresh":
            return None

        src = payload["src"]

        if src == "web":
            if csrf is None or not hmac.compare_digest(
                self._make_csrf(refresh_token), csrf
            ):
                return None
        elif src != "mobile":
            return None

        jti = payload["jti"]
        ttl = int(payload["exp"]) - int(datetime.now(UTC).timestamp())
        await self.repo.set(f"block:{jti}", "1", ttl)

        user_id = payload["sub"]
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            logger.info("Failed to refresh JWT: user %s not found", user_id)
            return None

        token_version = int(payload.get("av", 0))
        if token_version != int(user.auth_version):
            logger.info(
                "Refreshing JWT with bumped auth version for user %s",
                user_id,
            )

        return await self.issue_tokens(user, src)

    async def revoke(self, refresh_token: str) -> dict[str, int | str] | None:
        payload = await self._verify_token(refresh_token)
        if payload is None or payload["typ"] != "refresh":
            return None

        ttl = int(payload["exp"]) - int(datetime.now(UTC).timestamp())
        await self.repo.set(f"block:{payload['jti']}", "1", ttl)

        return payload

    async def verify_access(self, access_token: str) -> dict[str, int | str] | None:
        payload = await self._verify_token(access_token)
        if payload is None or payload["typ"] != "access":
            logger.info('Failed to verify JWT: no payload or type is not "access"')
            return None

        return payload
