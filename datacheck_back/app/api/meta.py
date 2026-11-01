from fastapi import APIRouter

from app.core.catalog import CATEGORIES, RULES_INFO, SEVERITY_LABELS
from app.core.config import DEFAULT_MARKERS, get_settings
from app.services.file_reader import ALLOWED_EXTENSIONS

router = APIRouter(tags=["Geral"])


@router.get("/health", summary="Verificação de saúde")
def health():
    return {"status": "ok"}


@router.get("/settings", summary="Configurações públicas (limite de upload etc.)")
def settings():
    return {"max_upload_mb": get_settings().max_upload_mb, "allowed_extensions": list(ALLOWED_EXTENSIONS),
            "default_markers": DEFAULT_MARKERS,
            "data_retention_days": get_settings().data_retention_days, "max_versions": get_settings().max_versions}


@router.get("/rules", summary="Catálogo de verificações, categorias e severidades")
def rules():
    return {"rules": RULES_INFO, "categories": [{"code": k, **v} for k, v in CATEGORIES.items()],
            "severities": SEVERITY_LABELS}
