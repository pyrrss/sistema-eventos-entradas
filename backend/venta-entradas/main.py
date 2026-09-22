from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from typing import Literal, Optional
import logging
import grpc

import aforo_client
import aforo_pb2

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Microservicio Venta Entradas",
    version="1.0.0",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
    openapi_url="/v1/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(api_key: str = Depends(API_KEY_HEADER), db: Session = Depends(get_db)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida",
            headers={"WWW-Authenticate": "APIKey"},
        )
    key_record = db.query(models.ApiKey).filter(models.ApiKey.key == api_key, models.ApiKey.activo == True).first()
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o inactiva",
            headers={"WWW-Authenticate": "APIKey"},
        )
    return key_record


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
    estado: Literal['VENDIDA', 'ANULADA'] = 'VENDIDA'


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

@app.get("/v1/health")
def health():
    return {"message": "OK", "version": "1.0.0"}


# ----------- ASISTENTES -----------

@app.post("/v1/asistentes", response_model=AsistenteResponse, status_code=status.HTTP_201_CREATED)
def crear_asistente(asistente: AsistenteCreate, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    db_asistente = db.query(models.Asistente).filter(models.Asistente.rut == asistente.rut).first()
    if db_asistente:
        raise HTTPException(status_code=400, detail="El RUT ya está registrado.")
    nuevo_asistente = models.Asistente(**asistente.model_dump())
    db.add(nuevo_asistente)
    db.commit()
    db.refresh(nuevo_asistente)
    return nuevo_asistente


@app.get("/v1/asistentes", response_model=list[AsistenteResponse])
def obtener_asistentes(db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistentes = db.query(models.Asistente).offset(0).limit(50).all()
    return asistentes or []


@app.get("/v1/asistentes/{asistente_id}", response_model=AsistenteResponse)
def obtener_asistente_uuid(asistente_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El asistente no existe.")
    return asistente


@app.delete("/v1/asistentes/{asistente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_asistente(asistente_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El asistente no existe.")
    db.delete(asistente)
    db.commit()
    return None


@app.put("/v1/asistentes/{asistente_id}", response_model=AsistenteResponse)
def actualizar_asistente(asistente_id: UUID, datos_actualizados: AsistenteUpdate, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente_db = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()
    if not asistente_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El asistente con UUID {asistente_id} no existe.")
    asistente_db.nombre_completo = datos_actualizados.nombre_completo
    asistente_db.email = datos_actualizados.email
    db.commit()
    db.refresh(asistente_db)
    return asistente_db


@app.get("/v1/asistentes/rut/{rut}", response_model=AsistenteResponse)
def obtener_asistente_por_rut(rut: str, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.rut == rut).first()
    if not asistente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No se encontró a un asistente con el RUT: {rut}")
    return asistente


# ----------- EVENTOS Y SECCIONES (Proxy a gRPC Aforo) -----------

@app.get("/v1/eventos", response_model=list[EventoResponse])
def listar_eventos(_: models.ApiKey = Depends(verify_api_key)):
    try:
        from database import SessionLocal
        from models import Evento
        db = SessionLocal()
        try:
            eventos = db.query(Evento).all()
            return [
                EventoResponse(
                    id=e.evento_id,
                    nombre=e.nombre_evento,
                    nombre_lugar=e.nombre_lugar,
                    fecha_evento=e.fecha_evento
                ) for e in eventos
            ]
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error listando eventos: {e}")
        raise HTTPException(status_code=500, detail="Error consultando eventos")


@app.get("/v1/eventos/{evento_id}/secciones", response_model=list[SeccionResponse])
def listar_secciones_evento(evento_id: UUID, _: models.ApiKey = Depends(verify_api_key)):
    try:
        response = aforo_client.aforo_client.list_secciones(str(evento_id))
        if not response.evento_existe:
            raise HTTPException(status_code=404, detail="Evento no encontrado en Aforo")
        return [
            SeccionResponse(
                id=UUID(s.seccion_id),
                nombre=s.nombre_seccion,
                disponibles=s.cantidad_entradas_disponibles,
                total=s.capacidad_total
            ) for s in response.secciones
        ]
    except grpc.RpcError as e:
        logger.error(f"gRPC error listando secciones: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(status_code=503, detail="Servicio de Aforo no disponible")
        raise HTTPException(status_code=500, detail="Error consultando secciones")


# ----------- VENTAS -----------

@app.post("/v1/ventas", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
def crear_venta(venta: VentaCreate, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == venta.asistente_id).first()
    if not asistente:
        raise HTTPException(status_code=404, detail="Asistente no encontrado")

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
        estado=venta.estado
    )
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)
    return nueva_venta


@app.get("/v1/ventas", response_model=list[VentaResponse])
def listar_ventas(db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    ventas = db.query(models.Venta).order_by(models.Venta.fecha_venta.desc()).limit(100).all()
    return ventas or []


@app.get("/v1/ventas/{venta_id}", response_model=VentaResponse)
def obtener_venta(venta_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
    venta = db.query(models.Venta).filter(models.Venta.venta_id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return venta


@app.delete("/v1/ventas/{venta_id}", status_code=status.HTTP_200_OK)
def anular_venta(venta_id: UUID, db: Session = Depends(get_db), _: models.ApiKey = Depends(verify_api_key)):
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
    return venta