"""Almacén en memoria (desarrollo/tests) con interfaz lista para Supabase.

En producción con SUPABASE_URL + SECRET se usaría el cliente oficial;
aquí se mantiene un store por proceso para que la API sea funcional y
testeable sin credenciales, manteniendo aislamiento por user_id en backend.
"""
from __future__ import annotations

from typing import Any


class MemoryStore:
    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.settings: dict[str, dict[str, Any]] = {}
        self.entries: dict[str, dict[str, Any]] = {}  # id -> entry (con user_id)
        self.logs: dict[str, dict[str, Any]] = {}
        self.predictions: dict[str, list[dict[str, Any]]] = {}
        self.recommendations: dict[str, list[dict[str, Any]]] = {}
        self.favorites: dict[str, list[dict[str, Any]]] = {}
        self.invitations: dict[str, dict[str, Any]] = {}  # id -> inv
        self.links: dict[str, dict[str, Any]] = {}
        self.consents: dict[str, list[dict[str, Any]]] = {}
        self.notif: dict[str, dict[str, Any]] = {}
        self.ai_usage: dict[str, list[float]] = {}

    def reset(self) -> None:
        self.__init__()


STORE = MemoryStore()
