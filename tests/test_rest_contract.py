"""Contrato REST de venta-entradas: comportamientos que el fuzzing no puede expresar.

Suite esencial: auth por roles, invariante de estado (server-assigned),
idempotencia (replay + reuso de clave), y caché Redis (TTL + invalidación).
tests son net-zero (anulan al final)

Fuente de verdad del contrato: el spec servido (GET /api/v1/openapi.json);
"""
import requests

from conftest import BASE, EVENTO_ID, headers, random_uuid


# ---------- autenticación / autorización ----------

def test_sin_api_key_es_401():
    r = requests.get(f"{BASE}/asistentes", timeout=10)
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_api_key_invalida_es_401():
    r = requests.get(f"{BASE}/asistentes", headers=headers("no-existe"), timeout=10)
    assert r.status_code == 401


def test_lectura_puede_leer_pero_no_escribir(reader):
    assert requests.get(f"{BASE}/asistentes", headers=reader, timeout=10).status_code == 200
    r = requests.post(f"{BASE}/asistentes", headers=reader, json={
        "rut": "1.111.111-1", "nombre_completo": "No Deberia Pasar", "email": "x@y.cl"}, timeout=10)
    assert r.status_code == 403  # rol lectura rechazado (no 500: typo waning ya fue corregido)


def test_health_no_pide_key():
    r = requests.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["message"] == "OK"


# ---------- invariante de estado ----------

def test_estado_es_server_assigned_y_anulacion_solo_por_delete(admin, vendedor_id, seccion_con_stock):
    body = {"asistente_id": vendedor_id, "id_seccion_aforo": seccion_con_stock.seccion_id,
            "nombre_evento": "contract-test", "nombre_seccion": "contract-test", "cantidad": 1}
    r = requests.post(f"{BASE}/ventas", headers=admin,
                      json={**body, "estado": "ANULADA"}, timeout=15)
    assert r.status_code == 201
    venta = r.json()
    assert venta["estado"] == "VENDIDA"  # el input no puede fijar el estado

    d = requests.delete(f"{BASE}/ventas/{venta['venta_id']}", headers=admin, timeout=15)
    assert d.status_code == 200 and d.json()["estado"] == "ANULADA"
    # segunda anulación → 400 (única transición posible)
    assert requests.delete(f"{BASE}/ventas/{venta['venta_id']}", headers=admin, timeout=15).status_code == 400


# ---------- idempotencia ----------

def test_retry_mismo_cliente_replay(admin, vendedor_id, seccion_con_stock):
    key = random_uuid()
    body = {"asistente_id": vendedor_id, "id_seccion_aforo": seccion_con_stock.seccion_id,
            "nombre_evento": "contract-test", "nombre_seccion": "contract-test", "cantidad": 1}
    h = lambda k: {**admin, "Idempotency-Key": k}
    r1 = requests.post(f"{BASE}/ventas", headers=h(key), json=body, timeout=15)
    r2 = requests.post(f"{BASE}/ventas", headers=h(key), json=body, timeout=15)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["venta_id"] == r2.json()["venta_id"]  # replay, no segunda venta

    # limpieza net-zero
    requests.delete(f"{BASE}/ventas/{r1.json()['venta_id']}", headers=admin, timeout=15)


def test_misma_idem_key_distinto_payload_es_422(admin, vendedor_id, seccion_con_stock):
    key = random_uuid()
    base = {"asistente_id": vendedor_id, "id_seccion_aforo": seccion_con_stock.seccion_id,
            "nombre_evento": "contract-test", "nombre_seccion": "contract-test"}
    r1 = requests.post(f"{BASE}/ventas", headers={**admin, "Idempotency-Key": key},
                       json={**base, "cantidad": 1}, timeout=15)
    assert r1.status_code == 201
    r2 = requests.post(f"{BASE}/ventas", headers={**admin, "Idempotency-Key": key},
                       json={**base, "cantidad": 5}, timeout=15)
    assert r2.status_code == 422  # reuso de clave con payload distinto
    requests.delete(f"{BASE}/ventas/{r1.json()['venta_id']}", headers=admin, timeout=15)


# ---------- caché Redis ----------

def test_cache_secciones_ttl_e_invalidation(admin, redis_client, seccion_con_stock):
    r = requests.get(f"{BASE}/eventos/{EVENTO_ID}/secciones", headers=admin, timeout=15)
    assert r.status_code == 200
    ck = f"catalogo:secciones:{EVENTO_ID}"
    ttl = redis_client.ttl(ck)
    assert 0 < ttl <= 15, f"TTL esperado (0,15], llegó {ttl}"

    # vender → invalidación
    asistente = requests.get(f"{BASE}/asistentes", headers=admin, timeout=10).json()[0]["asistente_id"]
    v = requests.post(f"{BASE}/ventas", headers=admin, json={
        "asistente_id": asistente, "id_seccion_aforo": seccion_con_stock.seccion_id,
        "nombre_evento": "cache-test", "nombre_seccion": "cache-test", "cantidad": 1}, timeout=15)
    assert v.status_code == 201
    assert redis_client.exists(ck) == 0  # la venta borró la entrada
    requests.delete(f"{BASE}/ventas/{v.json()['venta_id']}", headers=admin, timeout=15)
    assert redis_client.exists(ck) == 0  # la anulación también


# ---------- regresiones de hallazgos del fuzzing ----------

def test_rut_con_caracter_de_control_es_422(admin):
    """'%00' (NUL) llegaba al query y psycopg2 lo convertía en 500;
    el pattern del contrato (Path) lo rechaza con 422 documentado."""
    r = requests.get(f"{BASE}/asistentes/rut/%00", headers=admin, timeout=10)
    assert r.status_code == 422
