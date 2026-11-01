from datetime import datetime, timezone
from typing import Optional


def iso(dt: Optional[datetime]) -> Optional[str]:
    """Datas vindas do SQLite chegam sem fuso; todas são UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def fmt_local(value: Optional[str]) -> str:
    """ISO (UTC) -> 'dd/mm/aaaa hh:mm' em UTC, para relatórios."""
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M") + " UTC"
    except ValueError:
        return value
