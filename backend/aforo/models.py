from sqlalchemy import Column, String, Integer, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from database import Base


class Evento(Base):
    __tablename__ = "evento"

    evento_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_evento = Column(String(200), nullable=False)
    nombre_lugar = Column(String(200), nullable=False)
    fecha_evento = Column(String(50), nullable=False)

    secciones = relationship("Seccion", back_populates="evento", cascade="all, delete-orphan")


class Seccion(Base):
    __tablename__ = "seccion"

    seccion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evento_id = Column(UUID(as_uuid=True), ForeignKey("evento.evento_id", ondelete="CASCADE"), nullable=False)
    nombre_seccion = Column(String(200), nullable=False)
    capacidad_total = Column(Integer, nullable=False)
    cantidad_entradas_disponibles = Column(Integer, nullable=False, default=0)

    evento = relationship("Evento", back_populates="secciones")

    __table_args__ = (
        CheckConstraint(
            "capacidad_total > 0 AND cantidad_entradas_disponibles >= 0 AND cantidad_entradas_disponibles <= capacidad_total",
            name="seccion_disponibilidad_ok"
        ),
    )