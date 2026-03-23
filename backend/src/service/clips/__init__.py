from fastapi import Depends

from broker import BrokerPublisher, get_broker_publisher
from database.relational_db import ClipsInterface, UoW, UserInterface, get_uow
from service.media import MediaStorageService, get_media_storage_service
from .clip_service import ClipService


async def get_clip_service(
    uow: UoW = Depends(get_uow),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
    broker: BrokerPublisher = Depends(get_broker_publisher),
) -> ClipService:
    clip_repo = ClipsInterface(uow.session)
    user_repo = UserInterface(uow.session)
    return ClipService(
        uow=uow,
        clip_repo=clip_repo,
        user_repo=user_repo,
        media_storage=media_storage,
        broker=broker,
    )


from .clip_service import ClipService
