# Sistema de Gestión de Eventos y Entradas

API REST pública (ventas) + servicio gRPC interno (aforo) + base de datos por servicio.

## Ejecución

```bash
docker compose up -d --build
python3 backend/scripts/seed.py   # puebla eventos/secciones y asistentes de prueba
docker compose down
```

Para empezar desde cero (vuelve a aplicar los `schema.sql` al recrear los volúmenes): `docker compose down -v`.

Frontend: `http://localhost:8080`

API REST (versionada): `http://localhost:8002/api/v1/docs` (Swagger UI)

**Autenticación**: Header `X-API-KEY`. Claves de desarrollo: `dev-key-123` (rol admin, puede escribir) y `dev-read-456` (rol lectura, solo GET). `GET /health` es público.

## Código gRPC

El contrato es `backend/aforo/aforo.proto`. En caso de modificar, ejecutar:

```bash
./scripts/gen-proto.sh
```

## Frontend

HTML/CSS/JS vanilla con pestañas Asistentes y Ventas. Se comunica por `fetch` con la API REST de venta-entradas. Cada intento de venta genera un `Idempotency-Key` (UUID) que se reenvía en reintentos, evitando duplicados.

Contenedor: nginx:alpine (puerto 80 → 8080).

## Backend

| Servicio | Rol | Protocolo | Stack |
|----------|-----|-----------|-------|
| aforo | Fuente de verdad: eventos, secciones, disponibilidad | gRPC (interno, 50051) | Python 3.12, grpcio, SQLAlchemy |
| venta-entradas | Asistentes y ventas; valida con aforo antes de vender | REST (8002, `/api/v1`) | Python 3.12, FastAPI, Uvicorn, cliente gRPC, SQLAlchemy, Redis (cache-aside del catálogo: eventos TTL 60 s, secciones TTL 15 s, invalidadas al vender/anular) |

### Endpoints REST (v1)

Todos requieren `X-API-KEY` (menos `health`); los que escriben requieren rol admin.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check (público) |
| POST | `/api/v1/asistentes` | Crear asistente |
| GET | `/api/v1/asistentes` | Listar asistentes |
| GET | `/api/v1/asistentes/{id}` | Obtener asistente por ID |
| PUT | `/api/v1/asistentes/{id}` | Actualizar asistente |
| GET | `/api/v1/asistentes/rut/{rut}` | Obtener asistente por RUT |
| GET | `/api/v1/eventos` | Listar eventos (proxy a Aforo) |
| GET | `/api/v1/eventos/{id}/secciones` | Listar secciones de evento (proxy gRPC, cacheado en Redis) |
| POST | `/api/v1/ventas` | Vender entrada (valida stock en Aforo; acepta `Idempotency-Key`: replay de la misma venta, 422 si el payload cambió, 409 si está en procesamiento) |
| GET | `/api/v1/ventas` | Listar ventas |
| GET | `/api/v1/ventas/{id}` | Obtener venta por ID |
| DELETE | `/api/v1/ventas/{id}` | Anular venta (libera aforo) |

### Servicio gRPC Aforo (puerto 50051)

| Método | Descripción |
|--------|-------------|
| `ListEventos` | Listar eventos |
| `GetSeccion` | Consultar sección y disponibilidad |
| `ListSecciones` | Listar secciones de un evento |
| `VenderEntrada` | Descontar stock |
| `AnularEntrada` | Devolver stock |

Contrato: `backend/aforo/aforo.proto` (package `aforo.v1`)

## Bases de Datos

Dos contenedores PostgreSQL 16 aislados (una base de datos independiente por servicio), más Redis para caché:

| Base | Tablas |
|------|--------|
| db_aforo | evento, seccion |
| db_ventas | asistente, venta, api_key, idempotencia |

Credenciales de desarrollo en `docker-compose.yml`.

## Contratos

- **REST**: la fuente de verdad es el spec servido `GET /api/v1/openapi.json`
  (OpenAPI 3.0.3, generado por `custom_openapi` en `main.py`);
  `openapi.yaml` es un snapshot documental, no se verifica contra el vivo.
- **gRPC**: `backend/aforo/aforo.proto` (Protobuf 3).

### Pruebas de contrato

```bash
docker compose up -d          # suite esencial: gRPC (8) + REST (9) + fuzzing Schemathesis (8 ops GET)
./scripts/run-contract-tests.sh
```

## Documentación de Decisiones (ADRs)

- [ADR-001](docs/adr/ADR-001.md): Estilo de integración y descomposición
- [ADR-002](docs/adr/ADR-002.md): REST hacia afuera, gRPC hacia adentro
- [ADR-003](docs/adr/ADR-003.md): Contrato, versionado y evolución
- [ADR-004](docs/adr/ADR-004.md): Resiliencia y modos de falla

## Experimento Competencia 6

Ver [docs/experimento.md](docs/experimento.md): Efecto del timeout ante dependencia lenta (gRPC).

## Uso de Asistentes de IA

Este proyecto fue desarrollado con asistencia de **GitHub Copilot / Claude (opencode)** para:
- Generación de código boilerplate (modelos, esquemas, Dockerfiles)
- Redacción de contratos OpenAPI y Protobuf
- Estructura de ADRs y documentación técnica
- Diseño del experimento de latencia

**Verificación humana**: Todo el código fue revisado, probado sintácticamente (`python3 -m py_compile`), y las decisiones de arquitectura fueron validadas por el equipo. Cada integrante puede explicar cualquier línea del código durante la defensa.

## Requisitos Técnicos Cumplidos

| Req | Descripción | Estado |
|-----|-------------|--------|
| T1 | Todo dockerizado (`docker compose up`) | ✅ |
| T2 | API REST versionada (`/api/v1`) | ✅ |
| T3 | Contratos explícitos (OpenAPI + `.proto`) | ✅ |
| T4 | Servicio gRPC interno con Protobuf | ✅ |
| T5 | Base de datos por servicio | ✅ |
| T6 | Autenticación API Key (roles admin/lectura) | ✅ |
| T7 | Manejo de fallas (timeout 3s, 503/504) | ✅ |

## Requisitos Opcionales

| Req | Descripción | Estado |
|-----|-------------|--------|
| O1 | Caché con Redis | ✅ cache-aside del catálogo con invalidación en venta/anulación |
| O2 | Idempotencia (`Idempotency-Key`) | ✅ en `POST /ventas`, lock en Postgres scopeado por cliente |
| O3 | HATEOAS | No implementado |
| O4 | Pruebas de contrato | ✅ suite automatizada (`scripts/run-contract-tests.sh`) |
| O5 | Segundo cliente gRPC en otro lenguaje | No implementado |
