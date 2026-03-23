from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.security import require
from database.relational_db import User
from service.users import UserService, get_user_service

router = APIRouter(prefix="/roles")


@router.get(
    path="/",
    summary="List available roles",
)
async def list_roles(
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[UserService, Depends(get_user_service)],
    search: str | None = Query(None),
    limit: int | None = Query(20, ge=1, le=100),
):
    roles = await svc.list_roles(search=search, limit=limit)
    return [
        {
            "id": str(role.id),
            "slug": role.slug,
            "name": role.name,
            "description": role.description,
        }
        for role in roles
    ]
