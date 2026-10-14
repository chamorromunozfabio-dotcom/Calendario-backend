"""Integración Groq exclusiva en backend, con fallbacks locales seguros."""
from __future__ import annotations

import time

ALLOWED_MODELS = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
}

FALLBACK_RECOMMENDATIONS = [
    ("Hidratación suave", "Bebe agua a lo largo del día y ten una botella cerca; la sed intensa o mareos ameritan consulta profesional.", "hidratación"),
    ("Descanso reparador", "Mantén horarios regulares de sueño y pausas cortas; si el dolor interfiere con tu vida diaria, busca atención profesional.", "descanso"),
    ("Movimiento amable", "Caminatas suaves o estiramientos de 10-20 min si te apetece; evita exigirte y escucha a tu cuerpo.", "autocuidado"),
    ("Comida equilibrada", "Incluye frutas, verduras, proteína y fibra según tu apetito, sin restricciones estrictas.", "alimentación"),
]

FALLBACK_MESSAGES = {
    "tranquilo": ["Respira despacio: estás haciendo lo suficiente por hoy.", "Puedes ir a tu ritmo; lo pequeño también cuenta."],
    "alegre": ["Que hoy encuentres un momento lindo, aunque sea breve.", "Tu energía merece cosas que te hagan sonreír."],
    "motivador": ["Paso a paso: tu constancia al cuidarte ya es un logro.", "Sigue: cada registro te ayuda a conocerte mejor."],
    "reflexivo": ["¿Qué necesita tu cuerpo hoy? Escucharlo también es cuidarte.", "Observar tus ciclos es una forma de conocerte."],
}

SYSTEM_GUARDRAILS = (
    "Eres un asistente de bienestar general en español. "
    "Prohibido: diagnosticar, prescribir medicamentos/hormonas/dosis/suplementos, "
    "recomendar remedios para inducir menstruación u ovulación, o dar fechas exactas. "
    "Incluye siempre un recordatorio breve de buscar atención profesional ante síntomas intensos."
)


def resolve_model(configured: str) -> str:
    configured = (configured or "").strip()
    if configured in ALLOWED_MODELS:
        return configured
    return "llama-3.3-70b-versatile"


def groq_available(api_key: str) -> bool:
    return bool(api_key and api_key.strip() and api_key.strip() != "tu-api-key")


def generate_with_groq(api_key: str, model: str, messages: list[dict], timeout_s: int, max_tokens: int) -> str | None:
    """Llama a Groq con timeout. Devuelve texto o None si falla. Nunca loguea la clave."""
    try:
        from groq import Groq
    except Exception:
        return None
    try:
        client = Groq(api_key=api_key, timeout=timeout_s)
        resp = client.chat.completions.create(
            model=resolve_model(model),
            messages=messages,
            max_tokens=max(50, min(max_tokens, 800)),
            temperature=0.7,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text[:2000] if text else None
    except Exception:
        return None


def check_rate_limit(store: dict, user_id: str, daily_limit: int) -> bool:
    """True si puede continuar. Ventana simple de 24h en memoria."""
    now = time.time()
    arr = [t for t in store.get(user_id, []) if now - t < 86400]
    store[user_id] = arr
    if len(arr) >= daily_limit:
        return False
    arr.append(now)
    return True
