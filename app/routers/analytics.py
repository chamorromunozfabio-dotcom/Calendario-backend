from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from ..auth import get_current_user_id
from ..database import STORE
from ..services.analytics import cycle_lengths_from_starts, describe_cycles, estimate_predictions

router = APIRouter()


@router.get("/analytics")
def get_analytics(uid: str = Depends(get_current_user_id)):
    entries = sorted(
        [e for e in STORE.entries.values() if e["user_id"] == uid],
        key=lambda x: x["start_date"],
    )
    starts = [date.fromisoformat(e["start_date"]) for e in entries]
    lengths = cycle_lengths_from_starts(starts)
    stats = describe_cycles(lengths)
    usual = STORE.settings.get(uid, {}).get("usual_cycle_length")
    luteal = STORE.settings.get(uid, {}).get("luteal_phase_length") or 14
    pred = estimate_predictions(starts, usual_cycle_length=usual, luteal=int(luteal))

    history = [
        {"from": a.isoformat(), "to": b.isoformat(), "days": (b - a).days}
        for a, b in zip(sorted(set(starts)), sorted(set(starts))[1:])
    ]
    issues: list[str] = []
    if len(starts) < 2:
        issues.append("Pocos datos: registra al menos 2 inicios de menstruación.")
    if any(L < 15 or L > 60 for L in lengths):
        issues.append("Hay ciclos fuera del rango 15-60 días; verifica fechas.")
    if stats.get("variability") is not None and stats["variability"] >= 7:
        issues.append("Alta variabilidad: las proyecciones tienen mayor incertidumbre.")

    return {
        "cycles": stats,
        "cycle_history": history,
        "prediction": pred,
        "records_used": {"period_starts": len(starts), "cycles": stats["count"]},
        "issues": issues,
        "method": "Media y desviación de duraciones entre inicios válidos (10-90 días). Sin IA ni ML.",
        "limitations": "Muestra pequeña e irregularidades aumentan la incertidumbre. No es diagnóstico ni anticonceptivo.",
    }
