from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# 1. Definir la URL de conexión
DATABASE_URL = os.getenv(
	"DATABASE_URL",
	"postgresql://admin:visioflow123@postgres:5432/contador_personas"
)

# 2. Creación de motor de conexión
engine = create_engine(DATABASE_URL)

# 3. Preparación de gestionador de sesiones
SesionLocal = sessionmaker(
	autocommit = False,
	autoflush = False,
	bind = engine
)

# 4. Base declarativa para los modelos
Base = declarative_base()

# 5. Obtener sesiones de cada petición
def get_db():
	db = SesionLocal()
	try:
		yield db
	finally:
		db.close()	