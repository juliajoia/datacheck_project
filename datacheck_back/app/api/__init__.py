from fastapi import APIRouter

from app.api import analyses, auth, cleaning, dashboard, eda, meta

api_router = APIRouter(prefix="/api")
for module in (meta, auth, analyses, cleaning, eda, dashboard):
    api_router.include_router(module.router)
