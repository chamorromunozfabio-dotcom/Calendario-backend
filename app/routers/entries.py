from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_id
from ..database import STORE
from ..schemas import EntryCreate, EntryUpdate, LogCreate

router = APIRouter()


def _overlap(uid: str, start: str, end: str | None, ignore_id: str | None = None) -> bool:
    ns, ne = start, end or start
    for e in STORE.entries.values():
        if e["user_id"] != uid or e["id"] == ignore_id:
            continue
        s, en = e["start_date"], e.get("end_date") or e["start_date"]
        # intersección de rangos (cadenas ISO yyyy-mm-dd comparables)
        if ns <= en and s <= ne:
            return True
    return False


@router.get("/entries")
def list_entries(limit: int = 100, offset: int = 0, uid: str = Depends(get_current_user_id)):
    limit = max(1, min(limit, 200))
    items = sorted(
        [e for e in STORE.entries.values() if e["user_id"] == uid],
        key=lambda x: x["start_date"], reverse=True,
    )
    return {"items": items[offset:offset + limit], "total": len(items)}


@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, uid: str = Depends(get_current_user_id)):
    start, end = body.start_date.isoformat(), body.end_date.isoformat() if body.end_date else None
    if _overlap(uid, start, end):
        raise HTTPException(status_code=409, detail="El rango se solapa con otro periodo registrado. Revisa las fechas.")
    eid = str(uuid4())
    entry = {
        "id": eid, "user_id": uid, "start_date": start, "end_date": end,
        "flow_intensity": body.flow_intensity, "pain_level": body.pain_level,
        "notes": body.notes, "source": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    STORE.entries[eid] = entry
    return entry


@router.patch("/entries/{entry_id}")
def patch_entry(entry_id: str, body: EntryUpdate, uid: str = Depends(get_current_user_id)):
    e = STORE.entries.get(entry_id)
    if not e or e["user_id"] != uid:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    data = body.model_dump(exclude_unset=True)
    ns = data.get("start_date").isoformat() if data.get("start_date") else e["start_date"]
    ne = data.get("end_date").isoformat() if data.get("end_date") else e.get("end_date")
    if ne is not None and ne < ns:
        raise HTTPException(status_code=422, detail="end_date no puede ser anterior a start_date")
    if _overlap(uid, ns, ne, ignore_id=entry_id):
        raise HTTPException(status_code=409, detail="El rango se solapa con otro periodo registrado.")
    e["start_date"] = ns
    e["end_date"] = ne
    for k in ("flow_intensity", "pain_level", "notes"):
        if k in data:
            e[k] = data[k]
    e["updated_at"] = datetime.now(timezone.utc).isoformat()
    return e


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str, uid: str = Depends(get_current_user_id)):
    e = STORE.entries.get(entry_id)
    if not e or e["user_id"] != uid:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    del STORE.entries[entry_id]
    return {"deleted": True}


# ---- daily logs ----
@router.get("/logs")
def list_logs(limit: int = 100, offset: int = 0, uid: str = Depends(get_current_user_id)):
    items = sorted([l for l in STORE.logs.values() if l["user_id"] == uid], key=lambda x: x["log_date"], reverse=True)
    return {"items": items[offset:offset + limit], "total": len(items)}


@router.post("/logs", status_code=201)
def upsert_log(body: LogCreate, uid: str = Depends(get_current_user_id)):
    lid = str(uuid4())
    # un log por fecha: actualizar si existe
    for existing in STORE.logs.values():
        if existing["user_id"] == uid and existing["log_date"] == body.log_date.isoformat():
            existing.update(body.model_dump())
            existing["log_date"] = body.log_date.isoformat()
            return existing
    rec = {"id": lid, "user_id": uid, **body.model_dump()}
    rec["log_date"] = body.log_date.isoformat()
    STORE.logs[lid] = rec
    return rec


@router.delete("/logs/{log_id}")
def delete_log(log_id: str, uid: str = Depends(get_current_user_id)):
    l = STORE.logs.get(log_id)
    if not l or l["user_id"] != uid:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    del STORE.logs[log_id]
    return {"deleted": True}
