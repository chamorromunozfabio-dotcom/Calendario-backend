from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends

from ..auth import get_current_user_id
from ..database import STORE
from ..schemas import ConsentCreate, CycleSettingsUpdate, ProfileUpdate

router = APIRouter()


def _profile(uid: str) -> dict:
    p = STORE.profiles.get(uid, {})
    s = STORE.settings.get(uid, {})
    n = STORE.notif.get(uid, {})
    return {
        "id": uid,
        "display_name": p.get("display_name"),
        "birth_year": p.get("birth_year"),
        "timezone": p.get("timezone", "America/Bogota"),
        "cycle_settings": {
            "usual_cycle_length": s.get("usual_cycle_length"),
            "usual_period_length": s.get("usual_period_length"),
            "luteal_phase_length": s.get("luteal_phase_length", 14),
            "last_period_start": s.get("last_period_start"),
            "birth_control": s.get("birth_control", False),
            "onboarding_completed": s.get("onboarding_completed", False),
        },
        "notification_preferences": {
            "period_reminder": n.get("period_reminder", True),
            "fertile_reminder": n.get("fertile_reminder", False),
            "wellness_messages": n.get("wellness_messages", True),
        },
    }


@router.get("/profile")
def get_profile(uid: str = Depends(get_current_user_id)):
    STORE.profiles.setdefault(uid, {})
    STORE.settings.setdefault(uid, {})
    return _profile(uid)


@router.patch("/profile")
def patch_profile(body: ProfileUpdate, uid: str = Depends(get_current_user_id)):
    p = STORE.profiles.setdefault(uid, {})
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            p[k] = v
    p["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _profile(uid)


@router.get("/settings")
def get_settings(uid: str = Depends(get_current_user_id)):
    return STORE.settings.get(uid, {})


@router.patch("/settings")
def patch_settings(body: CycleSettingsUpdate, uid: str = Depends(get_current_user_id)):
    s = STORE.settings.setdefault(uid, {})
    for k, v in body.model_dump(exclude_unset=True).items():
        s[k] = v.isoformat() if hasattr(v, "isoformat") and v is not None else v
    return s


@router.post("/consent")
def post_consent(body: ConsentCreate, uid: str = Depends(get_current_user_id)):
    rec = {"id": str(uuid4()), **body.model_dump(), "created_at": datetime.now(timezone.utc).isoformat()}
    STORE.consents.setdefault(uid, []).append(rec)
    return rec


@router.get("/export")
def export_data(uid: str = Depends(get_current_user_id)):
    """Exportación de datos propios (portabilidad, Ley 1581)."""
    return {
        "profile": STORE.profiles.get(uid, {}),
        "settings": STORE.settings.get(uid, {}),
        "entries": [e for e in STORE.entries.values() if e["user_id"] == uid],
        "logs": [l for l in STORE.logs.values() if l["user_id"] == uid],
        "favorites": STORE.favorites.get(uid, []),
        "consents": STORE.consents.get(uid, []),
    }


@router.delete("/account")
def delete_account(uid: str = Depends(get_current_user_id)):
    """Eliminación de cuenta: borra todos los datos del store (documentado)."""
    STORE.profiles.pop(uid, None)
    STORE.settings.pop(uid, None)
    for k in [k for k, v in STORE.entries.items() if v["user_id"] == uid]:
        STORE.entries.pop(k)
    for k in [k for k, v in STORE.logs.items() if v["user_id"] == uid]:
        STORE.logs.pop(k)
    STORE.predictions.pop(uid, None)
    STORE.recommendations.pop(uid, None)
    STORE.favorites.pop(uid, None)
    STORE.consents.pop(uid, None)
    STORE.notif.pop(uid, None)
    for k in [k for k, v in STORE.links.items() if v["owner_id"] == uid or v["partner_id"] == uid]:
        STORE.links.pop(k)
    for k in [k for k, v in STORE.invitations.items() if v["owner_id"] == uid]:
        STORE.invitations[k]["revoked"] = True
    return {"deleted": True}
