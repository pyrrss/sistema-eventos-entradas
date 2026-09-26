# Experimento Competencia 6: Efecto del timeout ante dependencia lenta

## Hipótesis
Un timeout de 3 segundos en el cliente gRPC protege a la API REST de latencias
en cascada cuando el servicio de Aforo se degrada, pero aumenta la tasa de
errores **504** bajo degradación sostenida. Un timeout muy bajo (1 s) genera
falsos positivos (rechaza respuestas que habrían llegado poco después); uno muy
alto (10 s) bloquea workers y degrada la UX: los clientes esperan segundos por
respuesta aunque el sistema "técnicamente" tenga éxito.

> Nota de mapeo: timeout agotado (`DEADLINE_EXCEEDED`) → **504**; servicio
> inalcanzable (`UNAVAILABLE`) → **503**. Este experimento degrada latencia,
> no disponibilidad, por lo que los errores observados son 504
> (`backend/venta-entradas/main.py:367-368, 443-444`).

## Variables
| Variable | Valores probados |
|----------|------------------|
| **Independiente** | Timeout gRPC (1 s, 3 s, 10 s) · Latencia inyectada en Aforo (0, 800, 2000, 4000 ms) |
| **Dependiente** | % respuestas 504, Latencia P50/P95/P99 (ms), Throughput (req/s), % éxito (201) |
| **Controladas** | Mismo host, red localhost, carga idéntica (100 req, 10 concurrentes), mismo payload (1 ticket), API Key admin, estado limpio por combinación |

## Metodología

La latencia se inyecta **a nivel de aplicación** (`time.sleep` en el handler
`VenderEntrada` del servicer, controlado por la variable de entorno
`LATENCIA_MS` del contenedor `aforo`). Se eligió esta vía sobre `tc netem` por
dos razones: (1) no requiere privilegios `NET_ADMIN` ni paquetes extra en el
contenedor, así que es reproducible con el stack estándar; (2) la latencia
aplicada es exactamente `LATENCIA_MS` por request, sin el artefacto del doble
salto (red + BD) que introduciría `tc` sobre `eth0` del contenedor.

Variables de entorno agregadas para el experimento (defaults = comportamiento
de producción, la suite de contratos no se ve afectada):
- `LATENCIA_MS` en `aforo` (default `0`) — `backend/aforo/main.py:20-22, 79-80`
- `GRPC_TIMEOUT` en `venta-entradas` (default `3.0`) — `backend/venta-entradas/aforo_client.py:14`

Para cada una de las **12 combinaciones** timeout × latencia:

1. Recrear `aforo` y `venta-entradas` con `GRPC_TIMEOUT`/`LATENCIA_MS` de la combinación (`docker compose up -d`).
2. **Reset de estado** (crítico: 12×100 ventas agotarían el stock de cualquier sección): `TRUNCATE venta, idempotencia CASCADE`, `UPDATE seccion SET disponibles = capacidad_total`, `redis-cli FLUSHALL`.
3. **Warmup**: 3 requests seriales despreciados (calienta canales gRPC y pools de conexión) + reset otra vez.
4. **Carga**: 100 × `POST /api/v1/ventas` (1 entrada, mismo asistente y sección —la de menor
   capacidad ≥100, "VIP - Acceso Exclusivo" (100)—) con 10 concurrentes mediante `scripts/experimento.py`.
5. Registrar códigos de estado, P50/P95/P99 y throughput; limpiar latencia con el reset de la siguiente combinación.

Datos crudos: `docs/experimento-data/results.json` (máquina) y `table.md`.

```bash
# reproducir todo
docker compose up -d --build
python3 backend/scripts/seed.py
python3 scripts/experimento.py
```

## Resultados

Matriz completa (12 combinaciones, datos crudos en `docs/experimento-data/results.json`):

