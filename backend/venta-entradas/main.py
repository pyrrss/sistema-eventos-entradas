from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from typing import Literal

models.Base.metadata.create_all(bind=engine)        # Esto crea las tablas en la base de datos físicamente si no existen

app = FastAPI(
    title="Microservicio Venta Entradas",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependencia: Genera una sesión de BD segura
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------- ESQUEMAS (sirve para validar los tipos que se usan :v) -------------
class AsistenteCreate(BaseModel):
    rut: str = Field(..., max_length=20, description="RUT chileno con guion")
    nombre_completo: str = Field(..., max_length=200)
    email: EmailStr # Valida automáticamente que tenga formato de correo (@)

class AsistenteResponse(AsistenteCreate):
    asistente_id: UUID
    fecha_registro: datetime

    class Config:
        # Permite que Pydantic lea directamente el objeto de SQLAlchemy
        from_attributes = True 

class VentaCreate(BaseModel):
    asistente_id: UUID
    id_seccion_aforo: UUID
    nombre_evento: str = Field(..., max_length=200)
    nombre_seccion: str = Field(..., max_length=200)
    # Restringimos a que solo acepte estos dos valores exactos
    estado: Literal['VENDIDA', 'ANULADA'] = 'VENDIDA' 

class VentaResponse(VentaCreate):
    venta_id: UUID
    fecha_venta: datetime

    class Config:
        from_attributes = True

# ----------- ENDPOINTS -------------

@app.get("/api/health")
def health():
    """
    Health, simplemente eso.
    """
    return {"message": "OK"}


@app.post("/api/asistentes", response_model=AsistenteResponse, status_code=status.HTTP_201_CREATED)
def crear_asistente(asistente: AsistenteCreate, db: Session = Depends(get_db)):
    """
    Crea un asistente. 
    """

    db_asistente = db.query(models.Asistente).filter(models.Asistente.rut == asistente.rut).first()

    if db_asistente:
        raise HTTPException(
            status_code=400, 
            detail="El RUT ya está registrado."
        )

    nuevo_asistente = models.Asistente(**asistente.model_dump())       # Instancia ORM, desempaqueta el esquema Pydantic

    db.add(nuevo_asistente)
    db.commit()
    db.refresh(nuevo_asistente)

    return nuevo_asistente

@app.get("/api/asistentes", response_model=list[AsistenteResponse])
def obtener_asistentes(db: Session = Depends(get_db)):
    """
    Obtener todos los asistentes.
    """

    asistentes = db.query(models.Asistente).offset(0).limit(50).all()

    if not asistentes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No existen asistentes."
        )

    return asistentes

@app.get("/api/asistentes/{asistente_id}", response_model=AsistenteResponse)
def obtener_asistente_uuid(asistente_id: UUID, db: Session = Depends(get_db)):
    """
    Obtenemos un asistente dado su ID.
    """
    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()

    if not asistente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="El asistente no existe."
        )

    return asistente_id

@app.get("/api/asistentes/rut/{rut}", response_model=AsistenteResponse)
def obtener_asistente_por_rut(rut: str, db: Session = Depends(get_db)):
    """
    Obtener el asistente a partir de su RUT.
    """

    asistente = db.query(models.Asistente).filter(models.Asistente.rut == rut).first()

    if not asistente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró a un asistente con el RUT: {rut}"
        )

    return asistente

@app.delete("/api/asistentes/{asistente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_asistente(asistente_id: UUID, db: Session = Depends(get_db)):
    """
    Permite eliminar un asistente.
    """

    asistente = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id).first()

    if not asistente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El asistente no existe."
        )

    db.delete(asistente)
    db.commit()

    return None

@app.put("/api/asistentes/{asistente_id}", response_model=AsistenteResponse)
def actualizar_asistente(asistente_id: UUID, datos_actualizados: AsistenteCreate, db: Session = Depends(get_db)):
    """
    Actualiza los datos de un asistente.
    """

    asistente_db = db.query(models.Asistente).filter(models.Asistente.asistente_id == asistente_id)

    if not asistente_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El asistente con UUID {asistente_id} no existe."
        )

    asistente_db.rut = datos_actualizados.rut
    asistente_db.nombre_completo = datos_actualizados.nombre_completo
    asistente_db.email = datos_actualizados.email

    db.commit()
    db.refresh(asistente_db)

    return asistente_db
