# Sistema de Gestión de Eventos y Entradas

API REST pública (ventas) + servicio gRPC interno (aforo) + base de datos por servicio.

## Ejecución

```bash
docker compose up -d --build
docker compose down
```

Frontend: `http://localhost:8080`


## Frontend

HTML/CSS/JS vanilla con pestañas Asistentes y Ventas. Se comunica por `fetch` con la API REST de venta-entradas.

Contenedor: nginx:alpine (puerto 80 → 8080).

## Backend

| Servicio | Rol | Protocolo | Stack |
|----------|-----|-----------|-------|
| aforo | Fuente de verdad: eventos, secciones, disponibilidad | gRPC (interno, 50051) | Python 3.12, grpcio, SQLAlchemy |
| venta-entradas | Asistentes y ventas; valida con aforo antes de vender | REST (8000) | Python 3.12, FastAPI, Uvicorn, cliente gRPC, SQLAlchemy |

## Bases de Datos

Dos contenedores PostgreSQL 16 aislados (una base de datos independiente por servicio):

| Base | Tablas |
|------|--------|
| db_aforo | evento, seccion                                              |
| db_ventas | asistente, venta                                            |

Credenciales de desarrollo en `docker-compose.yml`.
