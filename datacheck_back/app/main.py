"""DataCheck — API de validação e diagnóstico de qualidade de dados."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import DEV_SECRET, get_settings
from app.core.errors import DataCheckError
from app.services import temp_storage

# Logs apenas de eventos técnicos; nunca conteúdo de planilhas ou dados pessoais.
logger = logging.getLogger("datacheck")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    if s.environment == "production" and s.secret_key == DEV_SECRET:
        raise RuntimeError("Defina DATACHECK_SECRET_KEY em produção.")
    temp_storage.purge_expired()
    try:  # aplica a política de retenção das bases armazenadas (não impede a API de subir se o banco estiver indisponível)
        from sqlalchemy.orm import Session
        from app.database import get_engine
        from app.services.analysis_service import cleanup_expired
        with Session(get_engine()) as db:
            cleanup_expired(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Limpeza de retenção não executada: %s", type(exc).__name__)
    yield


app = FastAPI(
    title="DataCheck API", version="2.0.0", lifespan=lifespan,
    description="API de validação e diagnóstico de qualidade de dados. Dados confiáveis. Decisões inteligentes.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
)
app.include_router(api_router)


@app.exception_handler(DataCheckError)
async def handle_known(_: Request, exc: DataCheckError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def handle_validation(_: Request, exc: RequestValidationError):
    fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) or "corpo" for e in exc.errors())
    return JSONResponse({"detail": f"Dados inválidos: {fields}.", "fields": [e["loc"][1:] for e in exc.errors()]},
                        status_code=422)


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception):
    logger.error("Erro inesperado: %s", type(exc).__name__)
    return JSONResponse({"detail": "Ocorreu um erro interno ao processar a solicitação."}, status_code=500)
