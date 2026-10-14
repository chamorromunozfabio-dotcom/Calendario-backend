from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import ai, analytics, calendar, entries, partner, profile

settings = get_settings()

app = FastAPI(title="CCycle API", version="1.0.0", description="API de CCycle: seguimiento menstrual, estimaciones y bienestar.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Log mínimo sin datos sensibles
    if isinstance(exc, Exception) and hasattr(exc, "status_code"):
        return JSONResponse(
            status_code=getattr(exc, "status_code", 500),
            content={"detail": str(getattr(exc, "detail", "Error")), "code": "api_error"},
        )
    return JSONResponse(status_code=500, content={"detail": "Error interno", "code": "internal"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "ccycle-backend", "env": settings.ENVIRONMENT}


@app.get("/")
def root():
    return {"service": "CCycle API", "docs": "/docs", "health": "/health"}


app.include_router(profile.router, prefix="/api/v1", tags=["profile"])
app.include_router(entries.router, prefix="/api/v1", tags=["entries"])
app.include_router(calendar.router, prefix="/api/v1", tags=["calendar"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(ai.router, prefix="/api/v1", tags=["ai"])
app.include_router(partner.router, prefix="/api/v1", tags=["partner"])
