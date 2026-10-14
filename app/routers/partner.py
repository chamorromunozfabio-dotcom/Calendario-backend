"""Vinculación opcional con pareja: permisos explícitos y revocación inmediata."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_id
from ..database import STORE
from ..schemas import InvitationAccept, InvitationCreate
from ..services.groq_service import FALLBACK_RECOMMENDATIONS
from ..services.partner import default_expires, hash_code, is_invitation_valid, new_invite_code

router = APIRouter()


@router.post("/partner/invitations", status_code=201)
def create_invitation(body: InvitationCreate, uid: str = Depends(get_current_user_id)):
    code = new_invite_code()
    inv = {
        "id": str(uuid4()), "owner_id": uid,
        "code_hash": hash_code(code),
        "expires_at": default_expires(body.expires_hours).isoformat(),
        "max_uses": body.max_uses, "uses": 0, "revoked": False,
        "share_mood": body.share_mood,
        "share_phase_only": body.share_phase_only,
        "share_symptoms": body.share_symptoms,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    STORE.invitations[inv["id"]] = inv
    # El código en claro SOLO se devuelve una vez a la dueña para compartir.
    return {**inv, "code": code, "code_hash": "oculto"}


@router.get("/partner/invitations")
def list_invitations(uid: str = Depends(get_current_user_id)):
    items = [i for i in STORE.invitations.values() if i["owner_id"] == uid]
    return {"items": [{**i, "code_hash": "oculto"} for i in items]}


@router.delete("/partner/invitations/{inv_id}")
def revoke_invitation(inv_id: str, uid: str = Depends(get_current_user_id)):
    inv = STORE.invitations.get(inv_id)
    if not inv or inv["owner_id"] != uid:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    inv["revoked"] = True
    return {"revoked": True}


@router.post("/partner/accept")
def accept_invitation(body: InvitationAccept, uid: str = Depends(get_current_user_id)):
    target = None
    for inv in STORE.invitations.values():
        if inv["code_hash"] == hash_code(body.code):
            target = inv
            break
    if target is None:
        # Respuesta genérica para no enumerar códigos
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    if target["owner_id"] == uid:
        raise HTTPException(status_code=400, detail="No puedes aceptar tu propia invitación")
    ok, _ = is_invitation_valid(target)
    if not ok:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    # ¿ya existe vínculo?
    for link in STORE.links.values():
        if link["owner_id"] == target["owner_id"] and link["partner_id"] == uid:
            raise HTTPException(status_code=409, detail="Ya existe un vínculo activo")
    target["uses"] += 1
    lid = str(uuid4())
    link = {
        "id": lid, "owner_id": target["owner_id"], "partner_id": uid,
        "invitation_id": target["id"],
        "share_mood": target["share_mood"],
        "share_phase_only": target["share_phase_only"],
        "share_symptoms": target["share_symptoms"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    STORE.links[lid] = link
    return link


@router.get("/partner/links")
def my_links(uid: str = Depends(get_current_user_id)):
    mine = [l for l in STORE.links.values() if l["owner_id"] == uid or l["partner_id"] == uid]
    return {"items": mine}


@router.delete("/partner/links/{link_id}")
def delete_link(link_id: str, uid: str = Depends(get_current_user_id)):
    link = STORE.links.get(link_id)
    # Solo la dueña puede revocar (la pareja ve, no borra)
    if not link or link["owner_id"] != uid:
        raise HTTPException(status_code=404, detail="Vínculo no encontrado")
    del STORE.links[link_id]
    return {"revoked": True}


@router.get("/partner/shared-recommendations")
def shared_recommendations(uid: str = Depends(get_current_user_id)):
    """Vista de pareja: solo info autorizada. Nunca notas, síntomas detallados ni fechas exactas por defecto."""
    links = [l for l in STORE.links.values() if l["partner_id"] == uid]
    if not links:
        raise HTTPException(status_code=403, detail="Sin vínculos activos")
    out = []
    for link in links:
        owner = link["owner_id"]
        # Fase orientativa (sin fechas exactas si share_phase_only)
        tips = [
            "Pregunta cómo se siente hoy y qué apoyo prefiere.",
            "Ofrece ayuda práctica (compras, descanso, espacio tranquilo).",
            "Evita minimizar el dolor; valida su experiencia.",
        ]
        item: dict = {
            "owner_ref": link["owner_id"][:8] + "…",  # sin identificadores completos
            "phase_only": link["share_phase_only"],
            "tips": tips,
            "local_support": [f"• {t}: {b}" for t, b, _ in FALLBACK_RECOMMENDATIONS[:2]],
        }
        if link.get("share_mood"):
            moods = [l.get("mood") for l in STORE.logs.values() if l["user_id"] == owner and l.get("mood")]
            item["recent_mood"] = moods[-1] if moods else None
        out.append(item)
    return {"items": out}
