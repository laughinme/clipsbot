from typing import Literal
from sqlalchemy.exc import IntegrityError

from database.relational_db import (
    RolesInterface,
    UserInterface,
    User,
    UoW,
)
from domain.auth import UserRegister, UserLogin
from domain.auth.enums import DEFAULT_ROLE
from core.config import Settings
from core.crypto import hash_password, verify_password, needs_rehash
from service.notifications import NotificationService
from .exceptions import AlreadyExists, WrongCredentials
from ..tokens import TokenService

config = Settings() # pyright: ignore[reportCallIssue]

class CredentialsService:
    def __init__(
        self,
        uow: UoW,
        user_repo: UserInterface,
        role_repo: RolesInterface,
        token_service: TokenService,
        notification_service: NotificationService,
    ):
        self.uow = uow
        self.user_repo = user_repo
        self.role_repo = role_repo
        self.token_service = token_service
        self.notification_service = notification_service
        
    @staticmethod
    async def _check_password(password: str, password_hash: str) -> bool:
        try:
            valid = await verify_password(password, password_hash)
            if not valid:
                raise WrongCredentials()
        except ValueError:
            raise WrongCredentials()
        
        return valid
        
    @staticmethod
    async def _hash_password(password: str) -> str:
        return await hash_password(password)
    
    
    async def register(
        self,
        payload: UserRegister,
        src: Literal['web', 'mobile']
    ) -> tuple[str, str, str]:
        
        password_hash = await self._hash_password(payload.password)

        user = User(
            email=payload.email,
            password_hash=password_hash,
            # allow_password_login=True,
            username=payload.username,
        )
        
        try:
            await self.user_repo.add(user)
            await self.uow.session.flush()
        except IntegrityError:
            raise AlreadyExists()
        
        
        default_role = await self.role_repo.get_by_slug(DEFAULT_ROLE.value)
        if default_role is None:
            raise RuntimeError("Default role is missing from the database")

        await self.user_repo.assign_roles(user, [default_role])

        await self.notification_service.send_text(
            f"New user registered: {payload.email}"
        )
        
        access, refresh, csrf = await self.token_service.issue_tokens(user, src)
        return access, refresh, csrf
    
    
    async def login(
        self,
        payload: UserLogin,
        src: Literal['web', 'mobile']
    ) -> tuple[str, str, str]:
        user = await self.user_repo.get_by_email(payload.email)
        if user is None:
            raise WrongCredentials()

        await self._check_password(payload.password, user.password_hash)
        
        if await needs_rehash(user.password_hash):
            user.password_hash = await self._hash_password(payload.password)
        
        access, refresh, csrf = await self.token_service.issue_tokens(user, src)
        return access, refresh, csrf
    
    
    async def logout(self, refresh_token: str) -> None:
        payload = await self.token_service.revoke(refresh_token)
        if payload is None:
            raise WrongCredentials()
