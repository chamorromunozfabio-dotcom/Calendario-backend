"""Dependencias de autenticación. No confía en user_id del cliente."""
from __future__ import annotations

import json
import time
import urllib.request
import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


def _unauthorized(msg: str = "No autenticado") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)


_JWKS_CACHE: dict = {"keys": [], "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 600


def _fetch_jwks(jwks_url: str) -> list:
    """Descarga las claves públicas (JWKS) con caché en memoria de 10 min."""
    now = time.time()
    if _JWKS_CACHE["keys"] and now - _JWKS_CACHE["fetched_at"] < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE["keys"]
    req = urllib.request.Request(jwks_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        raise _unauthorized("Token inválido o expirado")
    keys = data.get("keys", []) if isinstance(data, dict) else []
    if keys:
        _JWKS_CACHE["keys"] = keys
        _JWKS_CACHE["fetched_at"] = now
    return keys


def _verify_es256_jwks(token: str, jwks_url: str) -> dict:
    """Verifica un JWT ES256 (Supabase signing keys) contra el JWKS público."""
    try:
        kid = jwt.get_unverified_header(token).get("kid", "")
    except jwt.PyJWTError:
        raise _unauthorized("Token inválido o expirado")
    for key in _fetch_jwks(jwks_url):
        if key.get("kid") == kid and key.get("kty") == "EC":
            public_key = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(key))
            try:
                return jwt.decode(token, public_key, algorithms=["ES256"], options={"verify_aud": False})
            except jwt.PyJWTError:
                raise _unauthorized("Token inválido o expirado")
    raise _unauthorized("Token inválido o expirado")


def get_current_user_id(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Extrae el user_id desde el JWT de Supabase Auth.

    Soporta dos formatos de firma:
    - ES256 (Supabase signing keys): verifica contra el JWKS público
      (`SUPABASE_URL/auth/v1/.well-known/jwks.json`).
    - HS256 (secreto heredado): verifica con SUPABASE_JWT_SECRET.
    En modo test/desarrollo sin JWT secret ni URL, acepta un UUID como
    Bearer (solo para pruebas locales, documentado).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized()
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized()

    secret = settings.SUPABASE_JWT_SECRET.strip()
    supabase_url = settings.SUPABASE_URL.strip()

    if token.count(".") == 2 and (secret or supabase_url):
        try:
            alg = jwt.get_unverified_header(token).get("alg", "")
        except jwt.PyJWTError:
            raise _unauthorized("Token inválido o expirado")
        if alg == "ES256" and supabase_url:
            jwks_url = supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
            payload = _verify_es256_jwks(token, jwks_url)
            sub = str(payload.get("sub", "")).strip()
            if not sub:
                raise _unauthorized()
            return sub
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
        raise _unauthorized("Token inválido o expirado")

    if secret:
        raise _unauthorized("Token inválido o expirado")

    # Sin secreto ni URL (test/dev): el token debe ser un UUID válido.
    try:
        return str(uuid.UUID(token))
    except ValueError:
        raise _unauthorized("Token inválido")
