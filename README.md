# Sistema de Gestión de Eventos y Entradas

API REST pública (ventas) + servicio gRPC interno (aforo) + base de datos por servicio.

## Ejecución

```bash
docker compose up -d --build
docker compose down
```

Frontend: `http://localhost:8080`

API REST (versionada): `http://localhost:8002/api/v1/docs` (Swagger UI)

**Autenticación**: Header `X-API-Key: dev-key-123`

## Código gRPC

El contrato es `backend/aforo/aforo.proto`. En caso de modificar, ejecutar:

```bash
./scripts/gen-proto.sh
```

## Frontend

HTML/CSS/JS vanilla con pestañas Asistentes y Ventas. Se comunica por `fetch` con la API REST de venta-entradas.

Contenedor: nginx:alpine (puerto 80 → 8080).

## Backend

| Servicio | Rol | Protocolo | Stack |
|----------|-----|-----------|-------|
| aforo | Fuente de verdad: eventos, secciones, disponibilidad | gRPC (interno, 50051) | Python 3.12, grpcio, SQLAlchemy |
| venta-entradas | Asistentes y ventas; valida con aforo antes de vender | REST (8002, `/api/v1`) | Python 3.12, FastAPI, Uvicorn, cliente gRPC, SQLAlchemy |

### Endpoints REST (v1)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/api/v1/health` | Health check |
| POST | `/api/api/v1/asistentes` | Crear asistente |
| GET | `/api/api/v1/asistentes` | Listar asistentes |
| GET | `/api/api/v1/asistentes/{id}` | Obtener asistente por ID |
| PUT | `/api/api/v1/asistentes/{id}` | Actualizar asistente |
| DELETE | `/api/api/v1/asistentes/{id}` | Eliminar asistente |
| GET | `/api/api/v1/asistentes/rut/{rut}` | Obtener asistente por RUT |
| GET | `/api/api/v1/eventos` | Listar eventos (proxy a Aforo) |
| GET | `/api/api/v1/eventos/{id}/secciones` | Listar secciones de evento (proxy gRPC) |
| POST | `/api/api/v1/ventas` | Vender entrada (valida stock en Aforo) |
| GET | `/api/api/v1/ventas` | Listar ventas |
| GET | `/api/api/v1/ventas/{id}` | Obtener venta por ID |
| DELETE | `/api/api/v1/ventas/{id}` | Anular venta (libera aforo) |

### Servicio gRPC Aforo (puerto 50051)

| Método | Descripción |
|--------|-------------|
| `GetSeccion` | Consultar sección y disponibilidad |
| `ListSecciones` | Listar secciones de un evento |
| `VenderEntrada` | Descontar stock (idempotente) |
| `AnularEntrada` | Devolver stock (idempotente) |

Contrato: `backend/aforo/aforo.proto` (package `aforo.v1`)

## Bases de Datos

Dos contenedores PostgreSQL 16 aislados (una base de datos independiente por servicio):

| Base | Tablas |
|------|--------|
| db_aforo | evento, seccion |
| db_ventas | asistente, venta, api_key |

Credenciales de desarrollo en `docker-compose.yml`.

## Contratos

- **REST**: la fuente de verdad es el spec servido `GET /api/v1/openapi.json`
  (OpenAPI 3.0.3, generado por `custom_openapi` en `main.py`);
  `openapi.yaml` es un snapshot documental, no se verifica contra el vivo.
- **gRPC**: `backend/aforo/aforo.proto` (Protobuf 3).

### Pruebas de contrato

```bash
docker compose up -d          # suite esencial: gRPC (9) + REST (9) + fuzzing GETs
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
| T6 | Autenticación API Key | ✅ |
| T7 | Manejo de fallas (timeout 3s, 503/504) | ✅ |

## Requisitos Opcionales (Pendientes)

| Req | Descripción |
|-----|-------------|
| O1 | Caché con Redis |
| O2 | Idempotencia (Idempotency-Key) |
| O3 | HATEOAS |
| O4 | Pruebas de contrato |
| O5 | Segundo cliente gRPC en otro lenguaje |
