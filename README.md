# CCycle — Backend

API del seguimiento menstrual y bienestar. Python + FastAPI + Pydantic + Uvicorn.
La IA (Groq) se usa **solo aquí**, nunca desde el frontend.

## Desarrollo local

```powershell
py -m pip install -r requirements.txt
Copy-Item .env.example .env   # edítalo con tus valores
py -m pytest tests -q
py -m uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/health y http://localhost:8000/docs
```

## Variables de entorno

| Variable | Ejemplo | Descripción |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `production` (`testing` solo tests) |
| `FRONTEND_URL` | `http://localhost:5173` | URL del frontend |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos separados por coma (sin `*` en prod) |
| `SUPABASE_URL` | `https://tu-proyecto.supabase.co` | Proyecto Supabase |
| `SUPABASE_ANON_KEY` | `tu-anon-key` | Clave publicable |
| `SUPABASE_JWT_SECRET` | `tu-jwt-secret` | Para verificar los JWT de Supabase Auth |
| `GROQ_API_KEY` | *(vacío en dev)* | Solo servidor. Sin key la IA usa respaldo local |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Debe existir en tu cuenta de Groq |
| `GROQ_TIMEOUT_SECONDS` | `20` | Timeout de llamadas a Groq |
| `GROQ_MAX_TOKENS` | `600` | Tope de tokens por respuesta |
| `AI_DAILY_LIMIT` | `20` | Límite diario de peticiones IA por usuaria |

## Desplegar en Render (paso a paso)

1. Entra a [render.com](https://render.com) e inicia sesión con tu cuenta de GitHub.
2. **New → Web Service →** selecciona el repositorio `Calendario-backend`.
3. Configura:
   - **Runtime**: Python 3 · **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
   - Plan Free (o el que prefieras).
4. En **Environment** añade cada variable de la tabla (usa la URL de Vercel
   en `FRONTEND_URL` y `BACKEND_CORS_ORIGINS`, ej. `https://tu-app.vercel.app`).
5. **Create Web Service**. Tu API quedará en `https://tu-servicio.onrender.com`.
6. Verifica `https://tu-servicio.onrender.com/health` → `{"status":"ok"}`.
7. Pega esa URL como `VITE_API_URL` en el proyecto del frontend (Vercel) y redespliega.

> Nota: el plan Free de Render "duerme" el servicio sin tráfico; la primera
> petición puede tardar ~1 min. Es normal.
