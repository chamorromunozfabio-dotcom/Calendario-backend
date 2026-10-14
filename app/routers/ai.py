from __future__ import annotations

import random
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user_id
from ..config import get_settings
from ..database import STORE
from ..schemas import AIRecommendRequest, AISupportRequest, FavoriteCreate
from ..services.groq_service import (
    FALLBACK_MESSAGES,
    FALLBACK_RECOMMENDATIONS,
    SYSTEM_GUARDRAILS,
    check_rate_limit,
    generate_with_groq,
    groq_available,
)

router = APIRouter()

EDU = {
    "bienestar": "Fase orientativa: prioriza descanso y escucha corporal.",
    "nutricion": "Información educativa general, sin dietas estrictas ni suplementos.",
    "descanso": "Higiene del sueño: horarios regulares, luz natural de día y pantallas bajas de noche.",
    "educativa": "El ciclo típico incluye fase menstrual, folicular, ovulación y lútea; varía entre personas.",
}


@router.post("/ai/recommendations")
def ai_recommendations(body: AIRecommendRequest, uid: str = Depends(get_current_user_id)):
    s = get_settings()
    if not check_rate_limit(STORE.ai_usage, uid, s.AI_DAILY_LIMIT):
        raise HTTPException(status_code=429, detail="Límite diario de IA alcanzado. Intenta mañana.")
    free = (body.free_text or "")[:500]
    context_min = f"focus={body.focus}; cycle_day={body.cycle_day}"
    text: str | None = None
    source = "respaldo_local"
    if groq_available(s.GROQ_API_KEY):
        text = generate_with_groq(
            s.GROQ_API_KEY, s.GROQ_MODEL,
            [
                {"role": "system", "content": SYSTEM_GUARDRAILS},
                {"role": "user", "content": f"Da 3 recomendaciones generales de {body.focus} ({context_min}). Nota usuaria: {free}. Máx 120 palabras, español, sin diagnósticos ni prescripciones."},
            ],
            s.GROQ_TIMEOUT_SECONDS, s.GROQ_MAX_TOKENS,
        )
        if text:
            source = "groq"
    if not text:
        picks = random.sample(FALLBACK_RECOMMENDATIONS, k=3)
        text = "\n".join(f"• {t}: {b}" for t, b, _ in picks)
    rec = {
        "id": str(uuid4()), "user_id": uid, "kind": body.focus,
        "title": f"Recomendaciones de {body.focus}",
        "body": text + "\n\nSi tienes síntomas intensos o persistentes, busca atención profesional.",
        "reason": f"Generado para focus={body.focus} con contexto mínimo autorizado ({context_min}).",
        "source": source, "created_at": datetime.now(timezone.utc).isoformat(),
        "education": EDU.get(body.focus, ""),
    }
    STORE.recommendations.setdefault(uid, []).append(rec)
    return rec


@router.post("/ai/support-message")
def ai_support(body: AISupportRequest, uid: str = Depends(get_current_user_id)):
    s = get_settings()
    if not check_rate_limit(STORE.ai_usage, uid, s.AI_DAILY_LIMIT):
        raise HTTPException(status_code=429, detail="Límite diario de IA alcanzado. Intenta mañana.")
    text: str | None = None
    source = "respaldo_local"
    if groq_available(s.GROQ_API_KEY):
        text = generate_with_groq(
            s.GROQ_API_KEY, s.GROQ_MODEL,
            [
                {"role": "system", "content": SYSTEM_GUARDRAILS},
                {"role": "user", "content": f"Escribe un mensaje breve (máx 40 palabras) tono {body.tone}. Estado compartido: {body.mood}. Nota: {(body.free_text or '')[:300]}. No asumas experiencias universales."},
            ],
            s.GROQ_TIMEOUT_SECONDS, 200,
        )
        if text:
            source = "groq"
    if not text:
        text = random.choice(FALLBACK_MESSAGES.get(body.tone, FALLBACK_MESSAGES["tranquilo"]))
    return {"message": text, "tone": body.tone, "source": source, "disclaimer": "Apoyo general, no sustituye ayuda profesional."}


@router.get("/messages/favorites")
def list_favorites(uid: str = Depends(get_current_user_id)):
    return {"items": STORE.favorites.get(uid, [])}


@router.post("/messages/favorites", status_code=201)
def add_favorite(body: FavoriteCreate, uid: str = Depends(get_current_user_id)):
    rec = {"id": str(uuid4()), "message": body.message, "tone": body.tone,
           "created_at": datetime.now(timezone.utc).isoformat()}
    STORE.favorites.setdefault(uid, []).append(rec)
    return rec


@router.delete("/messages/favorites/{fav_id}")
def del_favorite(fav_id: str, uid: str = Depends(get_current_user_id)):
    arr = STORE.favorites.get(uid, [])
    for i, f in enumerate(arr):
        if f["id"] == fav_id:
            arr.pop(i)
            return {"deleted": True}
    raise HTTPException(status_code=404, detail="No encontrado")


@router.get("/recommendations")
def list_recommendations(uid: str = Depends(get_current_user_id)):
    return {"items": list(reversed(STORE.recommendations.get(uid, [])))}
