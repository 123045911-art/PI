# Importaciones
from fastapi import FastAPI
from app.data.db import engine
from app.data import areas as AreasDB, area_events as AreaEventsDB, area_state as AreaStateDB, heatmap_points as HeatmapPointsDB
from app.router import areas, cameras, dashboard, events_heatmap, system

# Tablas de BD
AreasDB.Base.metadata.create_all(bind = engine)
AreaEventsDB.Base.metadata.create_all(bind = engine)
AreaStateDB.Base.metadata.create_all(bind = engine)
HeatmapPointsDB.Base.metadata.create_all(bind = engine)

# Instancia del servidor
app = FastAPI(
    title="API Visioflow",
    version="1.0"
)

app.include_router(system.router)
app.include_router(cameras.router)
app.include_router(areas.router)
app.include_router(events_heatmap.router)
app.include_router(dashboard.router)