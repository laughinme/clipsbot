from typing import Annotated
from fastapi import APIRouter, Depends, Query

from core.security import require
from database.relational_db import User
from domain.users import UserModel
from service.users import UserService, get_user_service
from domain.common import CursorPage

router = APIRouter()


@router.get(
    path='/',
    response_model=CursorPage[UserModel],
    summary='List users with filters and search (cursor pagination)',
)
async def list_users(
    _: Annotated[User, Depends(require('admin'))],
    svc: Annotated[UserService, Depends(get_user_service)],
    banned: bool | None = Query(None, description='Filter by banned status'),
    search: str | None = Query(None, description='Search by username or email'),
    limit: int = Query(50, ge=1, le=100, description='Page size'),
    cursor: str | None = Query(None, description='Opaque cursor'),
):
    users, next_cursor = await svc.admin_list_users(
        banned=banned,
        search=search,
        limit=limit,
        cursor=cursor,
    )
    return CursorPage(items=users, next_cursor=next_cursor)
