from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Path, Query

from core.security import require
from database.relational_db import User
from domain.users import UserModel
from service.users import UserService, get_user_service
from service.users.exceptions import UserNotFoundError

router = APIRouter()


@router.post(
    path='/ban',
    response_model=UserModel,
    summary='Ban or unban a user',
)
async def set_ban(
    user_id: Annotated[UUID, Path(...)],
    _: Annotated[User, Depends(require('admin'))],
    svc: Annotated[UserService, Depends(get_user_service)],
    banned: bool = Query(True, description="Set to false to remove ban"),
):
    target = await svc.get_user(user_id)
    if target is None:
        raise UserNotFoundError()
    
    updated = await svc.admin_set_ban(target, banned=banned)
    return updated
