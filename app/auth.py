"""Dependencias de autenticación. No confía en user_id del cliente."""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


def _unauthorized(msg: str = "No autenticado") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)


def get_current_user_id(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Extrae el user_id desde el JWT de Supabase Auth.

    En producción verifica la firma HS256 con SUPABASE_JWT_SECRET.
    En modo test/desarrollo sin JWT secret, acepta un UUID como Bearer
    (solo para pruebas locales, documentado).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized()
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized()

    secret = settings.SUPABASE_JWT_SECRET.strip()
    if secret:
        try:
            payload = jwt.decode(
                token, secret, algorithms=["HS256"], options={"verify_aud": False}
            )
        except jwt.PyJWTError:
            raise _unauthorized("Token inválido o expirado")
        sub = str(payload.get("sub", "")).strip()
        if not sub:
            raise _unauthorized()
        return sub

    # Sin secreto (test/dev): el token debe ser un UUID válido.
    try:
        return str(uuid.UUID(token))
    except ValueError:
        raise _unauthorized("Token inválido")
