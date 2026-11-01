from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.services import dashboard_service as svc

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", summary="Indicadores gerais do usuário")
def summary(db: DB, user: CurrentUser):
    return svc.summary(db, user)


@router.get("/charts", summary="Dados dos gráficos do dashboard")
def charts(db: DB, user: CurrentUser):
    return svc.charts(db, user)
