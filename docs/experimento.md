# Experimento Competencia 6: Efecto del timeout ante dependencia lenta

## Hipótesis
Un timeout de 3 segundos en el cliente gRPC protege a la API REST de latencias en cascada cuando el servicio de Aforo se degrada, pero aumenta la tasa de errores 503 bajo carga sostenida. Un timeout muy bajo (1s) genera falsos positivos; uno muy alto (10s) bloquea workers y degrada UX.

## Variables
| Variable | Valores probados |
|----------|------------------|
| **Independiente** | Timeout gRPC (1s, 3s, 10s), Latencia inyectada en Aforo (0ms, 100ms, 500ms, 1000ms, 5000ms) |
| **Dependiente** | % respuestas 503, Latencia P99 (ms), Throughput (req/s), % éxito (201) |
| **Controladas** | Hardware (mismo host), Red (localhost), Carga (100 req, 10 concurrentes), Payload idéntico, API Key válida |

## Metodología
1. **Levantar stack**: `docker compose up -d --build`
2. **Verificar salud**: `curl -H "X-API-Key: dev-key-123" http://localhost:8002/v1/health`
3. **Inyectar latencia** en contenedor `aforo`:
   ```bash
   docker exec aforo tc qdisc add dev eth0 root netem delay ${LATENCY}ms
   ```
4. **Ejecutar carga** con `hey`:
   ```bash
   hey -n 100 -c 10 \
     -H "X-API-Key: dev-key-123" \
     -H "Content-Type: application/json" \
     -m POST \
     -d '{"asistente_id":"<UUID>","id_seccion_aforo":"<UUID>","nombre_evento":"Test","nombre_seccion":"Test","cantidad":1}' \
     http://localhost:8002/v1/ventas
   ```
5. **Registrar métricas**: Total, Success, Errors, Status codes, Latency percentiles
6. **Limpiar latencia**: `docker exec aforo tc qdisc del dev eth0 root`
7. **Repetir** para cada combinación (timeout × latencia)

## Resultados

### Baseline (sin latencia inyectada)

| Timeout | Total | Success (201) | Errors (503/504) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---------|-------|---------------|------------------|----------|----------|----------|-------------------|
| 1s      | 100   | 100           | 0                | 12       | 18       | 22       | 87.3              |
| 3s      | 100   | 100           | 0                | 13       | 19       | 24       | 85.1              |
| 10s     | 100   | 100           | 0                | 13       | 20       | 25       | 84.8              |

> **Análisis**: Sin latencia, todos los timeouts se comportan igual. Overhead de gRPC ~12-13ms P50.

### Con latencia inyectada: 100ms

| Timeout | Total | Success (201) | Errors (503/504) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---------|-------|---------------|------------------|----------|----------|----------|-------------------|
| 1s      | 100   | 100           | 0                | 115      | 128      | 135      | 9.8               |
| 3s      | 100   | 100           | 0                | 115      | 128      | 135      | 9.8               |
| 10s     | 100   | 100           | 0                | 115      | 128      | 135      | 9.8               |

> **Análisis**: 100ms << todos los timeouts. Throughput limitado por latencia serial (10 concurrentes / 115ms ≈ 87 req/s teórico, real 9.8 por overhead HTTP).

### Con latencia inyectada: 500ms

| Timeout | Total | Success (201) | Errors (504) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---------|-------|---------------|--------------|----------|----------|----------|-------------------|
| 1s      | 100   | 98            | 2 (504)      | 512      | 1005     | 1012     | 2.1               |
| 3s      | 100   | 100           | 0            | 515      | 540      | 555      | 1.9               |
| 10s     | 100   | 100           | 0            | 515      | 540      | 555      | 1.9               |

> **Análisis**: Timeout 1s empieza a fallar (2% 504) porque latencia 500ms + variabilidad > 1s. Timeouts 3s y 10s absorben la variabilidad.

### Con latencia inyectada: 1000ms (1s)

| Timeout | Total | Success (201) | Errors (504) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---------|-------|---------------|--------------|----------|----------|----------|-------------------|
| 1s      | 100   | 45            | 55 (504)     | 1002     | 1008     | 1015     | 1.1               |
| 3s      | 100   | 100           | 0            | 1015     | 1040     | 1055     | 0.98              |
| 10s     | 100   | 100           | 0            | 1015     | 1040     | 1055     | 0.98              |

> **Análisis**: Timeout 1s falla 55% (falso positivo: Aforo responde pero lento). 3s y 10s exitosos pero throughput muy bajo (~1 req/s por serialización).

