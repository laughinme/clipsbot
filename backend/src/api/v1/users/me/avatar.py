from typing import Annotated

from fastapi import APIRouter, Depends

from core.security import auth_user
from database.relational_db import User
from domain.users import (
    AvatarConfirmRequest,
    AvatarPresignRequest,
    AvatarPresignResponse,
    UserModel,
)
from service.users import UserService, get_user_service

router = APIRouter()


@router.post(
    path="/me/avatar/presign",
    response_model=AvatarPresignResponse,
    summary="Create presigned URL for avatar upload",
)
async def create_avatar_presigned_upload(
    payload: AvatarPresignRequest,
    user: Annotated[User, Depends(auth_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> AvatarPresignResponse:
    return await svc.create_avatar_presign(
        user=user,
        filename=payload.filename,
        content_type=payload.content_type,
    )


@router.post(
    path="/me/avatar/confirm",
    response_model=UserModel,
    summary="Confirm uploaded avatar and attach it to profile",
)
async def confirm_avatar_upload(
    payload: AvatarConfirmRequest,
    user: Annotated[User, Depends(auth_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> User:
    await svc.confirm_avatar_upload(user=user, object_key=payload.object_key)
    return user


@router.delete(
    path="/me/avatar",
    response_model=UserModel,
    summary="Remove current user avatar",
)
async def delete_avatar(
    user: Annotated[User, Depends(auth_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> User:
    await svc.remove_avatar(user=user)
    return user
