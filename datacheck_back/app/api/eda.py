from __future__ import annotations

import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Query, Response

from app.api.deps import DB, CurrentUser
from app.schemas.eda import EdaConfig
from app.services import analysis_service as svc
from app.services.eda import service

router = APIRouter(tags=["Análise exploratória (EDA)"])


@router.get("/analyses/{analysis_id}/eda/options", summary="Seções e colunas aplicáveis à EDA da versão (e prontidão)")
def options(analysis_id: uuid.UUID, db: DB, user: CurrentUser, version_number: Optional[int] = None):
    return service.options(db, svc.get_owned(db, user, analysis_id), version_number)


@router.post("/analyses/{analysis_id}/eda/generate", status_code=202, summary="Gerar relatório EDA (processamento em segundo plano)")
def generate(analysis_id: uuid.UUID, body: EdaConfig, tasks: BackgroundTasks, db: DB, user: CurrentUser):
    report = service.create(db, svc.get_owned(db, user, analysis_id), user, body)
    tasks.add_task(service.run_job, report.id)
    return service.detail(db, user, report.id)


@router.get("/eda", summary="Relatórios EDA do usuário")
def list_reports(db: DB, user: CurrentUser, analysis_id: Optional[uuid.UUID] = None):
    return service.list_reports(db, user, analysis_id)


@router.get("/eda/{report_id}", summary="Detalhes e estatísticas de um relatório EDA")
def get_report(report_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.detail(db, user, report_id)


@router.get("/eda/{report_id}/download", summary="Baixar relatório (format=pdf|xlsx)")
def download(report_id: uuid.UUID, db: DB, user: CurrentUser, format: str = Query("pdf")):
    data, media, name = service.download(db, user, report_id, format)
    return Response(data, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.post("/eda/{report_id}/regenerate", status_code=202, summary="Gerar novamente (mesma versão e configuração)")
def regenerate(report_id: uuid.UUID, tasks: BackgroundTasks, db: DB, user: CurrentUser):
    report = service.regenerate(db, user, report_id)
    tasks.add_task(service.run_job, report.id)
    return service.detail(db, user, report.id)


@router.delete("/eda/{report_id}", status_code=204, summary="Excluir relatório EDA e seus arquivos")
def delete(report_id: uuid.UUID, db: DB, user: CurrentUser):
    service.delete(db, user, report_id)
