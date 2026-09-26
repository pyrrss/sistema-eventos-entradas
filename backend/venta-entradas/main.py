from fastapi import FastAPI, Depends, HTTPException, status, Header, Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models
from database import engine, get_db
from datetime import datetime
from auth import verify_api_key, require_admin
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from typing import Optional
import logging
import hashlib
import grpc

from sqlalchemy.exc import IntegrityError

import aforo_client
import aforo_pb2
import cache

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Microservicio Venta Entradas",
    version="1.0.0",
    description=("API REST pública para gestión de asistentes y ventas de entradas. "
                 "Comunica internamente con el servicio gRPC de Aforo."),
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json"
)


def _downgrade_node(node):
    """OpenAPI 3.1 -> 3.0.3: anyOf[..., {type:'null'}] pasa a nullable: true."""
    if isinstance(node, dict):
        out = {k: _downgrade_node(v) for k, v in node.items()}
        anyof = out.get("anyOf")
        if isinstance(anyof, list):
            non_null = [s for s in anyof if not (isinstance(s, dict) and s.get("type") == "null")]
            if len(non_null) != len(anyof) and non_null:
                out.pop("anyOf")
                if len(non_null) == 1 and isinstance(non_null[0], dict):
                    out.update(non_null[0])
                else:
                    out["anyOf"] = non_null
                out["nullable"] = True
        return out
    if isinstance(node, list):
        return [_downgrade_node(x) for x in node]
    return node


