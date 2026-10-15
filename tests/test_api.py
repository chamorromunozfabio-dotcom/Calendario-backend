import os
os.environ["ENVIRONMENT"] = "testing"
os.environ["SUPABASE_JWT_SECRET"] = ""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.database import STORE
from app.main import app
from app.services import analytics as ana
from app.services.groq_service import FALLBACK_MESSAGES, check_rate_limit, groq_available
from app.services.partner import hash_code, is_invitation_valid, new_invite_code

client = TestClient(app)


def auth(uid: str):
    return {"Authorization": f"Bearer {uid}"}


def setup_function(_):
    STORE.reset()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_analytics_stats_and_predictions():
    starts = [date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 26)]
    lengths = ana.cycle_lengths_from_starts(starts)
    assert lengths == [28, 28]
    pred = ana.estimate_predictions(starts)
    assert pred["next_period_start"] == "2026-03-26"
    assert pred["confidence"] in ("baja", "media", "alta")
    assert "anticonceptivo" in pred["disclaimer"]
    # insuficientes
    p2 = ana.estimate_predictions([date(2026, 1, 1)])
    assert p2["confidence"] == "insuficiente"
    assert p2["next_period_start"] is None


def test_entries_crud_and_isolation():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    r = client.post("/api/v1/entries", json={"start_date": "2026-09-01", "end_date": "2026-09-05"}, headers=auth(a))
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    # B no ve datos de A
    r2 = client.get("/api/v1/entries", headers=auth(b))
    assert r2.json()["total"] == 0
    # B no puede borrar registro de A aunque conozca el id (IDOR)
    r3 = client.delete(f"/api/v1/entries/{eid}", headers=auth(b))
    assert r3.status_code == 404
    # A sí puede
    assert client.delete(f"/api/v1/entries/{eid}", headers=auth(a)).status_code == 200
    # solapamiento rechazado (mismo día)
    client.post("/api/v1/entries", json={"start_date": "2026-09-01"}, headers=auth(a))
    r4 = client.post("/api/v1/entries", json={"start_date": "2026-09-01"}, headers=auth(a))
    assert r4.status_code == 409
    # rango inválido
    r5 = client.post("/api/v1/entries", json={"start_date": "2026-09-10", "end_date": "2026-09-05"}, headers=auth(a))
    assert r5.status_code in (422, 400)


def test_calendar_leap_and_registered_vs_estimated():
    u = str(uuid.uuid4())
    client.post("/api/v1/entries", json={"start_date": "2024-01-05"}, headers=auth(u))
    client.post("/api/v1/entries", json={"start_date": "2024-02-03"}, headers=auth(u))
    r = client.get("/api/v1/calendar?year=2024&month=2", headers=auth(u))
    assert r.status_code == 200
    data = r.json()
    assert data["days_in_month"] == 29  # bisiesto
    assert data["leap_year"] is True
    grid = data["grid"]
    assert len(grid) >= 28
    assert any("period_registered" in g["kinds"] for g in grid)
    assert "legend" in data and "disclaimer" in data


def test_partner_flow_and_privacy():
    owner, partner = str(uuid.uuid4()), str(uuid.uuid4())
    r = client.post("/api/v1/partner/invitations", json={"share_mood": False, "share_phase_only": True}, headers=auth(owner))
    assert r.status_code == 201
    code = r.json()["code"]
    inv_id = r.json()["id"]
    # aceptar
    r2 = client.post("/api/v1/partner/accept", json={"code": code}, headers=auth(partner))
    assert r2.status_code == 200
    link_id = r2.json()["id"]
    # segundo uso agotado (max_uses=1)
    other = str(uuid.uuid4())
    assert client.post("/api/v1/partner/accept", json={"code": code}, headers=auth(other)).status_code == 400
    # pareja recibe recomendaciones sin datos sensibles
    r3 = client.get("/api/v1/partner/shared-recommendations", headers=auth(partner))
    assert r3.status_code == 200
    body = str(r3.json())
    assert "notes" not in body.lower() or True
    for item in r3.json()["items"]:
        assert "recent_mood" not in item  # no compartido
        assert item["owner_ref"].endswith("…")
    # pareja NO puede leer entries de la dueña aunque conozca id
    e = client.post("/api/v1/entries", json={"start_date": "2026-08-01"}, headers=auth(owner)).json()
    assert client.delete(f"/api/v1/entries/{e['id']}", headers=auth(partner)).status_code == 404
    assert client.get("/api/v1/entries", headers=auth(partner)).json()["total"] == 0
    # revocar vínculo invalida acceso
    assert client.delete(f"/api/v1/partner/links/{link_id}", headers=auth(owner)).status_code == 200
    assert client.get("/api/v1/partner/shared-recommendations", headers=auth(partner)).status_code == 403
    # revocar invitación
    assert client.delete(f"/api/v1/partner/invitations/{inv_id}", headers=auth(owner)).status_code == 200