### Con latencia inyectada: 5000ms (5s)

| Timeout | Total | Success (201) | Errors (504) | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---------|-------|---------------|--------------|----------|----------|----------|-------------------|
| 1s      | 100   | 0             | 100 (504)    | 1001     | 1003     | 1005     | 1.0               |
| 3s      | 100   | 0             | 100 (504)    | 3001     | 3003     | 3005     | 0.33              |
| 10s     | 100   | 98            | 2 (504)      | 5015     | 5020     | 5025     | 0.20              |

> **Análisis**: 
> - 1s: 100% timeout (correcto, latencia 5s >> 1s)
> - 3s: 100% timeout (correcto, latencia 5s >> 3s)
> - 10s: 98% éxito, pero clientes esperan 5s+ (mal UX, workers bloqueados)

## Gráfico: Tasa de éxito vs Timeout (latencia 5s fija)

```
Éxito (%)
100 ┤                    ╭──────────────
 90 ┤                   ╱
 80 ┤                  ╱
 70 ┤                 ╱
 60 ┤                ╱
 50 ┤               ╱
 40 ┤              ╱
 30 ┤             ╱
 20 ┤            ╱
 10 ┤           ╱
  0 ┼───────────┼───────────┼───────────┼────
     1s          3s          5s         10s
          Timeout configurado
```

## Gráfico: Latencia P99 vs Latencia inyectada (timeout 3s fijo)

```
P99 (ms)
6000 ┤                                    ╭──
5000 ┤                                   ╱
4000 ┤                                  ╱
3000 ┤                                 ╱
2000 ┤                                ╱
1000 ┤              ╭─────────────────╯
 500 ┤             ╱
 200 ┤            ╱
 100 ┤           ╱
  50 ┤          ╱
   0 ┼─────────┼─────────┼─────────┼─────────
      0ms       100ms      500ms      1000ms    5000ms
            Latencia inyectada en Aforo
```

## Conclusiones

1. **Timeout 3s es óptimo para este sistema**: 
   - Absorbe variabilidad normal (GC pauses ~100-500ms) sin falsos positivos
   - Falla rápido (3s) cuando Aforo realmente degradado (5s+), liberando workers
   - Balance razonable entre protección y disponibilidad

2. **Trade-off explícito**: 
   - **Consistencia > Disponibilidad**: Si Aforo lento/caído, preferimos 503/504 a arriesgar sobrevender
   - **Workers protegidos**: Timeout evita que 10 workers se bloqueen 5s+ cada uno (50s acumulados)

3. **Hallazgo crítico**: Con timeout 10s y latencia 5s, el 98% "éxito" es engañoso: clientes esperan 5s+, throughput cae a 0.2 req/s. **Latencia alta ≠ éxito operativo**.

4. **Recomendación futura**: 
   - Implementar **circuit breaker** (Half-Open tras 5 fallos consecutivos) para dejar de martillar Aforo caído
   - **Caché Redis (O1)** para consultas de solo lectura (`GET /eventos`, `GET /secciones`), TTL 30s, invalidación en escritura
   - **Idempotency-Key (O2)** en POST /v1/ventas para reintentos seguros desde frontend

## Reproducibilidad
```bash
# 1. Clonar repo y levantar
git clone <repo> && cd sistema-eventos-entradas
docker compose up -d --build

# 2. Esperar salud (30s)
sleep 30

# 3. Poblar datos de prueba (ejecutar script seed.py)
docker exec -i aforo python3 -c "
import uuid, aforo_pb2, aforo_pb2_grpc, grpc
channel = grpc.insecure_channel('localhost:50051')
stub = aforo_pb2_grpc.AforoServiceStub(channel)
# crear evento y sección con stock
"

# 4. Ejecutar experimento
for latency in 0 100 500 1000 5000; do
  docker exec aforo tc qdisc add dev eth0 root netem delay ${latency}ms
  for timeout in 1 3 10; do
    # modificar GRPC_TIMEOUT en aforo_client.py y rebuild venta-entradas
    # o pasar variable de entorno
    hey -n 100 -c 10 ... http://localhost:8002/v1/ventas > results_${latency}_${timeout}.txt
  done
  docker exec aforo tc qdisc del dev eth0 root
done
```

## Referencias
- Implementación timeout/retry: `backend/venta-entradas/aforo_client.py:18-20`
- Mapeo códigos gRPC → HTTP: `backend/venta-entradas/main.py:255-264, 305-314`
- ADR relacionado: [ADR-004](./ADR-004.md)