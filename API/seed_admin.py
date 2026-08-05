import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.data.db import SessionLocal
from app.models.user import User
from app.security.hash import hash_password

ADMIN_USERNAME = os.getenv("ADMIN_INITIAL_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD", "visioflow123")

def seed():
    db: Session = SessionLocal()
    try:
        # Verificar si el admin ya existe
        admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if not admin:
            print("Creando usuario admin estático...")
            admin = User(
                username=ADMIN_USERNAME,
                password=hash_password(ADMIN_PASSWORD),
                is_admin=True
            )
            db.add(admin)
            try:
                db.commit()
                print(f"Admin creado: {ADMIN_USERNAME}")
                return
            except IntegrityError:
                # Otra replica gano la carrera e inserto el mismo admin primero;
                # seguimos con la rama de actualizacion en vez de fallar.
                db.rollback()
                admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()

        print("El usuario admin ya existe. Asegurando rol admin y contraseña...")
        admin.is_admin = True
        admin.password = hash_password(ADMIN_PASSWORD)
        db.commit()
        print(f"Credenciales de admin actualizadas: {ADMIN_USERNAME}")

    except Exception as e:
        print(f"Error al poblar la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
