from fastapi import APIRouter


def get_webhooks() -> APIRouter:
    
    webhooks = APIRouter(prefix='/webhooks', tags=['Webhooks'])
    
    return webhooks
