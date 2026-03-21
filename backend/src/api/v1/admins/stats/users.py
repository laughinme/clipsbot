from typing import Annotated
from fastapi import APIRouter, Depends, Query

from database.relational_db import User
from domain.statistics import RegistrationsGraph, UserStatsSummary
from core.security import require
from service.statistics import StatService, get_stats_service

router = APIRouter()

@router.get(
    path='/summary',
    response_model=UserStatsSummary,
    summary='Get users summary counters',
)
async def users_summary(
    _: Annotated[User, Depends(require('admin'))],
    svc: Annotated[StatService, Depends(get_stats_service)],
):
    return await svc.users_summary()

@router.get(
    path='/registrations',
    response_model=list[RegistrationsGraph],
    summary='Get graph data for new registrations by days',
)
async def registrations(
    _: Annotated[User, Depends(require('admin'))],
    svc: Annotated[StatService, Depends(get_stats_service)],
    days: int = Query(30, description='Number of days back to retrieve data for'),
):
    return await svc.new_registrations(days)
