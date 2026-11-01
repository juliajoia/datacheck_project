from __future__ import annotations

import uuid
from typing import Optional
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Query, Response, UploadFile
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.core.config import SAMPLE_DIR, get_settings
from app.core.errors import DataCheckError
from app.models import Analysis, AnalysisFeedback, AnalysisVersion, ValidationIssue
from app.schemas.analysis import FeedbackIn, IssueFilters
from app.schemas.validation import RunRequest
from app.services import analysis_service as svc
from app.services import data_store, issues_service, pdf_report, reports

router = APIRouter(prefix="/analyses", tags=["Análises"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SAMPLES = {"1": "municipios_exemplo_1.csv", "2": "municipios_exemplo_2.csv"}


def _upload_response(analysis: Analysis, profile: dict) -> dict:
    return {"id": str(analysis.id), "status": analysis.status, **profile}


@router.post("/upload", status_code=201, summary="Enviar planilha (CSV/XLSX)")
def upload(file: UploadFile, db: DB, user: CurrentUser):
    limit = int(get_settings().max_upload_mb * 1024 * 1024)
    chunks, total = [], 0
    while chunk := file.file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise DataCheckError(f"O arquivo excede o limite de {get_settings().max_upload_mb:g} MB.", 413)
        chunks.append(chunk)
    analysis, profile = svc.create_upload(db, user, file.filename or "arquivo", b"".join(chunks))
    return _upload_response(analysis, profile)


@router.post("/upload-sample/{sample}", status_code=201, summary="Carregar base fictícia de demonstração")
def upload_sample(sample: str, db: DB, user: CurrentUser):
    name = SAMPLES.get(sample)
    if not name or not (SAMPLE_DIR / name).exists():
        raise DataCheckError("Base de demonstração inexistente.", 404)
    analysis, profile = svc.create_upload(db, user, name, (SAMPLE_DIR / name).read_bytes())
    return _upload_response(analysis, profile)


@router.get("/{analysis_id}/profile", summary="Perfil da planilha (opcionalmente de outra aba)")
def profile(analysis_id: uuid.UUID, db: DB, user: CurrentUser, sheet: Optional[str] = None):
    analysis = svc.get_owned(db, user, analysis_id)
    return _upload_response(analysis, svc.profile(analysis, sheet))


@router.post("/{analysis_id}/run", summary="Executar as verificações")
def run(analysis_id: uuid.UUID, body: RunRequest, db: DB, user: CurrentUser):
    analysis = svc.run(db, svc.get_owned(db, user, analysis_id), body, user)
    return svc.to_result(analysis)


@router.get("", summary="Listar análises do usuário")
def list_analyses(db: DB, user: CurrentUser, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    where = (Analysis.user_id == user.id, Analysis.status != "uploaded")
    total = db.scalar(select(func.count()).select_from(Analysis).where(*where))
    rows = db.scalars(select(Analysis).where(*where).order_by(Analysis.created_at.desc())
                      .limit(page_size).offset((page - 1) * page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [svc.list_item(a) for a in rows]}


@router.get("/{analysis_id}", summary="Detalhes e indicadores de uma análise")
def get_analysis(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    analysis = svc.get_owned(db, user, analysis_id)
    sent = db.scalar(select(func.count()).select_from(AnalysisFeedback)
                     .where(AnalysisFeedback.analysis_id == analysis.id, AnalysisFeedback.user_id == user.id))
    return {**svc.to_result(analysis), "feedback_submitted": bool(sent)}


@router.get("/{analysis_id}/data", summary="Visualizar a planilha (padrão: a original enviada), sem baixar arquivo")
def view_data(analysis_id: uuid.UUID, db: DB, user: CurrentUser, version: int = Query(0, ge=0), q: Optional[str] = None,
              page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    analysis = svc.get_owned(db, user, analysis_id)
    v = db.scalar(select(AnalysisVersion).where(AnalysisVersion.analysis_id == analysis.id, AnalysisVersion.version_number == version))
    if not v or not v.storage_reference or v.status == "purged":
        raise DataCheckError("A planilha desta análise não está armazenada (a opção de manter a base estava desligada ou o prazo de retenção expirou).", 409)
    df, rows = data_store.load_version(v.storage_reference)
    keep = list(range(len(df)))
    if q and q.strip():
        needle = q.strip().lower()
        mask = df.apply(lambda c: c.str.lower().str.contains(needle, regex=False)).any(axis=1) | pd.Series([needle in str(r) for r in rows], index=df.index)
        keep = [i for i in keep if bool(mask.iloc[i])]
    total, start = len(keep), (page - 1) * page_size
    chunk = keep[start:start + page_size]
    page_rows = [rows[i] for i in chunk]
    flags: dict[int, dict[str, dict]] = {}
    if version == 0 and page_rows:
        order = {"critical": 0, "warning": 1, "info": 2}
        for r, col, sev, cat, desc in db.execute(select(ValidationIssue.row_number, ValidationIssue.column_name, ValidationIssue.severity,
                                                         ValidationIssue.issue_type, ValidationIssue.description)
                                                  .where(ValidationIssue.analysis_id == analysis.id, ValidationIssue.row_number.in_(page_rows))):
            cur = flags.setdefault(r, {}).get(col)
            if not cur or order[sev] < order[cur["severity"]]:
                flags[r][col] = {"severity": sev, "category": cat, "description": desc}
    return {"version": version, "label": v.label, "columns": list(df.columns), "total": total, "page": page, "page_size": page_size,
            "total_rows": len(df), "rows": [{"row": rows[i], "values": df.iloc[i].tolist(), "flags": flags.get(rows[i], {})} for i in chunk]}


@router.get("/{analysis_id}/issues", summary="Ocorrências (busca, filtros, ordenação e paginação)")
def issues(analysis_id: uuid.UUID, db: DB, user: CurrentUser, q: Optional[str] = None,
           column: list[str] = Query([]), category: list[str] = Query([]), severity: list[str] = Query([]),
           sort_by: str = "row", descending: bool = False,
           page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
    analysis = svc.get_owned(db, user, analysis_id)
    f = IssueFilters(q=q, columns=column, categories=category, severities=severity,
                     sort_by=sort_by, descending=descending)
    return issues_service.page(db, analysis.id, f, page, page_size)


@router.delete("/{analysis_id}", status_code=204, summary="Excluir análise e suas ocorrências")
def delete(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    svc.delete_analysis(db, svc.get_owned(db, user, analysis_id))


@router.get("/{analysis_id}/export", summary="Exportar relatório (format=csv|xlsx)")
def export(analysis_id: uuid.UUID, db: DB, user: CurrentUser, format: str = "xlsx"):
    if format not in ("csv", "xlsx"):
        raise DataCheckError("Formato de exportação inválido. Use csv ou xlsx.", 422)
    analysis = svc.get_owned(db, user, analysis_id)
    if analysis.status != "completed":
        raise DataCheckError("A análise ainda não foi concluída.", 409)
    result, found = svc.to_result(analysis), issues_service.all_issues(db, analysis.id)
    data = reports.report_xlsx(result, found) if format == "xlsx" else reports.report_csv(result, found)
    stem = f"datacheck_{analysis.filename.rsplit('.', 1)[0]}"
    return Response(data, media_type=XLSX if format == "xlsx" else "text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(stem)}.{format}"})


@router.get("/{analysis_id}/export/issues", summary="Exportar a tabela de inconsistências (format=xlsx|pdf)")
def export_issues(analysis_id: uuid.UUID, db: DB, user: CurrentUser, format: str = "xlsx"):
    if format not in ("xlsx", "pdf"):
        raise DataCheckError("Formato de exportação inválido. Use xlsx ou pdf.", 422)
    analysis = svc.get_owned(db, user, analysis_id)
    if analysis.status != "completed":
        raise DataCheckError("A análise ainda não foi concluída.", 409)
    found = issues_service.all_issues(db, analysis.id)
    if format == "pdf":
        data, media = pdf_report.issues_pdf(svc.to_result(analysis), found), "application/pdf"
    else:
        data, media = reports.issues_xlsx(found), XLSX
    stem = f"datacheck_inconsistencias_{analysis.filename.rsplit('.', 1)[0]}"
    return Response(data, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(stem)}.{format}"})


@router.post("/{analysis_id}/feedback", status_code=201, summary="Registrar feedback sobre a análise")
def feedback(analysis_id: uuid.UUID, body: FeedbackIn, db: DB, user: CurrentUser):
    analysis = svc.get_owned(db, user, analysis_id)
    db.add(AnalysisFeedback(analysis_id=analysis.id, user_id=user.id, **body.model_dump()))
    db.commit()
    return {"ok": True}
