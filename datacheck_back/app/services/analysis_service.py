"""Ciclo de vida de uma análise: upload → configuração → execução → persistência."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from typing import Optional

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DataCheckError
from app.models import Analysis, AnalysisVersion, EdaReport, User, ValidationIssue
from app.schemas.validation import RunRequest
from app.services import data_store, temp_storage
from app.services.analyzer import run_analysis
from app.services.file_reader import ALLOWED_EXTENSIONS, read_table
from app.services.profiler import build_profile
from app.utils.dates import iso

logger = logging.getLogger("datacheck")
INSERT_CHUNK = 5000


def cleanup_expired(db: Session) -> None:
    """Remove arquivos temporários e uploads abandonados (nunca analisados) vencidos."""
    temp_storage.purge_expired()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=get_settings().upload_ttl_minutes)
    db.execute(delete(Analysis).where(Analysis.status == "uploaded", Analysis.created_at < cutoff))
    # Retenção: bases armazenadas expiram; indicadores e ocorrências permanecem, mas o tratamento deixa de estar disponível.
    now = datetime.now(timezone.utc)
    for a in db.scalars(select(Analysis).where(Analysis.data_expires_at.is_not(None), Analysis.data_expires_at < now,
                                                Analysis.current_version.is_not(None))):
        data_store.delete_analysis_versions(a.id)
        for v in db.scalars(select(AnalysisVersion).where(AnalysisVersion.analysis_id == a.id)):
            v.storage_reference, v.status = None, "purged"
        a.current_version = None
    db.commit()


def create_upload(db: Session, user: User, filename: str, content: bytes) -> tuple[Analysis, dict]:
    cleanup_expired(db)
    name = PurePath(filename.replace("\\", "/")).name[:255] or "arquivo"
    table = read_table(content, name)  # valida formato, codificação, vazio, corrompido
    analysis = Analysis(
        user_id=user.id, filename=name, file_type=PurePath(name).suffix.lower().lstrip("."),
        file_size=len(content), sheet_name=table.sheet, total_rows=len(table.df),
        total_columns=int(table.df.shape[1]), status="uploaded")
    db.add(analysis)
    db.commit()
    temp_storage.save(analysis.id, content)
    return analysis, build_profile(table, name, len(content))


def get_owned(db: Session, user: User, analysis_id: uuid.UUID) -> Analysis:
    """Só devolve análises do próprio usuário; para os demais responde 404 (não vaza existência)."""
    analysis = db.scalar(select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id))
    if not analysis:
        raise DataCheckError("Análise não encontrada.", 404)
    return analysis


def _content(analysis: Analysis) -> bytes:
    if analysis.status != "uploaded":
        raise DataCheckError("Esta análise já foi processada.", 409)
    content = temp_storage.load(analysis.id)
    if content is None:
        raise DataCheckError("O arquivo temporário expirou. Envie a planilha novamente.", 410)
    return content


def profile(analysis: Analysis, sheet: Optional[str]) -> dict:
    table = read_table(_content(analysis), analysis.filename, sheet)
    return build_profile(table, analysis.filename, analysis.file_size)


def run(db: Session, analysis: Analysis, req: RunRequest, user: Optional[User] = None) -> Analysis:
    content = _content(analysis)
    # Transição atômica: impede duas execuções simultâneas da mesma análise.
    claimed = db.execute(update(Analysis).where(Analysis.id == analysis.id, Analysis.status == "uploaded")
                         .values(status="processing")).rowcount
    db.commit()
    if not claimed:
        raise DataCheckError("Esta análise já está em processamento ou foi concluída.", 409)
    try:
        table = read_table(content, analysis.filename, req.sheet)
        result, issues = run_analysis(table, req.config, filename=analysis.filename, file_size=analysis.file_size)
    except DataCheckError:
        _set_status(db, analysis, "uploaded")  # erro de configuração: o usuário pode corrigir e tentar de novo
        raise
    except Exception as exc:
        logger.error("Falha na análise %s: %s", analysis.id, type(exc).__name__)
        analysis.error_message = "Falha inesperada ao processar a planilha."
        _set_status(db, analysis, "failed")
        temp_storage.delete(analysis.id)
        raise DataCheckError("Ocorreu um erro ao processar a planilha.", 500)

    m = result["metrics"]
    analysis.sheet_name = table.sheet
    analysis.total_rows, analysis.total_columns = m["total_rows"], m["total_columns"]
    analysis.total_issues, analysis.affected_rows = m["total_occurrences"], m["affected_rows"]
    analysis.quality_score = result["score"]["value"]
    analysis.validation_config = {**req.config.model_dump(mode="json"), "store_values": req.store_values, "keep_data": req.keep_data}
    analysis.summary = result
    analysis.status, analysis.completed_at = "completed", datetime.now(timezone.utc)
    db.flush()
    rows = [{"analysis_id": analysis.id, "row_number": i.row, "column_name": i.column,
             "original_value": i.value if req.store_values else None, "issue_type": i.category,
             "severity": i.severity, "description": i.description, "suggestion": i.suggestion} for i in issues]
    for start in range(0, len(rows), INSERT_CHUNK):
        db.execute(insert(ValidationIssue), rows[start:start + INSERT_CHUNK])
    if req.keep_data:
        from app.services.cleaning import service as cleaning  # evita import circular
        cleaning.create_original_version(db, analysis, table.df, [table.first_data_line + i for i in range(len(table.df))],
                                         result, issues, user)
    db.commit()
    temp_storage.delete(analysis.id)
    return analysis


def _set_status(db: Session, analysis: Analysis, status: str) -> None:
    analysis.status = status
    db.commit()


def delete_analysis(db: Session, analysis: Analysis) -> None:
    temp_storage.delete(analysis.id)
    for ref in db.scalars(select(EdaReport.file_reference).where(EdaReport.analysis_id == analysis.id)):
        for ext in ("pdf", "xlsx"):
            data_store.delete_reference(f"{ref}.{ext}" if ref else None)
    data_store.delete_analysis_versions(analysis.id)
    db.delete(analysis)
    db.commit()


def list_item(a: Analysis) -> dict:
    rules = [r["name"] for r in (a.summary or {}).get("rules", []) if r.get("executed")]
    return {
        "id": str(a.id), "filename": a.filename, "file_type": a.file_type, "status": a.status,
        "created_at": iso(a.created_at), "completed_at": iso(a.completed_at),
        "total_rows": a.total_rows, "total_columns": a.total_columns, "total_issues": a.total_issues,
        "affected_rows": a.affected_rows, "quality_score": a.quality_score, "rules_used": rules,
        "sheet": a.sheet_name, "workflow_status": a.workflow_status, "current_version": a.current_version,
        "data_available": a.current_version is not None,
    }


def to_result(a: Analysis) -> dict:
    """Resultado completo (resumo salvo + identificação)."""
    return {**list_item(a), "file_size_bytes": a.file_size, "error_message": a.error_message,
            "store_values": (a.validation_config or {}).get("store_values", True), **(a.summary or {})}
