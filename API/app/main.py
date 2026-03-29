from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.data.db import engine
from app.router import areas, auth, dashboard, events, heatmap, state

app = FastAPI(
    title="Visio Flow API",
    description="API central: PostgreSQL, eventos desde Flask, consumo desde Laravel.",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
def health():
    return {"status": "ok", "service": "visio-flow-api"}


@app.get("/db-test")
def db_test():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return {"status": "ok", "db": "conectado"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/")
def root():
    return {"message": "Visio Flow API", "docs": "/docs"}


app.include_router(auth.router)
app.include_router(areas.router)
app.include_router(events.router)
app.include_router(state.router)
app.include_router(heatmap.router)
app.include_router(dashboard.router)
