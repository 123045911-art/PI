import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.router import areas, auth, dashboard, events, heatmap, state, users

# ── Configuración de entorno ───────────────────────────────────────────────────
ENV = os.getenv("APP_ENV", "production").lower()
IS_DEV = ENV in ("development", "dev", "local")

# ── Rate Limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ── Orígenes CORS permitidos ───────────────────────────────────────────────────
# En producción, listar explícitamente los orígenes permitidos.
ALLOWED_ORIGINS: list[str] = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8085,http://localhost:5000",
).split(",")

# ── Instancia FastAPI ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Visio Flow API",
    description="API central: PostgreSQL, eventos desde Flask, consumo desde Laravel.",
    version="1.0.0",
    # Deshabilitar documentación interactiva en producción
    docs_url="/docs" if IS_DEV else None,
    redoc_url="/redoc" if IS_DEV else None,
    openapi_url="/openapi.json" if IS_DEV else None,
)

# ── Middlewares ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Manejadores de error globales ──────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# ── Endpoints de diagnóstico ───────────────────────────────────────────────────

@app.get("/health", tags=["health"],
         summary="Health check del servicio (público)")
def health():
    """Endpoint de health check para Docker. No expone información sensible."""
    return {"status": "ok", "service": "visio-flow-api"}


@app.get("/", tags=["root"])
def root():
    return {"message": "Visio Flow API"}


# ELIMINADO: /db-test — exponía el estado de la base de datos sin autenticación.
# Para diagnósticos de base de datos usar herramientas internas con acceso directo.

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(areas.router)
app.include_router(events.router)
app.include_router(state.router)
app.include_router(heatmap.router)
app.include_router(dashboard.router)
app.include_router(users.router)
