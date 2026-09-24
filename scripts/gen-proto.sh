#!/usr/bin/env bash
# Regenera el código gRPC (aforo_pb2.py / aforo_pb2_grpc.py) desde
# backend/aforo/aforo.proto y lo propaga a ambos servicios.
#
# Uso:  ./scripts/gen-proto.sh          (requiere Docker)
# Tras ejecutarlo, commitear los pb2 regenerados en ambos directorios.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO="$ROOT/backend/aforo/aforo.proto"

# Imagen con grpcio-tools ya instalado (la de aforo se construye con él)
IMAGE="project-aforo"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Imagen $IMAGE no existe; construyéndola..."
    docker compose -f "$ROOT/docker-compose.yml" build aforo
fi

# 1) Generar en backend/aforo
docker run --rm -v "$ROOT/backend/aforo:/work" "$IMAGE" \
    python -m grpc_tools.protoc \
    --proto_path=/work --python_out=/work --grpc_python_out=/work \
    /work/aforo.proto

# 2) Copiar a backend/venta-entradas (cada servicio lleva su copia del contrato)
cp "$ROOT/backend/aforo/aforo_pb2.py" "$ROOT/backend/venta-entradas/aforo_pb2.py"
cp "$ROOT/backend/aforo/aforo_pb2_grpc.py" "$ROOT/backend/venta-entradas/aforo_pb2_grpc.py"

echo "OK: pb2 generados desde aforo.proto y sincronizados en ambos servicios."
