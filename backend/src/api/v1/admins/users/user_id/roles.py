from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from core.security import require
from database.relational_db import User
from domain.users import UserModel, UserRolesUpdate
from service.users import UserService, get_user_service
from service.users.exceptions import UserNotFoundError

router = APIRouter()


@router.put(
    path="/roles",
    response_model=UserModel,
    summary="Assign roles to user",
)
async def set_roles(
    payload: UserRolesUpdate,
    user_id: Annotated[UUID, Path(...)],
    current_user: Annotated[User, Depends(require('admin'))],
    svc: Annotated[UserService, Depends(get_user_service)],
):
    target = await svc.get_user(user_id)
    if target is None:
        raise UserNotFoundError()

    updated = await svc.admin_assign_roles(current_user, target, payload.roles)
    return updated
