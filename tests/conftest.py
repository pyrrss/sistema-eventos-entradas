import os
import sys
import uuid

import pytest
import requests

BASE = os.getenv("API_BASE", "http://localhost:8002/api/v1")
GRPC_TARGET = os.getenv("AFORO_GRPC", "localhost:50051")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_KEY = os.getenv("ADMIN_KEY", "dev-key-123")
READ_KEY = os.getenv("READ_KEY", "dev-read-456")

# para importar los stubs generados del proto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "aforo"))

DB_VENTAS = os.getenv("DB_VENTAS", "postgresql://ventas:ventas_dev@localhost:5433/db_ventas")

# evento/secciones del seed usados por los tests
EVENTO_ID = "11111111-1111-1111-1111-111111111111"


def headers(key=ADMIN_KEY):
    return {"X-API-KEY": key, "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def admin():
    return headers(ADMIN_KEY)


@pytest.fixture(scope="session")
def reader():
    return headers(READ_KEY)


@pytest.fixture(scope="session")
def stub():
    import grpc
    import aforo_pb2_grpc
    ch = grpc.insecure_channel(GRPC_TARGET)
    yield aforo_pb2_grpc.AforoServiceStub(ch)
    ch.close()


@pytest.fixture(scope="session")
def redis_client():
    import redis
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


@pytest.fixture(scope="session")
def vendedor_id():
    """asistente del seed para pruebas de venta"""
    r = requests.get(f"{BASE}/asistentes", headers=headers(), timeout=10)
    r.raise_for_status()
    for a in r.json():
        if a["rut"] == "12.345.678-9":
            return a["asistente_id"]
    pytest.skip("asistente del seed no encontrado; correr scripts/seed.py")


@pytest.fixture(scope="session")
def seccion_con_stock(stub):
    """primera sección del evento con >= 3 disponibles"""
    import aforo_pb2
    resp = stub.ListSecciones(aforo_pb2.ListSeccionesRequest(evento_id=EVENTO_ID), timeout=5)
    for s in resp.secciones:
        if s.cantidad_entradas_disponibles >= 3:
            return s
    pytest.skip("no hay secciones con stock >= 3 (realinear aforo con seed)")


def random_uuid():
    return str(uuid.uuid4())
