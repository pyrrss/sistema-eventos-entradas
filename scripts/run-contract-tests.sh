#!/usr/bin/env bash
# Corre la suite de pruebas de contrato contra el stack local vivo.
# No instala nada en el host: usa un contenedor descartable con
# --network host (los puertos del compose ya están publicados).
#
# Uso: ./scripts/run-contract-tests.sh [args extra de pytest]
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f docker-compose.yml ]; then
    echo "ejecutar desde la raíz del repo" >&2; exit 1
fi

if ! curl -sf http://localhost:8002/api/v1/health >/dev/null 2>&1; then
    echo "ERROR: venta-entradas no responde en :8002 — levantar con 'docker compose up -d'" >&2
    exit 1
fi

docker run --rm --network host \
    -v "$PWD:/app" -w /app \
    python:3.12-slim \
    bash -c "pip install -q -r tests/requirements-test.txt >/dev/null 2>&1 && python -m pytest tests/ \"$*\""
