"""Calendario mensual: combina días registrados + estimaciones calculadas."""
from __future__ import annotations

import calendar as calmod
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user_id
from ..database import STORE
from ..services.analytics import estimate_predictions

router = APIRouter()


def _iso(d: date) -> str:
    return d.isoformat()


@router.get("/calendar")
def get_calendar(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    uid: str = Depends(get_current_user_id),
):
    try:
        first = date(year, month, 1)
    except ValueError:
        raise HTTPException(status_code=422, detail="Mes inválido")
    _, days_in_month = calmod.monthrange(year, month)

    entries = [e for e in STORE.entries.values() if e["user_id"] == uid]
    logs_by_date = {l["log_date"]: l for l in STORE.logs.values() if l["user_id"] == uid}

    # días con menstruación registrada (rango start..end)
    bleeding: set[str] = set()
    for e in entries:
        s = date.fromisoformat(e["start_date"])
        en = date.fromisoformat(e["end_date"]) if e.get("end_date") else s
        d = s
        while d <= en:
            bleeding.add(_iso(d))
            d += timedelta(days=1)

    # estimaciones (solo si hay datos)
    starts = [date.fromisoformat(e["start_date"]) for e in entries]
    usual = STORE.settings.get(uid, {}).get("usual_cycle_length")
    pred = estimate_predictions(starts, usual_cycle_length=usual) if starts or usual else None
    est_period: set[str] = set()
    fertile: set[str] = set()
    ovulation: str | None = None
    if pred and pred.get("next_period_start"):
        ps = date.fromisoformat(pred["next_period_start"])
        pe = date.fromisoformat(pred["next_period_end"])
        d = ps
        while d <= pe:
            est_period.add(_iso(d))
            d += timedelta(days=1)
        f, t = date.fromisoformat(pred["fertile_from"]), date.fromisoformat(pred["fertile_to"])
        d = f
        while d <= t:
            fertile.add(_iso(d))
            d += timedelta(days=1)
        ovulation = pred["ovulation_date"]

    # cuadrícula completa Lun-Dom (iso semanas): días adyacentes incluidos
    grid: list[dict] = []
    monday_offset = (first.weekday())  # 0=lunes
    cursor = first - timedelta(days=monday_offset)
    for _ in range(42):
        iso = _iso(cursor)
        in_month = cursor.month == month
        kinds: list[str] = []
        symbols: list[str] = []
        if iso in bleeding:
            kinds.append("period_registered"); symbols.append("●")
        elif iso in est_period and in_month:
            kinds.append("period_estimated"); symbols.append("○")
        if ovulation == iso:
            kinds.append("ovulation_estimated"); symbols.append("★")
        elif iso in fertile:
            kinds.append("fertile_estimated"); symbols.append("◐")
        if iso in logs_by_date:
            kinds.append("has_log"); symbols.append("◆")
        grid.append({"date": iso, "in_month": in_month, "weekday": cursor.weekday(), "kinds": kinds, "symbols": symbols})
        cursor += timedelta(days=1)
        if cursor.month != month and cursor.weekday() == 0 and len([g for g in grid if g["in_month"]]) >= days_in_month:
            break

    return {
        "year": year, "month": month, "days_in_month": days_in_month,
        "leap_year": calmod.isleap(year),
        "grid": grid,
        "legend": {
            "period_registered": "● Menstruación registrada (confirmada por ti)",
            "period_estimated": "○ Menstruación estimada (cálculo, no confirmada)",
            "fertile_estimated": "◐ Ventana fértil estimada (orientativa)",
            "ovulation_estimated": "★ Ovulación estimada (orientativa)",
            "has_log": "◆ Día con registro de síntomas/ánimo",
        },
        "prediction": pred,
        "disclaimer": "Las estimaciones son orientativas, no certezas médicas ni método anticonceptivo.",
    }
