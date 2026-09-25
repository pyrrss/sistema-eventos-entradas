import hashlib
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader 
from sqlalchemy.orm import Session

import models
from database import get_db

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-KEY", auto_error=False, scheme_name="ApiKeyAuth")

ROL_ADMIN = "admin"
ROL_LECTURA = "lectura"

_CHALLENGE = {"WWW-Authenticate": 'ApiKey realm="ventana-entradas"'}

def hash_api_key(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()

def verify_api_key(
    api_key: str | None = Depends(API_KEY_HEADER),
    db: Session = Depends(get_db)
) -> models.ApiKey:
    """ Autentica la solicitud, devuelve el registro de la key o lanza 401 / 403."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida",
            headers=_CHALLENGE,
        )

    registro = db.get(models.ApiKey, hash_api_key(api_key))
    if registro is None:
        logger.warning("Fallo en la autenticación: API Key desconocida")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
            headers=_CHALLENGE,
        )

    if not registro.activo:
        logger.warning("Autorización rechazada: API Key revocada (%s)", registro.nombre)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key revocada",
        )
    
    return registro

def require_admin(registro:models.ApiKey = Depends(verify_api_key)) -> models.ApiKey:
    """Autoriza operaciones de escritura: exige rol admin, sino 403."""
    if registro.rol != ROL_ADMIN:
        logger.warning("Autorización denegada: '%s' con rol '%s' intentó escribir", registro.nombre, registro.rol)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La API Key no tiene permiso para esta operación",
        )
    return registro
