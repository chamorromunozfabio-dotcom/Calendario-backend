"""Cálculos estadísticos independientes de Groq. Sin diagnósticos."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, pstdev


def cycle_lengths_from_starts(starts: list[date]) -> list[int]:
    ordered = sorted(set(starts))
    return [(b - a).days for a, b in zip(ordered, ordered[1:]) if 10 <= (b - a).days <= 90]


def describe_cycles(lengths: list[int]) -> dict:
    if not lengths:
        return {"count": 0, "avg": None, "min": None, "max": None, "variability": None, "regularity": "insuficiente"}
    avg = round(mean(lengths), 1)
    var = round(pstdev(lengths), 1) if len(lengths) >= 2 else 0.0
    if len(lengths) < 2:
        reg = "insuficiente"
    elif var <= 2:
        reg = "regular"
    elif var <= 6:
        reg = "algo_variable"
    else:
        reg = "irregular"
    return {"count": len(lengths), "avg": avg, "min": min(lengths), "max": max(lengths), "variability": var, "regularity": reg}


def estimate_predictions(
    period_starts: list[date],
    usual_cycle_length: int | None = None,
    luteal: int = 14,
) -> dict:
    """Estima próximo periodo / ventana fértil / ovulación como ORIENTACIÓN.

    Nunca exacto. Requiere >=2 inicios válidos o duración habitual conocida.
    """
    lengths = cycle_lengths_from_starts(period_starts)
    stats = describe_cycles(lengths)
    warnings: list[str] = []
    avg: float | None = None
    cycles_used = stats["count"]
    method = "sin_datos"

    if cycles_used >= 2:
        avg = float(stats["avg"])
        method = f"media_de_{cycles_used}_ciclos"
    elif usual_cycle_length:
        avg = float(usual_cycle_length)
        cycles_used = 0
        method = "duracion_habitual_declarada"
        warnings.append("Estimación basada en tu duración habitual, no en historial suficiente.")
    else:
        return {
            "method": method, "cycles_used": 0, "avg_cycle_length": None,
            "variability_days": None, "regularity": "insuficiente",
            "next_period_start": None, "next_period_end": None,
            "fertile_from": None, "fertile_to": None, "ovulation_date": None,
            "confidence": "insuficiente",
            "warnings": ["Registra al menos 2 inicios de menstruación para estimar."],
            "disclaimer": "Orientativo. No usar como anticonceptivo ni para garantizar días seguros.",
        }

    last = max(period_starts)
    avg_int = int(round(avg))
    if not (15 <= avg_int <= 60):
        warnings.append("Duración media fuera de rango habitual; revisa tus registros.")
    if stats["variability"] is not None and stats["variability"] >= 7:
        warnings.append("Ciclos irregulares: la incertidumbre es alta.")

    next_start = last + timedelta(days=avg_int)
    next_end = next_start + timedelta(days=4)  # ventana orientativa
    ovulation = next_start - timedelta(days=luteal)
    fertile_from = ovulation - timedelta(days=5)
    fertile_to = ovulation + timedelta(days=1)

    confidence = "baja" if cycles_used < 3 or (stats["variability"] or 0) > 4 else ("media" if cycles_used < 6 else "alta")
    if method.startswith("duracion_habitual"):
        confidence = "baja"

    return {
        "method": method, "cycles_used": cycles_used, "avg_cycle_length": round(avg, 1),
        "variability_days": stats["variability"], "regularity": stats["regularity"],
        "next_period_start": next_start.isoformat(), "next_period_end": next_end.isoformat(),
        "fertile_from": fertile_from.isoformat(), "fertile_to": fertile_to.isoformat(),
        "ovulation_date": ovulation.isoformat(), "confidence": confidence,
        "warnings": warnings,
        "disclaimer": "Estimaciones orientativas, no certezas médicas. No usar como método anticonceptivo.",
    }
