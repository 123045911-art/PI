from fastapi import status, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

# Seguridad HTTP Basic
security = HTTPBasic()

def verificar_peticion(credenciales: HTTPBasicCredentials = Depends(security)):
    usuario_correcto = secrets.compare_digest(credenciales.username,"admin")
    contrasena_correcta = secrets.compare_digest(credenciales.password,"visioflow123")

    if not(usuario_correcto and contrasena_correcta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CREDENCIALES NO VÁLIDAS."
        )
    return credenciales.username