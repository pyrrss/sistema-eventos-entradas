#!/usr/bin/env python3
"""Experimento Competencia 6: efecto del timeout gRPC ante dependencia lenta.

Matriz: GRPC_TIMEOUT {1,3,10}s x LATENCIA_MS {0,800,2000,4000}ms (inyección
en la app, servicer VenderEntrada). Por combinación:
  1) recrea aforo+venta-entradas con las env vars
  2) resetea estado (ventas/idempotencia/stock/caché)
  3) manda 100 requests POST /ventas con 10 concurrentes y mide

Ejecutar desde el host, con el stack arriba:  python3 scripts/experimento.py
Pasos de un solo combo:  python3 scripts/experimento.py --timeout 3 --latency 800
Salida: docs/experimento-data/results.json + tabla markdown en stdout.
"""
import json
import math
import os
import pathlib
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "http://localhost:8002/api/v1"
ADMIN = {"X-API-KEY": "dev-key-123"}
N_REQ, CONC = 100, 10
TIMEOUTS = [1.0, 3.0, 10.0]
LATENCIAS = [0, 800, 2000, 4000]
OUT_DIR = ROOT / "docs" / "experimento-data"

DB_VENTAS = dict(host="localhost", port=5433, user="ventas", password="ventas_dev", dbname="db_ventas")
DB_AFORO = dict(host="localhost", port=5432, user="aforo", password="aforo_dev", dbname="db_aforo")


def compose_up(timeout: float, latency: int):
    env = {**os.environ, "GRPC_TIMEOUT": str(timeout), "LATENCIA_MS": str(latency)}
    subprocess.run(["docker", "compose", "up", "-d", "aforo", "venta-entradas"],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    # esperar a que la API responda (recreate + arranque uvicorn)
    for _ in range(60):
        try:
            if requests.get(f"{BASE}/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("venta-entradas no recuperó /health tras el recreate")


def reset_state():
    with psycopg2.connect(**DB_VENTAS) as c, c.cursor() as cur:
        cur.execute("TRUNCATE venta, idempotencia CASCADE")
    with psycopg2.connect(**DB_AFORO) as c, c.cursor() as cur:
        cur.execute("UPDATE seccion SET cantidad_entradas_disponibles = capacidad_total")
    subprocess.run(["docker", "exec", "redis", "redis-cli", "FLUSHALL"],
                   check=True, capture_output=True)


def target_ids():
    with psycopg2.connect(**DB_VENTAS) as c, c.cursor() as cur:
        cur.execute("SELECT asistente_id FROM asistente LIMIT 1")
        asistente = str(cur.fetchone()[0])
    with psycopg2.connect(**DB_AFORO) as c, c.cursor() as cur:
        # sección del evento principal con stock suficiente para N_REQ ventas
        cur.execute("""
            SELECT s.seccion_id, s.nombre_seccion, e.nombre_evento
            FROM seccion s JOIN evento e USING (evento_id)
            WHERE s.capacidad_total >= %s
            ORDER BY s.capacidad_total ASC LIMIT 1""", (N_REQ,))
        sid, seccion, evento = cur.fetchone()
    return asistente, str(sid), seccion, evento


def pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1)]


def run_load(payload: dict, client_timeout: float):
    """100 POST con 10 concurrentes. Mide latencia por request y wall time."""
    def one(_):
        t0 = time.perf_counter()
        try:
            r = requests.post(f"{BASE}/ventas", headers=ADMIN, json=payload,
                              timeout=client_timeout + 25)
            code, detail = r.status_code, ""
        except requests.RequestException as e:
            code, detail = -1, type(e).__name__
        return code, (time.perf_counter() - t0) * 1000, detail

    latencies, codes = [], {}
    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        for code, ms, detail in ex.map(one, range(N_REQ)):
            latencies.append(ms)
            key = str(code) if code != -1 else f"client-error:{detail}"
            codes[key] = codes.get(key, 0) + 1
    wall = time.perf_counter() - t_start
    return {
        "total": N_REQ,
        "codes": codes,
        "success": codes.get("201", 0),
        "p50_ms": round(pct(latencies, 50), 1),
        "p95_ms": round(pct(latencies, 95), 1),
        "p99_ms": round(pct(latencies, 99), 1),
        "throughput_rps": round(N_REQ / wall, 2),
        "wall_s": round(wall, 1),
    }


def run_combo(timeout: float, latency: int, n_req: int = N_REQ):
    compose_up(timeout, latency)
    reset_state()
    asistente, seccion, nombre_seccion, nombre_evento = target_ids()
    payload = {"asistente_id": asistente, "id_seccion_aforo": seccion,
               "nombre_evento": nombre_evento, "nombre_seccion": nombre_seccion,
               "cantidad": 1}
    # warmup: 3 requests seriales (pool de conexiones gRPC/HTTP frío)
    run_warm = {**payload}
    for _ in range(3):
        requests.post(f"{BASE}/ventas", headers=ADMIN, json=run_warm, timeout=timeout + 25)
    reset_state()
    # medir
    old_n = globals()["N_REQ"]
    globals()["N_REQ"] = n_req
    try:
        res = run_load(payload, timeout)
    finally:
        globals()["N_REQ"] = old_n
    # dejar respirar al server: drains de requests viejos con sleep inyectado
    time.sleep(latency / 1000 + 2)
    return {"timeout_s": timeout, "latency_ms": latency, **res}


def main():
    args = sys.argv[1:]
    quick = "--timeout" in args
    if quick:
        t = float(args[args.index("--timeout") + 1])
        la = int(args[args.index("--latency") + 1])
        n = int(args[args.index("--n") + 1]) if "--n" in args else N_REQ
        print(json.dumps(run_combo(t, la, n), indent=2))
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for lat in LATENCIAS:
        for t in TIMEOUTS:
            print(f"# timeout={t}s latency={lat}ms ...", flush=True, file=sys.stderr)
            r = run_combo(t, lat)
            results.append(r)
            print(f"  201={r['success']} p99={r['p99_ms']}ms rps={r['throughput_rps']}",
                  flush=True, file=sys.stderr)
        (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))

    print("\n| Latencia | Timeout | Success (201) | Errores | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        errs = {k: v for k, v in r["codes"].items() if k != "201"}
        e = ", ".join(f"{v} ({k})" for k, v in errs.items()) or "0"
        print(f"| {r['latency_ms']}ms | {r['timeout_s']:g}s | {r['success']}/{r['total']} | {e} "
              f"| {r['p50_ms']} | {r['p95_ms']} | {r['p99_ms']} | {r['throughput_rps']} |")


if __name__ == "__main__":
    main()