| Latencia | Timeout | Success (201) | Errores | P50 (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |
|---|---|---|---|---|---|---|---|
| 0 ms | 1s¹ | 68/100 | 32 (503) | 148.1 | 221.2 | 428.3 | 62.81 |
| 0 ms | 3s | 100/100 | 0 | 156.5 | 272.6 | 316.0 | 57.12 |
| 0 ms | 10s | 100/100 | 0 | 148.3 | 223.4 | 278.3 | 60.65 |
| 800 ms | 1s | 100/100 | 0 | 831.3 | 908.0 | 922.0 | 11.79 |
| 800 ms | 3s | 100/100 | 0 | 844.7 | 957.4 | 969.6 | 11.42 |
| 800 ms | 10s | 100/100 | 0 | 838.1 | 906.9 | 959.9 | 11.59 |
| 2000 ms | 1s | 0/100 | 100 (504) | 1012.1 | 1081.4 | 1111.1 | 9.69 |
| 2000 ms | 3s | 100/100 | 0 | 2022.7 | 2123.3 | 2139.5 | 4.88 |
| 2000 ms | 10s | 100/100 | 0 | 2034.8 | 2132.3 | 2149.8 | 4.87 |
| 4000 ms | 1s | 0/100 | 100 (504) | 1014.4 | 1142.4 | 1195.9 | 9.61 |
| 4000 ms | 3s | 0/100 | 100 (504) | 3011.6 | 3084.2 | 3119.3 | 3.30 |
| 4000 ms | 10s | 100/100 | 0 | 4024.8 | 4116.8 | 4135.3 | 2.47 |

¹ **Anomalía de arranque frío, transitoria**: la primera corrida de la matriz (inmediatamente después
de recrear los contenedores) produjo 32 errores 503 (`UNAVAILABLE` → "Aforo no disponible"), no 504:
ráfagas RPC sobre el canal gRPC recién restablecido pueden fallar de inmediato ("socket closed"), sin
siquiera esperar el deadline. Repetida la combinación en caliente: **100/100 (201), P99 232 ms**. Se
conserva la corrida original por honestidad y se documenta el efecto.

### Análisis por nivel de degradación

- **L = 0 (baseline)**: P50 ≈ 150 ms bajo ráfaga de 10 concurrentes (cola de threads en REST/gRPC;
  en régimen secuencial la operación cuesta ~15 ms). Throughput ~60 req/s con cualquier timeout:
  el timeout no cuesta nada cuando no se usa.
- **L = 800 ms**: los tres timeouts sobreviven al 100 %. Con T = 1 s el margen fue de apenas
  78 ms (P99 = 922 vs deadline 1000): cualquier jitter adicional (GC, concurrencia real)
  convertiría el 1 s en máquina de falsos positivos.
- **L = 2000 ms**: T = 1 s falla el 100 % (504 a ~1.0 s), mientras T = 3 s y T = 10 s completan el
  100 %. Aquí el timeout corto *agrava* la indisponibilidad: el sistema era capaz de responder.
- **L = 4000 ms**: T = 1 s y T = 3 s fallan todo, pero con P99 de 1.2 s / 3.1 s —el fast-fail
  devuelve capacidad al cliente rápido—. T = 10 s "triunfa" con 100/100, al costo de P50 = 4.0 s y
  throughput de 2.5 req/s (24× peor que baseline). **Latencia alta ≠ éxito operativo.**

### Propiedades medidas (no supuestas)

1. **El timeout es un techo duro de latencia**: en toda combinación fallida, P99 ≤ timeout +
   ~200 ms (peor caso medido: 3119 ms con deadline de 3000 ms). El cliente nunca espera más que el
   presupuesto configurado.
2. **Ley de Little verificada**: throughput ≈ concurrencia / P50 en las 12 combinaciones
   (p. ej. 10/2.02 s = 4.95 ≈ 4.88 medido; 10/4.02 = 2.49 ≈ 2.47). El cuello de botella es la
   espera, no el CPU.
3. **Fast-fail como load-shedding**: con L = 4 s, T = 1 s sostiene 9.6 req/s de *rezago de error*
   frente a 2.5 req/s de T = 10 s: deadlines cortos liberan workers antes y protegen al resto del
   sistema.
4. **Ventana de inconsistencia (hallazgo)**: con T = 1 s y L = 2 s, el cliente ya recibió 504 y sin
   embargo Aforo consuma la venta *después* del abandono: `disponibles` bajó escalonadamente
   100 → 99 (t+6 s) → 93 (t+10 s) con **0 filas en `venta`**. Ventas-huérfanas: butacas descontadas
   sin ticket emitido.

## Gráfico: tasa de éxito vs timeout (L = 4000 ms fijo)

```
Éxito (%)
100 ┤                                    ●──── 10s (pero P50=4.0s)
 80 ┤
 60 ┤
 40 ┤
 20 ┤
  0 ┼─────────●────────────●────────────┬────
           1s            3s            10s
                    Timeout
   ● = medido; el salto 0%→100% ocurre entre 3s y 10s
```

## Gráfico: P99 vs latencia inyectada (T fijo por serie)

```
P99 (ms)
4200 ┤                                           ●  T=10s (sigue a la latencia: UX degradada)
4000 ┤                                         ╱
2200 ┤                          ●─────●──────╱
2000 ┤                        ╱  T=3s ╱ T=10s
1000 ┤              ●╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ ← techo del deadline T=1s (falla, no espera)
 300 ┤  ●●●  baseline (~150ms)
   0 ┼────┬─────────┬─────────┬─────────┬────
       0ms      800ms     2000ms     4000ms   L inyectada
   Serie T=3s: P99 316 → 970 → 2140 → 3119 (luego clamp: falla en vez de esperar)
```

## Conclusiones

1. **3 s es el equilibrio correcto para este sistema (medido)**: absorbe degradación moderada
   (hasta ~2 s, con cabeza: P99 = 2140 ms) y ante degradación severa (4 s) pone un techo duro de
   ~3.1 s y libera workers, en lugar de colgar clientes.
2. **1 s es peligroso**: a L = 800 ms ya quedaban 78 ms de margen en el P99, y falla el 100 % con
   L ≥ 2 s que el sistema sí servía (falsos positivos); además fue el único punto donde apareció
   sensibilidad al arranque frío del canal (503 transitorios).
3. **10 s maximiza el éxito aparente y minimiza la disponibilidad real**: 100/100 a L = 4 s con
   P50 = 4 s y 2.5 req/s. Un SLO de "tasa de 201" sin límite de latencia premiaría exactamente esta
   configuración — el experimento muestra por qué los SLOs deben incluir percentiles.
4. **Trade-off coherente con ADR-004 (CP)**: ante Aforo lento se prefiere 504 (rechazo) a respuestas
   colgadas; **pero el experimento demuestra que el rechazo todavía no es seguro**: el descuento
   puede consumarse post-timeout (hallazgo 4, ventas huérfanas). El timeout protege la UX, no la
   consistencia.
5. **Trabajo futuro** (adicional al circuit breaker propuesto en ADR-004): (a) en el servicer,
   verificar `context.is_active()` antes de comitear para no venderle al cliente que ya se fue;
   (b) compensación tipo saga (reconciliación `venta` ↔ `disponibles` o reintento de anulación);
   (c) la caché Redis ya implementada (O1) amortigua la degradación en lecturas de catálogo, pero
   no cubre `POST /ventas`: el camino de venta depende de Aforo en línea.

> Nota: recomendaciones de versiones anteriores de este documento (O1 caché Redis, O2
> Idempotency-Key) **ya están implementadas** y verificadas por la suite de contratos
> (`./scripts/run-contract-tests.sh`), por lo que se retiran de las conclusiones.

## Reproducibilidad

El método completo está en Metodología; en una sola sesión:

```bash
docker compose up -d --build && python3 backend/scripts/seed.py
python3 scripts/experimento.py            # 12 combinaciones
# el script termina con el stack en defaults (GRPC_TIMEOUT=3.0, LATENCIA_MS=0) y estado limpio
```


## Referencias
- Timeout del cliente gRPC: `backend/venta-entradas/aforo_client.py:14` (`GRPC_TIMEOUT` por env var; sin reintentos — un único intento por llamada, decisión documentada en ADR-004)
- Inyección de latencia: `backend/aforo/main.py:20-22` (`LATENCIA_MS`) aplicada en `VenderEntrada`
- Mapeo de códigos gRPC → HTTP: `backend/venta-entradas/main.py:365-368` (ventas), `441-444` (anulación)
- ADR relacionado: [ADR-004](adr/ADR-004.md): Resiliencia y modos de falla
