from sqlalchemy import Column, String, DateTime, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base


class ApiKey(Base):
    __tablename__ = "api_key"

    key = Column(String(64), primary_key=True)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Asistente(Base):
    __tablename__ = "asistente"

    asistente_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rut = Column(String(20), nullable=False, unique=True)
    nombre_completo = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False)
    
    # server_default=func.now() le dice a Postgres que use CURRENT_TIMESTAMP automáticamente
    fecha_registro = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relación bidireccional con Venta
    ventas = relationship("Venta", back_populates="asistente", cascade="all, delete-orphan")


class Venta(Base):
    __tablename__ = "venta"

    venta_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # index=True crea automáticamente el índice idx_venta_asistente que pediste en SQL
    asistente_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("asistente.asistente_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    fecha_venta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    estado = Column(String(20), nullable=False)
    
    # ¡OJO AQUÍ! Esto NO es una ForeignKey en SQLAlchemy porque la tabla Seccion 
    # vive en otra base de datos (en el microservicio de Aforo). 
    # Solo guardamos el UUID como referencia cruzada.
    id_seccion_aforo = Column(UUID(as_uuid=True), nullable=False)
    
    nombre_evento = Column(String(200), nullable=False)
    nombre_seccion = Column(String(200), nullable=False)

    # Relación de vuelta hacia Asistente
    asistente = relationship("Asistente", back_populates="ventas")

    __table_args__ = (
        CheckConstraint(
            "estado IN ('VENDIDA', 'ANULADA')", 
            name="check_estado_venta"
        ),
    )

    @property
    def id(self):
        return self.venta_id

    @property
    def created_at(self):
        return self.fecha_venta

    @property
    def asistente_nombre(self):
        return self.asistente.nombre_completo if self.asistente else None

    @property
    def evento_nombre(self):
        return self.nombre_evento

    @property
    def seccion_nombre(self):
        return self.nombre_seccion