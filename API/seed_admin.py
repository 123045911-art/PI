import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.data.db import SessionLocal
from app.models.user import User
from app.security.hash import hash_password

def seed():
    db: Session = SessionLocal()
    try:
        # Verificar si el admin ya existe
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("Creando usuario admin estático...")
            admin = User(
                username="admin",
                password=hash_password("123456"),
                is_admin=True
            )
            db.add(admin)
            db.commit()
            print("Admin creado: admin / 123456")
        else:
            print("El usuario admin ya existe.")
            # Asegurarse de que sea admin y tenga la contraseña correcta
            admin.is_admin = True
            admin.password = hash_password("123456")
            db.commit()
            print("Credenciales de admin actualizadas para 'admin'.")
                
    except Exception as e:
        print(f"Error al poblar la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
