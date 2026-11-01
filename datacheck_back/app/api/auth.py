from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import DB, GUEST_EMAIL, LoggedUser
from app.core.config import get_settings
from app.core.errors import DataCheckError
from app.core.security import COOKIE_NAME, create_session_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["Autenticação (opcional)"])


def _set_cookie(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(COOKIE_NAME, create_session_token(user.id), max_age=s.session_days * 86400,
                        httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite, path="/")


@router.post("/register", response_model=UserOut, status_code=201, summary="Criar conta")
def register(body: RegisterIn, response: Response, db: DB):
    email = body.email.lower()
    if email == GUEST_EMAIL or db.scalar(select(User).where(User.email == email)):
        raise DataCheckError("Este e-mail já está cadastrado.", 409)
    user = User(name=body.name, email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _set_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut, summary="Entrar")
def login(body: LoginIn, response: Response, db: DB):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Mensagem única para e-mail inexistente e senha errada (não revela quais e-mails existem).
    if not verify_password(user.password_hash if user else None, body.password):
        raise DataCheckError("E-mail ou senha incorretos.", 401)
    _set_cookie(response, user)
    return user


@router.post("/logout", status_code=204, summary="Sair")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut, summary="Usuário autenticado (401 se for visitante)")
def me(user: LoggedUser):
    return user
