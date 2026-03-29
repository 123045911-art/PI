from fastapi import Header, HTTPException, status

def verify_admin(x_is_admin: bool = Header(False, alias="X-Is-Admin")):
    if not x_is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: solo para administradores."
        )
