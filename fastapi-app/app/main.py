# Importaciones
from fastapi import FastAPI
from app.data.db import engine
from app.data import areas, area_events, area_state, heatmap_points

# Tablas de BD
areas.Base.metadata.create_all(bind = engine)
area_events.Base.metadata.create_all(bind = engine)
area_state.Base.metadata.create_all(bind = engine)
heatmap_points.Base.metadata.create_all(bind = engine)

# Instancia del servidor
app = FastAPI(
    title="API Visioflow",
    version="1.0"
)