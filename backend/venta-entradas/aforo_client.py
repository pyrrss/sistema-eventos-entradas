import grpc
import logging
import os

import aforo_pb2
import aforo_pb2_grpc

logger = logging.getLogger(__name__)

AFORO_HOST = os.getenv("AFORO_GRPC_HOST", "aforo")
AFORO_PORT = os.getenv("AFORO_GRPC_PORT", "50051")
AFORO_TARGET = f"{AFORO_HOST}:{AFORO_PORT}"

GRPC_TIMEOUT = 3.0
MAX_RETRIES = 1


class AforoClient:
    def __init__(self):
        self._channel = None
        self._stub = None

    def _get_stub(self):
        if self._channel is None or self._channel._channel._state != grpc.ChannelConnectivity.READY:
            self._channel = grpc.insecure_channel(AFORO_TARGET)
            self._stub = aforo_pb2_grpc.AforoServiceStub(self._channel)
        return self._stub

    def get_seccion(self, seccion_id: str):
        stub = self._get_stub()
        request = aforo_pb2.GetSeccionRequest(seccion_id=seccion_id)
        try:
            return stub.GetSeccion(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            logger.error(f"gRPC GetSeccion error: {e.code()} - {e.details()}")
            raise

    def list_secciones(self, evento_id: str):
        stub = self._get_stub()
        request = aforo_pb2.ListSeccionesRequest(evento_id=evento_id)
        try:
            return stub.ListSecciones(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            logger.error(f"gRPC ListSecciones error: {e.code()} - {e.details()}")
            raise

    def vender_entrada(self, seccion_id: str, cantidad: int):
        stub = self._get_stub()
        request = aforo_pb2.VenderEntradaRequest(seccion_id=seccion_id, cantidad=cantidad)
        try:
            return stub.VenderEntrada(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            logger.error(f"gRPC VenderEntrada error: {e.code()} - {e.details()}")
            raise

    def anular_entrada(self, seccion_id: str, cantidad: int):
        stub = self._get_stub()
        request = aforo_pb2.AnularEntradaRequest(seccion_id=seccion_id, cantidad=cantidad)
        try:
            return stub.AnularEntrada(request, timeout=GRPC_TIMEOUT)
        except grpc.RpcError as e:
            logger.error(f"gRPC AnularEntrada error: {e.code()} - {e.details()}")
            raise

    def close(self):
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None


aforo_client = AforoClient()