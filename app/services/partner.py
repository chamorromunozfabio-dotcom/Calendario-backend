"""Lógica de invitaciones de pareja: tokens seguros, expiración, revocación."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def new_invite_code() -> str:
    return "ccy_" + secrets.token_urlsafe(24)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def is_invitation_valid(inv: dict, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    exp = inv.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if inv.get("revoked"):
        return False, "revocada"
    if exp and now > exp:
        return False, "expirada"
    if inv.get("uses", 0) >= inv.get("max_uses", 1):
        return False, "agotada"
    return True, "ok"


def default_expires(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=max(1, min(hours, 168)))
