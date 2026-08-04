import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.data.db import engine
from app.models import Base
from app.router import areas, auth, dashboard, events, heatmap, live, state, users

# ── Configuración de entorno ───────────────────────────────────────────────────
ENV = os.getenv("APP_ENV", "production").lower()
IS_DEV = ENV in ("development", "dev", "local")

# ── Rate Limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ── Orígenes CORS permitidos ───────────────────────────────────────────────────
# En producción, listar explícitamente los orígenes permitidos.
ALLOWED_ORIGINS: list[str] = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8081,http://127.0.0.1:8081,http://localhost:5000,http://127.0.0.1:5000,http://localhost:19006,http://127.0.0.1:19006",
).split(",")

# ── Instancia FastAPI ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Visio Flow API",
    description="API central: PostgreSQL, eventos desde Flask, consumo desde cliente móvil/web.",
    version="1.0.0",
    # Deshabilitar documentación interactiva en producción
    docs_url="/docs" if IS_DEV else None,
    redoc_url="/redoc" if IS_DEV else None,
    openapi_url="/openapi.json" if IS_DEV else None,
)


@app.on_event("startup")
def create_missing_tables() -> None:
    Base.metadata.create_all(bind=engine)

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
    # Excluir objetos ValueError internos para que el mensaje siempre sea JSON
    # serializable y el cliente reciba 422 en lugar de un error 500.
    safe_errors = [
        {key: value for key, value in error.items() if key not in {"ctx", "input"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


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
app.include_router(live.router)
