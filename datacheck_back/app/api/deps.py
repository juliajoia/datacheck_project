from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DataCheckError
from app.core.security import COOKIE_NAME, read_session_token
from app.database import get_db
from app.models import User

DB = Annotated[Session, Depends(get_db)]

# O login é opcional. Quem não entra usa o usuário "visitante" (compartilhado por todos os visitantes);
# quem entra tem análises próprias, invisíveis para visitantes e para outras contas.
GUEST_EMAIL = "local@datacheck.local"
NO_LOGIN_HASH = "!"  # valor que nunca corresponde a uma senha


def session_user(db: DB, session: Annotated[Optional[str], Cookie(alias=COOKIE_NAME)] = None) -> Optional[User]:
    user_id = read_session_token(session) if session else None
    user = db.get(User, user_id) if user_id else None
    return user if user and user.email != GUEST_EMAIL else None


def current_user(db: DB, logged: Annotated[Optional[User], Depends(session_user)]) -> User:
    if logged:
        return logged
    guest = db.scalar(select(User).where(User.email == GUEST_EMAIL))
    if guest:
        return guest
    guest = User(name="Visitante", email=GUEST_EMAIL, password_hash=NO_LOGIN_HASH)
    db.add(guest)
    try:
        db.commit()
    except IntegrityError:  # outra requisição criou primeiro
        db.rollback()
        guest = db.scalar(select(User).where(User.email == GUEST_EMAIL))
    return guest


def logged_user(logged: Annotated[Optional[User], Depends(session_user)]) -> User:
    if not logged:
        raise DataCheckError("Você não está conectado.", 401)
    return logged


CurrentUser = Annotated[User, Depends(current_user)]
LoggedUser = Annotated[User, Depends(logged_user)]
