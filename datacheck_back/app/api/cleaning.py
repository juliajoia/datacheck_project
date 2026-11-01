from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from app.api.deps import DB, CurrentUser
from app.core.errors import DataCheckError
from app.utils.dates import iso
from app.schemas.cleaning import CleaningRequest, ColumnTypesIn, OutlierRequest
from app.services import analysis_service as svc
from app.services.cleaning import export as treated_export
from app.services.cleaning import fixes, service

router = APIRouter(prefix="/analyses/{analysis_id}", tags=["Tratamento de dados"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _own(db, user, analysis_id: uuid.UUID):
    return svc.get_owned(db, user, analysis_id)


@router.get("/cleaning/summary", summary="Indicadores do tratamento (progresso, pendências, antes × depois)")
def summary(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.summary(db, _own(db, user, analysis_id))


@router.get("/cleaning/options", summary="Tipos de variável e, com ?column=, recomendação e métodos de imputação")
def options(analysis_id: uuid.UUID, db: DB, user: CurrentUser, column: Optional[str] = None):
    return service.column_options(db, _own(db, user, analysis_id), column)


@router.put("/cleaning/column-types", summary="Alterar manualmente a classificação estatística das variáveis")
def column_types(analysis_id: uuid.UUID, body: ColumnTypesIn, db: DB, user: CurrentUser):
    return service.set_column_types(db, _own(db, user, analysis_id), body.types)


@router.get("/cleaning/issues", summary="Inconsistências pendentes da versão corrente")
def issues(analysis_id: uuid.UUID, db: DB, user: CurrentUser, category: list[str] = Query([]), column: list[str] = Query([]),
           severity: list[str] = Query([]), q: Optional[str] = None, include_accepted: bool = False,
           page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
    return service.issues_page(db, _own(db, user, analysis_id), category=category, column=column, severity=severity, q=q,
                               include_accepted=include_accepted, page=page, page_size=page_size)


@router.get("/cleaning/duplicates", summary="Grupos de registros duplicados da versão corrente")
def duplicates(analysis_id: uuid.UUID, db: DB, user: CurrentUser, limit: int = Query(200, ge=1, le=1000)):
    st = service.load_state(db, _own(db, user, analysis_id))
    groups = fixes.duplicate_groups(st.ctx, st.config.duplicates.key_columns)
    keys = st.config.duplicates.key_columns or []
    return {"version": st.version.version_number, "key_columns": keys,
            "issue_column": ", ".join(keys) if keys else "(linha completa)",  # coluna usada nas ocorrências de duplicidade
            "total_groups": len(groups), "conflicting_groups": sum(not g["exact"] for g in groups),
            "temporal_columns": [c for c, i in st.stat.items() if i["stat_type"] == "temporal"],
            "groups": groups[:limit], "truncated": len(groups) > limit}


@router.post("/cleaning/outliers", summary="Detectar possíveis valores extremos (IQR, z-score ou limites)")
def outliers(analysis_id: uuid.UUID, body: OutlierRequest, db: DB, user: CurrentUser):
    st = service.load_state(db, _own(db, user, analysis_id))
    if body.column not in st.df.columns:
        raise DataCheckError(f"A coluna «{body.column}» não existe.", 404)
    if st.stat[body.column]["stat_type"] not in ("quant_discrete", "quant_continuous"):
        raise DataCheckError("Valores extremos só se aplicam a variáveis quantitativas.", 422)
    return fixes.detect_outliers(st.ctx, body.column, body.method, body.params)


@router.get("/cleaning/coordinate-suggestions", summary="Linhas com provável inversão entre latitude e longitude")
def coordinate_suggestions(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    st = service.load_state(db, _own(db, user, analysis_id))
    g = st.config.geo
    if not g.lat_column or not g.lon_column:
        return {"lat_column": None, "lon_column": None, "suggestions": []}
    return {"lat_column": g.lat_column, "lon_column": g.lon_column, "suggestions": fixes.suggest_coordinate_swaps(st.ctx, g.lat_column, g.lon_column)}


@router.post("/cleaning/preview", summary="Prévia de uma correção (nada é gravado)")
def preview(analysis_id: uuid.UUID, body: CleaningRequest, db: DB, user: CurrentUser):
    return service.preview(db, _own(db, user, analysis_id), body)


@router.post("/cleaning/apply", summary="Aplicar uma correção confirmada (cria uma nova versão)")
def apply(analysis_id: uuid.UUID, body: CleaningRequest, db: DB, user: CurrentUser):
    return service.apply(db, _own(db, user, analysis_id), user, body)


@router.post("/cleaning/undo", summary="Desfazer a última alteração")
def undo(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.undo(db, _own(db, user, analysis_id), user)


@router.get("/cleaning/history", summary="Histórico de correções")
def history(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.history(db, _own(db, user, analysis_id))


@router.post("/cleaning/validate", summary="Validar base tratada (reexecuta as regras)")
def validate(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.validate_treated(db, _own(db, user, analysis_id))


@router.get("/cleaning/export", summary="Baixar a base tratada (csv|xlsx)")
def export(analysis_id: uuid.UUID, db: DB, user: CurrentUser, format: str = "csv", delimiter: str = "comma",
           encoding: str = "utf-8-sig", decimal: str = "keep", include_summary: bool = True):
    if format not in ("csv", "xlsx"):
        raise DataCheckError("Formato inválido. Use csv ou xlsx.", 422)
    analysis = _own(db, user, analysis_id)
    st = service.load_state(db, analysis)
    markers, dec = st.config.missing.markers, st.config.decimal_separator
    if format == "csv":
        data = treated_export.export_csv(st.df, st.stat, markers, dec, delimiter=delimiter, encoding=encoding, decimal=decimal)
        media = "text/csv; charset=utf-8"
    else:
        info = None
        if include_summary:
            s = service.summary(db, analysis)
            ops, after, before = s["operations"], s["after"], s["before"]
            info = {"Arquivo de origem": analysis.filename, "Versão exportada": st.version.label,
                    "Data do processamento (UTC)": iso(datetime.now(timezone.utc)),
                    "Registros (original)": before.get("rows"), "Registros (tratada)": after["rows"],
                    "Valores imputados": ops["imputed_values"], "Registros removidos": ops["removed_rows"],
                    "Duplicidades resolvidas": ops["duplicates_resolved"], "Correções manuais": ops["manual_corrections"],
                    "Ocorrências aceitas como exceção": after["accepted"], "Inconsistências pendentes": after["pending"],
                    "Score antes": before.get("score"), "Score depois": after["score"]}
        data, media = treated_export.export_xlsx(st.df, st.stat, markers, dec, info), XLSX
    name = f"datacheck_tratada_{analysis.filename.rsplit('.', 1)[0]}_v{st.version.version_number}"
    return Response(data, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.{format}"})


@router.get("/versions", summary="Versões da base")
def versions(analysis_id: uuid.UUID, db: DB, user: CurrentUser):
    return service.versions_list(db, _own(db, user, analysis_id))


@router.get("/versions/{version_id}", summary="Detalhes de uma versão")
def version_detail(analysis_id: uuid.UUID, version_id: str, db: DB, user: CurrentUser):
    analysis = _own(db, user, analysis_id)
    for v in service.versions_list(db, analysis):
        if v["id"] == version_id or str(v["version_number"]) == version_id:
            return v
    raise DataCheckError("Versão não encontrada.", 404)


@router.post("/versions/{version_id}/restore", summary="Restaurar uma versão (0 = base original)")
def restore(analysis_id: uuid.UUID, version_id: str, db: DB, user: CurrentUser):
    analysis = _own(db, user, analysis_id)
    for v in service.versions_list(db, analysis):
        if v["id"] == version_id or str(v["version_number"]) == version_id:
            return service.restore(db, analysis, user, v["version_number"])
    raise DataCheckError("Versão não encontrada.", 404)
