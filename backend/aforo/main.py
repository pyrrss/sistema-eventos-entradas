import grpc
import os
import time
from concurrent import futures
import logging
import uuid

from sqlalchemy import update

import aforo_pb2
import aforo_pb2_grpc

from database import SessionLocal
from models import Evento, Seccion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inyección de latencia para el experimento de competencia 6 (docs/experimento.md).
# LATENCIA_MS=0 (default) => comportamiento normal del servicio.
LATENCIA_MS = int(os.getenv("LATENCIA_MS", "0"))


class AforoService(aforo_pb2_grpc.AforoServiceServicer):
    def ListEventos(self, request, context):
        db = SessionLocal()
        try:
            eventos = db.query(Evento).order_by(Evento.fecha_evento).all()
            return aforo_pb2.ListEventosResponse(
                eventos=[
                    aforo_pb2.EventoInfo(
                        evento_id=str(e.evento_id),
                        nombre_evento=e.nombre_evento,
                        nombre_lugar=e.nombre_lugar,
                        fecha_evento=str(e.fecha_evento),
                    )
                    for e in eventos
                ]
            )
        finally:
            db.close()

    def GetSeccion(self, request, context):
        db = SessionLocal()
        try:
            seccion = db.query(Seccion).filter(Seccion.seccion_id == uuid.UUID(request.seccion_id)).first()
            if not seccion:
                return aforo_pb2.SeccionResponse(existe=False)
            return aforo_pb2.SeccionResponse(
                seccion_id=str(seccion.seccion_id),
                evento_id=str(seccion.evento_id),
                nombre_seccion=seccion.nombre_seccion,
                capacidad_total=seccion.capacidad_total,
                cantidad_entradas_disponibles=seccion.cantidad_entradas_disponibles,
                existe=True
            )
        finally:
            db.close()

    def ListSecciones(self, request, context):
        db = SessionLocal()
        try:
            evento = db.query(Evento).filter(Evento.evento_id == uuid.UUID(request.evento_id)).first()
            if not evento:
                return aforo_pb2.ListSeccionesResponse(evento_existe=False)
            secciones_info = []
            for s in evento.secciones:
                secciones_info.append(aforo_pb2.SeccionInfo(
                    seccion_id=str(s.seccion_id),
                    nombre_seccion=s.nombre_seccion,
                    capacidad_total=s.capacidad_total,
                    cantidad_entradas_disponibles=s.cantidad_entradas_disponibles
                ))
            return aforo_pb2.ListSeccionesResponse(secciones=secciones_info, evento_existe=True)
        finally:
            db.close()

    def VenderEntrada(self, request, context):
        if LATENCIA_MS:
            time.sleep(LATENCIA_MS / 1000)  # fault injection: simula Aforo lento
        db = SessionLocal()
        try:
            sid = uuid.UUID(request.seccion_id)
            if request.cantidad < 1:
                return aforo_pb2.VenderEntradaResponse(
                    exito=False,
                    mensaje="Cantidad debe ser >= 1",
                    disponibles_restantes=0
                )
            # Chequeo + descuento atómicos en una sola sentencia: Postgres
            # re-evalúa el WHERE tras el lock de la fila, así dos ventas
            # concurrentes no pueden sobreventer (ni perder stock con 0/negativos).
            res = db.execute(
                update(Seccion)
                .where(Seccion.seccion_id == sid,
                       Seccion.cantidad_entradas_disponibles >= request.cantidad)
                .values(cantidad_entradas_disponibles=Seccion.cantidad_entradas_disponibles - request.cantidad)
            )
            if res.rowcount == 0:
                seccion = db.query(Seccion).filter(Seccion.seccion_id == sid).first()
                if seccion is None:
                    return aforo_pb2.VenderEntradaResponse(
                        exito=False,
                        mensaje="Sección no encontrada",
                        disponibles_restantes=0
                    )
                return aforo_pb2.VenderEntradaResponse(
                    exito=False,
                    mensaje=f"Stock insuficiente. Disponibles: {seccion.cantidad_entradas_disponibles}",
                    disponibles_restantes=seccion.cantidad_entradas_disponibles
                )
            db.commit()
            seccion = db.query(Seccion).filter(Seccion.seccion_id == sid).first()
            return aforo_pb2.VenderEntradaResponse(
                exito=True,
                mensaje="Venta registrada",
                disponibles_restantes=seccion.cantidad_entradas_disponibles
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Error en VenderEntrada: {e}")
            return aforo_pb2.VenderEntradaResponse(
                exito=False,
                mensaje=f"Error interno: {str(e)}",
                disponibles_restantes=0
            )
        finally:
            db.close()

    def AnularEntrada(self, request, context):
        db = SessionLocal()
        try:
            sid = uuid.UUID(request.seccion_id)
            if request.cantidad < 1:
                return aforo_pb2.AnularEntradaResponse(
                    exito=False,
                    mensaje="Cantidad debe ser >= 1",
                    disponibles_restantes=0
                )
            # Atómico: solo reintegra si el total no excede la capacidad.
            # Sin esto, una cantidad negativa "anularía" entradas
            # (robo silencioso de stock).
            res = db.execute(
                update(Seccion)
                .where(Seccion.seccion_id == sid,
                       (Seccion.cantidad_entradas_disponibles + request.cantidad) <= Seccion.capacidad_total)
                .values(cantidad_entradas_disponibles=Seccion.cantidad_entradas_disponibles + request.cantidad)
            )
            if res.rowcount == 0:
                seccion = db.query(Seccion).filter(Seccion.seccion_id == sid).first()
                if seccion is None:
                    return aforo_pb2.AnularEntradaResponse(
                        exito=False,
                        mensaje="Sección no encontrada",
                        disponibles_restantes=0
                    )
                return aforo_pb2.AnularEntradaResponse(
                    exito=False,
                    mensaje=f"No se pueden anular más entradas de las vendidas. Capacidad total: {seccion.capacidad_total}",
                    disponibles_restantes=seccion.cantidad_entradas_disponibles
                )
            db.commit()
            seccion = db.query(Seccion).filter(Seccion.seccion_id == sid).first()
            return aforo_pb2.AnularEntradaResponse(
                exito=True,
                mensaje="Anulación registrada",
                disponibles_restantes=seccion.cantidad_entradas_disponibles
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Error en AnularEntrada: {e}")
            return aforo_pb2.AnularEntradaResponse(
                exito=False,
                mensaje=f"Error interno: {str(e)}",
                disponibles_restantes=0
            )
        finally:
            db.close()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    aforo_pb2_grpc.add_AforoServiceServicer_to_server(AforoService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info("Servidor gRPC Aforo iniciado en puerto 50051")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()