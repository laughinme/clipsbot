import json
import secrets
from typing import Annotated, Literal

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings
from core.errors import ForbiddenError, UnauthorizedError
from core.rbac import (
    ROLES_CACHE_TTL_SECONDS, 
    roles_cache_key,
    GLOBAL_ROLE_IMPLICATIONS,
    TEAM_ROLE_IMPLICATIONS,
)
from database.redis import CacheRepo, get_redis
from database.relational_db import User
from service.auth import TokenService, get_token_service
from service.users import UserService, get_user_service
# from service.organizations import OrganizationService, get_organization_service

security = HTTPBearer(
    description="Access token must be passed as Bearer to authorize request"
)


async def extract_jti(request: Request) -> str:
    token = request.cookies.get("refresh_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
    if not token:
        raise UnauthorizedError("Missing refresh token")
    try:
        payload = jwt.decode(
            token, options={"verify_signature": False, "verify_exp": False}
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Bad refresh token passed") from exc
    jti = payload.get("jti")
    if not jti:
        raise UnauthorizedError("Bad refresh token passed")
    return jti

async def parse_token(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    token_svc: Annotated[TokenService, Depends(get_token_service)],
) -> dict[str, int | str]:
    payload = await token_svc.verify_access(creds.credentials)
    if payload is None:
        raise UnauthorizedError("Bad access token passed")
    
    return payload

async def auth_user(
    payload: Annotated[dict[str, int | str], Depends(parse_token)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> User:
    user_id = str(payload["sub"])
    user = await svc.get_user(user_id)
    if user is None:
        raise UnauthorizedError("Not authorized")
    if user.banned:
        raise ForbiddenError(
            "Your account is banned, contact support: laughinmee@gmail.com",
        )

    return user


async def load_cached_roles(user: User) -> list[str]:
    cache_repo = CacheRepo(get_redis())

    roles = await cache_repo.get(roles_cache_key(user.id, user.auth_version))
    
    if roles is not None:
        return json.loads(roles)
    
    roles_slugs = user.role_slugs
    await cache_repo.set(roles_cache_key(user.id, user.auth_version), json.dumps(roles_slugs), ttl=ROLES_CACHE_TTL_SECONDS)

    return roles_slugs

def verify_auth_version(token_version: int | str | None, user: User) -> None:
    if token_version is None or int(token_version) != int(user.auth_version):
        raise UnauthorizedError("Access token expired, please sign in again")


def expand_roles(roles: list[str], implications: dict[str, set[str]]) -> set[str]:
    """Expand roles to include all implied roles"""
    base = set(roles)
    
    effective_roles = set(base)
    stack = list(base)
    
    while stack:
        role = stack.pop()
        for implied in implications.get(role, set()):
            if implied not in effective_roles:
                effective_roles.add(implied)
                stack.append(implied)
    
    return effective_roles


def require(
    *roles: str,
    scope: Literal["global", "org"] = "global",
    org_kw: str = "org_id",
    bypass_global: frozenset[str] = frozenset({"admin"}),
    bypass_team: frozenset[str] = frozenset({"owner"}),
):
    expected = set(roles)

    async def dependency(
        request: Request,
        payload: Annotated[dict[str, int | str], Depends(parse_token)],
        user: Annotated[User, Depends(auth_user)],
        # org_svc: Annotated[OrganizationService, Depends(get_organization_service)],
    ) -> None:
        
        verify_auth_version(payload.get("av"), user)
        
        global_roles = await load_cached_roles(user)
        eff_roles = expand_roles(list(global_roles), GLOBAL_ROLE_IMPLICATIONS)
        
        if eff_roles & bypass_global:
            return
        
        if scope == "global":
            if not expected.issubset(eff_roles):
                raise ForbiddenError("You don't have permission to do this")
            return
        
        # elif scope == "org":
        #     org_id = request.path_params.get(org_kw) or request.query_params.get(org_kw)
        #     if org_id is None:
        #         raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Organization ID is required")
            
        #     user_org_role = await org_svc.get_membership_role(org_id, user.id)
        #     if user_org_role is None:
        #         raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You don't have permission to do this")
            
        #     org_roles = expand_roles([user_org_role.value], TEAM_ROLE_IMPLICATIONS)
        #     if org_roles & bypass_team:
        #         return
            
        #     if not expected.issubset(org_roles):
        #         raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You don't have permission to do this")

    return dependency


async def require_internal_service(
    x_internal_service_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    settings = get_settings()
    if not x_internal_service_token:
        raise UnauthorizedError("Missing internal service token")
    if not secrets.compare_digest(x_internal_service_token, settings.INTERNAL_BOT_TOKEN):
        raise UnauthorizedError("Invalid internal service token")


# async def _resolve_permissions(
#     user: User,
#     cache_repo: CacheRepo,
# ) -> set[str]:
#     cache_key = permissions_cache_key(user.id, user.auth_version)
#     cached = await cache_repo.get(cache_key)
#     if cached:
#         try:
#             return set(json.loads(cached))
#         except json.JSONDecodeError:
#             await cache_repo.delete(cache_key)

#     permissions = set(user.permission_slugs)
#     if permissions:
#         await cache_repo.set(
#             cache_key,
#             json.dumps(sorted(permissions)),
#             ttl=PERMISSIONS_CACHE_TTL_SECONDS,
#         )
#     return permissions


# def require_permissions(*permissions: SystemPermission | str):
#     expected = {
#         perm.value if isinstance(perm, SystemPermission) else str(perm)
#         for perm in permissions
#     }

#     async def dependency(
#         user: Annotated[User, Depends(auth_user)],
#     ) -> User:
#         cache_repo = CacheRepo(get_redis())
#         granted = await _resolve_permissions(user, cache_repo)
#         if not expected.issubset(granted):
#             raise HTTPException(
#                 status.HTTP_403_FORBIDDEN,
#                 detail="You don't have permission to do this",
#             )
#         return user

#     return dependency
