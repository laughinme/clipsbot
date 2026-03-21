from typing import Annotated
from fastapi import APIRouter, Depends

from database.relational_db import User
from domain.users import UserModel, UserPatch
from core.security import auth_user
from service.users import UserService, get_user_service

router = APIRouter()

@router.get(
    path='/me',
    response_model=UserModel,
    summary='Get user account info'
)
async def profile(
    user: Annotated[User, Depends(auth_user)],
    # TODO: Add expandable fields
    # expand: Annotated[list[ExpandUserFields], Query(default_factory=list, description="Fields to expand with in the response")],
    # svc: Annotated[UserService, Depends(get_user_service)],
):
    return user


@router.patch(
    path='/me',
    response_model=UserModel,
    summary='Update user info'
)
async def update_profile(
    payload: UserPatch,
    user: Annotated[User, Depends(auth_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
):
    await svc.patch_user(payload, user)
    return user