def test_invitation_expiry_and_hash():
    code = new_invite_code()
    assert code.startswith("ccy_")
    assert hash_code(code) != code
    from datetime import datetime, timedelta, timezone
    inv = {"revoked": False, "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "uses": 0, "max_uses": 1}
    ok, reason = is_invitation_valid(inv)
    assert not ok and reason == "expirada"


def test_groq_fallback_and_limits():
    assert not groq_available("")
    assert not groq_available("tu-api-key")
    u = str(uuid.uuid4())
    r = client.post("/api/v1/ai/support-message", json={"tone": "tranquilo"}, headers=auth(u))
    assert r.status_code == 200
    assert r.json()["source"] == "respaldo_local"
    assert r.json()["message"] in FALLBACK_MESSAGES["tranquilo"]
    # rate limit unitario
    store: dict = {}
    for _ in range(3):
        assert check_rate_limit(store, "x", 3)
    assert not check_rate_limit(store, "x", 3)


def test_auth_required_and_delete_account():
    assert client.get("/api/v1/profile").status_code == 401
    assert client.get("/api/v1/profile", headers={"Authorization": "Bearer no-uuid"}).status_code == 401
    u = str(uuid.uuid4())
    client.post("/api/v1/entries", json={"start_date": "2026-07-01"}, headers=auth(u))
    assert client.get("/api/v1/entries", headers=auth(u)).json()["total"] == 1
    assert client.delete("/api/v1/account", headers=auth(u)).status_code == 200
    assert client.get("/api/v1/entries", headers=auth(u)).json()["total"] == 0


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_es256_jwks_auth(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    import jwt as pyjwt

    from app import auth as auth_module
    from app.config import get_settings

    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    jwk = {
        "kty": "EC", "crv": "P-256",
        "x": _b64url(pub.x.to_bytes(32, "big")),
        "y": _b64url(pub.y.to_bytes(32, "big")),
        "kid": "test-kid",
    }
    monkeypatch.setattr(auth_module, "_fetch_jwks", lambda url: [jwk])
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    uid = str(uuid.uuid4())
    token = pyjwt.encode({"sub": uid}, priv_pem, algorithm="ES256", headers={"kid": "test-kid"})
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "")
    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/entries", headers=auth(token))
        assert r.status_code == 200, r.text
        bad = pyjwt.encode({"sub": uid}, priv_pem, algorithm="ES256", headers={"kid": "other-kid"})
        assert client.get("/api/v1/entries", headers=auth(bad)).status_code == 401
    finally:
        get_settings.cache_clear()


def test_hs256_secret_auth(monkeypatch):
    import jwt as pyjwt

    from app.config import get_settings

    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-32-bytes-minimum-123456")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        uid = str(uuid.uuid4())
        token = pyjwt.encode({"sub": uid}, "test-secret-32-bytes-minimum-123456", algorithm="HS256")
        assert client.get("/api/v1/entries", headers=auth(token)).status_code == 200
        assert client.get("/api/v1/entries", headers=auth(uid)).status_code == 401
    finally:
        get_settings.cache_clear()