def custom_openapi():
    """Spec servido como OpenAPI 3.0.3 (soporte completo de las herramientas de
    contrato — schemathesis <4 no soporta 3.1.0 —) con servers explícitos."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title, version=app.version, description=app.description,
        routes=app.routes,
    )
    schema = _downgrade_node(schema)
    schema["openapi"] = "3.0.3"
    schema["servers"] = [{"url": "http://localhost:8002",
                          "description": "Desarrollo (Docker Compose)"}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
def shutdown_event():
    aforo_client.aforo_client.close()


# ----------- ESQUEMAS -----------

class AsistenteCreate(BaseModel):
    rut: str = Field(..., max_length=20, description="RUT chileno con guion")
    nombre_completo: str = Field(..., max_length=200)
    email: EmailStr


class AsistenteUpdate(BaseModel):
    nombre_completo: str = Field(..., max_length=200)
    email: EmailStr


class AsistenteResponse(BaseModel):
    asistente_id: UUID
    rut: str
    nombre_completo: str
    email: EmailStr
    fecha_registro: datetime

    class Config:
        from_attributes = True


class VentaCreate(BaseModel):
    asistente_id: UUID
    id_seccion_aforo: UUID
    nombre_evento: str = Field(..., max_length=200)
    nombre_seccion: str = Field(..., max_length=200)
    cantidad: int = Field(..., ge=1)


class VentaResponse(BaseModel):
    id: UUID
    venta_id: UUID
    asistente_id: UUID
    asistente_nombre: Optional[str] = None
    id_seccion_aforo: UUID
    nombre_evento: str
    evento_nombre: Optional[str] = None
    nombre_seccion: str
    seccion_nombre: Optional[str] = None
    cantidad: int
    estado: str
    fecha_venta: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EventoResponse(BaseModel):
    id: UUID
    nombre: str
    nombre_lugar: str
    fecha_evento: str


class SeccionResponse(BaseModel):
    id: UUID
    nombre: str
    disponibles: int
    total: int


# ----------- ENDPOINTS v1 -----------

@app.get("/api/v1/health")
def health():
    return {"message": "OK", "version": "1.0.0"}


# ----------- ASISTENTES -----------

@app.post(
    "/api/v1/asistentes",
    response_model=AsistenteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "El RUT ya está registrado"}, 401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada o sin permisos (se requiere rol admin)"}},
)
def crear_asistente(asistente: AsistenteCreate, db: Session = Depends(get_db), _: models.ApiKey = Depends(require_admin)):
    db_asistente = db.query(models.Asistente).filter(models.Asistente.rut == asistente.rut).first()
    if db_asistente:
        raise HTTPException(status_code=400, detail="El RUT ya está registrado.")
    nuevo_asistente = models.Asistente(**asistente.model_dump())
    db.add(nuevo_asistente)
    db.commit()
    db.refresh(nuevo_asistente)
    return nuevo_asistente


@app.get(
    "/api/v1/asistentes",
    response_model=list[AsistenteResponse],
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}},
)
def obtener_asistentes(db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistentes = db.query(models.Asistente).offset(0).limit(50).all()
    return asistentes or []


@app.get(
    "/api/v1/asistentes/{asistente_id}",
    response_model=AsistenteResponse,
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}, 404: {"description": "El asistente no existe"}},
)
def obtener_asistente_uuid(asistente_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El asistente no existe.")
    return asistente


@app.delete(
    "/api/v1/asistentes/{asistente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada o sin permisos (se requiere rol admin)"}, 404: {"description": "El asistente no existe"}},
)
def eliminar_asistente(asistente_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(require_admin)):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El asistente no existe.")
    db.delete(asistente)
    db.commit()
    return None


@app.put(
    "/api/v1/asistentes/{asistente_id}",
    response_model=AsistenteResponse,
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada o sin permisos (se requiere rol admin)"}, 404: {"description": "El asistente no existe"}},
)
def actualizar_asistente(asistente_id: UUID, datos_actualizados: AsistenteUpdate, db: Session = Depends(get_db), _: models.ApiKey = Depends(require_admin)):
    asistente_db = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El asistente con UUID {asistente_id} no existe.")
    asistente_db.nombre_completo = datos_actualizados.nombre_completo
    asistente_db.email = datos_actualizados.email
    db.commit()
    db.refresh(asistente_db)
    return asistente_db


@app.get(
    "/api/v1/asistentes/rut/{rut}",
    response_model=AsistenteResponse,
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}, 404: {"description": "No se encontró un asistente con ese RUT"}},
)
def obtener_asistente_por_rut(rut: str = Path(..., max_length=20, pattern=r"^[0-9.kK\-]+$", description="RUT chileno (dígitos, puntos, guion y K; máx 20 como la columna)"), db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.rut == rut).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No se encontró a un asistente con el RUT: {rut}")
    return asistente


# ----------- EVENTOS Y SECCIONES (comunicación con Aforo mediante grpc) -----------

@app.get(
    "/api/v1/eventos",
    response_model=list[EventoResponse],
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}, 503: {"description": "Servicio de Aforo no disponible"}, 500: {"description": "Error consultando eventos"}},
)
def listar_eventos(_: models.ApiKey = Depends(verify_api_key)):
    cached = cache.get("catalogo:eventos")
    if cached is not None:
        return cached
    try:
        response = aforo_client.aforo_client.list_eventos()
        eventos = [
            EventoResponse(
                id=UUID(e.evento_id),
                nombre=e.nombre_evento,
                nombre_lugar=e.nombre_lugar,
                fecha_evento=e.fecha_evento
            ).model_dump(mode="json") for e in response.eventos
        ]
        cache.set_json("catalogo:eventos", eventos, cache.TTL_EVENTOS)
        return eventos
    except grpc.RpcError as e:
        logger.error(f"gRPC error listando eventos: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="Servicio de Aforo no disponible")
        raise HTTPException(status_code=500, detail="Error consultando eventos")


@app.get(
    "/api/v1/eventos/{evento_id}/secciones",
    response_model=list[SeccionResponse],
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}, 404: {"description": "Evento no encontrado en Aforo"}, 503: {"description": "Servicio de Aforo no disponible"}, 500: {"description": "Error consultando secciones"}},
)
def listar_secciones_evento(evento_id: UUID, _: models.ApiKey = Depends(verify_api_key)):
    clave = f"catalogo:secciones:{evento_id}"
    cached = cache.get(clave)
    if cached is not None:
        return cached
    try:
        response = aforo_client.aforo_client.list_secciones(str(evento_id))
        if not response.evento_existe:
            raise HTTPException(status_code=404, detail="Evento no encontrado en Aforo")
        secciones = [
            SeccionResponse(
                id=UUID(s.seccion_id),
                nombre=s.nombre_seccion,
                disponibles=s.cantidad_entradas_disponibles,
                total=s.capacidad_total
            ).model_dump(mode="json") for s in response.secciones
        ]
        cache.set_json(clave, secciones, cache.TTL_SECCIONES)
        return secciones
    except grpc.RpcError as e:
        logger.error(f"gRPC error listando secciones: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="Servicio de Aforo no disponible")
        raise HTTPException(status_code=500, detail="Error consultando secciones")


# ----------- VENTAS -----------

@app.post(
    "/api/v1/ventas",
    response_model=VentaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Error en datos o servicio de Aforo"},
        401: {"description": "API Key inválida o faltante"},
        403: {"description": "API Key revocada o sin permiso de escritura"},
        404: {"description": "Asistente no encontrado"},
        409: {"description": "Stock insuficiente, o una venta con esa Idempotency-Key está en procesamiento"},
        422: {"description": "Validación, o la Idempotency-Key fue reutilizada con otro payload"},
        503: {"description": "Servicio de Aforo no disponible"},
        504: {"description": "Timeout consultando servicio de Aforo"},
    },
)
def crear_venta(
    venta: VentaCreate,
    db: Session = Depends(get_db),
    registro: models.ApiKey = Depends(require_admin),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == venta.asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=404, detail="Asistente no encontrado")

    hash_body = hashlib.sha256(venta.model_dump_json().encode()).hexdigest()
    candado = None

    if idempotency_key:
        # El candado se scopea por cliente: dos API keys distintas que reenvíen el
        # mismo UUID no comparten candado (impossible replay cross-client).
        clave_idem = hashlib.sha256(f"{registro.key_hash}:{idempotency_key}".encode()).hexdigest()
        candado = models.Idempotencia(clave=clave_idem, hash_body=hash_body)
        db.add(candado)
        try:
            # Postgres bloquea aquí si otro request tiene la misma clave sin commitear.
            db.flush()
        except IntegrityError:
            # clave duplicada: es un retry del mismo intento lógico.
            db.rollback()
            previo = db.query(models.Idempotencia).filter(models.Idempotencia.clave == clave_idem).first()
            if previo is None:
                # El ganador abortó justo ahora; la clave quedó libre.
                raise HTTPException(status_code=409, detail="Venta duplicada abortada; reintente.")
            if previo.hash_body != hash_body:
                raise HTTPException(status_code=422, detail="La Idempotency-Key ya fue usada con otro payload.")
            if previo.venta_id is None:
                raise HTTPException(status_code=409, detail="Una venta con esa Idempotency-Key está en procesamiento.")
            original = db.get(models.Venta, previo.venta_id)
            if original is None:
                raise HTTPException(status_code=500, detail="Clave de idempotencia huérfana.")
            logger.info(f"Replay idempotente: clave={idempotency_key} -> venta={previo.venta_id}")
            return original

    try:
        grpc_response = aforo_client.aforo_client.vender_entrada(str(venta.id_seccion_aforo), venta.cantidad)
    except grpc.RpcError as e:
        logger.error(f"gRPC error vendiendo entrada: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="Servicio de Aforo no disponible")
        if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(status_code=504, detail="Timeout consultando servicio de Aforo")
        raise HTTPException(status_code=500, detail="Error en servicio de Aforo")

    if not grpc_response.exito:
        if "insuficiente" in grpc_response.mensaje.lower() or "stock" in grpc_response.mensaje.lower():
            raise HTTPException(status_code=409, detail=grpc_response.mensaje)
        raise HTTPException(status_code=400, detail=grpc_response.mensaje)

    nueva_venta = models.Venta(
        asistente_id=venta.asistente_id,
        id_seccion_aforo=venta.id_seccion_aforo,
        nombre_evento=venta.nombre_evento,
        nombre_seccion=venta.nombre_seccion,
        cantidad=venta.cantidad,
        estado='VENDIDA'
    )
    db.add(nueva_venta)
    db.flush()
    if candado is not None:
        candado.venta_id = nueva_venta.venta_id
    db.commit()
    db.refresh(nueva_venta)
    # stock en Aforo cambio, se invalida cache de secciones para que
    # proxima lectura cachee stock actualizado
    cache.delete_pattern("catalogo:secciones:*")
    return nueva_venta


@app.get(
    "/api/v1/ventas",
    response_model=list[VentaResponse],
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}},
)
def listar_ventas(db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    ventas = db.query(models.Venta).order_by(models.Venta.fecha_venta.desc()).limit(100).all()
    return ventas or []


@app.get(
    "/api/v1/ventas/{venta_id}",
    response_model=VentaResponse,
    responses={401: {"description": "API Key inválida o faltante"}, 403: {"description": "API Key revocada"}, 404: {"description": "Venta no encontrada"}},
)
def obtener_venta(venta_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    venta = db.query(models.Venta).filter(models.Venta.venta_id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return venta


@app.delete(
    "/api/v1/ventas/{venta_id}",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "La venta ya está anulada, o error en Aforo"},
        401: {"description": "API Key inválida o faltante"},
        403: {"description": "API Key revocada o sin permisos (se requiere rol admin)"},
        404: {"description": "Venta no encontrada"},
        503: {"description": "Servicio de Aforo no disponible"},
        504: {"description": "Timeout consultando servicio de Aforo"},
    },
)
def anular_venta(venta_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(require_admin)):
    venta = db.query(models.Venta).filter(models.Venta.venta_id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado == 'ANULADA':
        raise HTTPException(status_code=400, detail="La venta ya está anulada")

    try:
        grpc_response = aforo_client.aforo_client.anular_entrada(str(venta.id_seccion_aforo), venta.cantidad)
    except grpc.RpcError as e:
        logger.error(f"gRPC error anulando entrada: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="Servicio de Aforo no disponible")
        if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(status_code=504, detail="Timeout consultando servicio de Aforo")
        raise HTTPException(status_code=500, detail="Error en servicio de Aforo")

    if not grpc_response.exito:
        raise HTTPException(status_code=400, detail=grpc_response.mensaje)

    venta.estado = 'ANULADA'
    db.commit()
    db.refresh(venta)
    cache.delete_pattern("catalogo:secciones:*")
    return venta
