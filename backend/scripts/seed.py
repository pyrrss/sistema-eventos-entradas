#!/usr/bin/env python3
"""
Script de seed para poblar las bases de datos de Aforo y Ventas con datos de prueba.
Ejecutar desde el host: python3 backend/scripts/seed.py
Requiere: docker compose up -d (servicios corriendo)
"""

import psycopg2
import uuid
from datetime import datetime, timedelta

# Configuración de conexiones
DB_AFORO = "postgresql://aforo:aforo_dev@localhost:5432/db_aforo"
DB_VENTAS = "postgresql://ventas:ventas_dev@localhost:5433/db_ventas"


def seed_aforo():
    """Pobla la BD de Aforo con eventos y secciones."""
    print("=== Poblando Aforo ===")
    conn = psycopg2.connect(DB_AFORO)
    cur = conn.cursor()

    # Eventos
    eventos = [
        {
            "evento_id": "11111111-1111-1111-1111-111111111111",
            "nombre": "Concierto Rock Nacional",
            "lugar": "Estadio Nacional",
            "fecha": "2025-12-25 20:00:00"
        },
        {
            "evento_id": "22222222-2222-2222-2222-222222222222",
            "nombre": "Festival Electrónico Verano",
            "lugar": "Parque Bicentenario",
            "fecha": "2026-01-15 18:00:00"
        },
        {
            "evento_id": "33333333-3333-3333-3333-333333333333",
            "nombre": "Obra de Teatro: Hamlet",
            "lugar": "Teatro Municipal",
            "fecha": "2026-02-10 19:30:00"
        },
        {
            "evento_id": "44444444-4444-4444-4444-444444444444",
            "nombre": "Stand Up Comedy Night",
            "lugar": "Club de Comedia",
            "fecha": "2026-03-05 21:00:00"
        },
    ]

    for ev in eventos:
        cur.execute("""
            INSERT INTO evento (evento_id, nombre_evento, nombre_lugar, fecha_evento)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (evento_id) DO NOTHING
        """, (ev["evento_id"], ev["nombre"], ev["lugar"], ev["fecha"]))
        print(f"  Evento: {ev['nombre']}")

    # Secciones por evento
    secciones = {
        "11111111-1111-1111-1111-111111111111": [  # Concierto Rock
            ("VIP - Frente al Escenario", 50),
            ("Plateas Bajas", 300),
            ("Plateas Altas", 500),
            ("Cancha General", 2000),
        ],
        "22222222-2222-2222-2222-222222222222": [  # Festival Electrónico
            ("VIP - Acceso Exclusivo", 100),
            ("Golden Circle", 500),
            ("General", 5000),
        ],
        "33333333-3333-3333-3333-333333333333": [  # Teatro
            ("Platea Baja", 200),
            ("Platea Alta", 150),
            ("Palcos", 50),
        ],
        "44444444-4444-4444-4444-444444444444": [  # Comedy
            ("Primera Fila", 30),
            ("General", 150),
        ],
    }

    for evento_id, secs in secciones.items():
        for i, (nombre, cap) in enumerate(secs):
            seccion_id = f"{evento_id[:8]}-{i:04d}-{evento_id[14:]}"
            cur.execute("""
                INSERT INTO seccion (seccion_id, evento_id, nombre_seccion, capacidad_total, cantidad_entradas_disponibles)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (seccion_id) DO NOTHING
            """, (seccion_id, evento_id, nombre, cap, cap))
            print(f"    Sección: {nombre} (cap: {cap})")

    conn.commit()
    cur.close()
    conn.close()
    print("=== Aforo listo ===\n")


def seed_ventas():
    """Pobla la BD de Ventas con API key y asistentes de prueba."""
    print("=== Poblando Ventas ===")
    conn = psycopg2.connect(DB_VENTAS)
    cur = conn.cursor()

    # Las API keys ya las siembra schema.sql (con su SHA-256) en el init de la DB.
    # Aquí solo creamos asistentes de prueba.

    # Asistentes de prueba
    asistentes = [
        {"rut": "12.345.678-9", "nombre": "Juan Pérez González", "email": "juan.perez@email.com"},
        {"rut": "98.765.432-1", "nombre": "María González Silva", "email": "maria.gonzalez@email.com"},
        {"rut": "11.222.333-4", "nombre": "Carlos Rodríguez López", "email": "carlos.rodriguez@email.com"},
        {"rut": "22.333.444-5", "nombre": "Ana Martínez Fernández", "email": "ana.martinez@email.com"},
        {"rut": "33.444.555-6", "nombre": "Pedro Sánchez Ruiz", "email": "pedro.sanchez@email.com"},
        {"rut": "44.555.666-7", "nombre": "Laura Torres Díaz", "email": "laura.torres@email.com"},
        {"rut": "55.666.777-8", "nombre": "Diego Herrera Vargas", "email": "diego.herrera@email.com"},
        {"rut": "66.777.888-9", "nombre": "Sofía Castro Morales", "email": "sofia.castro@email.com"},
    ]

    asistente_ids = {}
    for a in asistentes:
        cur.execute("""
            INSERT INTO asistente (rut, nombre_completo, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (rut) DO UPDATE SET nombre_completo = EXCLUDED.nombre_completo, email = EXCLUDED.email
            RETURNING asistente_id
        """, (a["rut"], a["nombre"], a["email"]))
        row = cur.fetchone()
        if row:
            asistente_ids[a["rut"]] = str(row[0])
            print(f"  Asistente: {a['nombre']} ({a['rut']}) -> {row[0]}")

    conn.commit()
    cur.close()
    conn.close()
    print("=== Ventas listo ===\n")
    return asistente_ids


def verify_data():
    """Verifica los datos insertados."""
    print("=== Verificación ===")

    # Aforo
    conn = psycopg2.connect(DB_AFORO)
    cur = conn.cursor()
    cur.execute("SELECT evento_id, nombre_evento FROM evento")
    eventos = cur.fetchall()
    print(f"\nEventos en Aforo: {len(eventos)}")
    for ev in eventos:
        cur.execute("SELECT nombre_seccion, capacidad_total, cantidad_entradas_disponibles FROM seccion WHERE evento_id = %s", (ev[0],))
        secs = cur.fetchall()
        print(f"  {ev[1]} ({ev[0]})")
        for s in secs:
            print(f"    - {s[0]}: {s[2]}/{s[1]} disponibles")
    cur.close()
    conn.close()

    # Ventas
    conn = psycopg2.connect(DB_VENTAS)
    cur = conn.cursor()
    cur.execute("SELECT nombre, rol, activo FROM api_key")
    keys = cur.fetchall()
    print(f"\nAPI Keys: {len(keys)}")
    for k in keys:
        print(f"  {k[0]} — rol: {k[1]}, activo: {k[2]}")

    cur.execute("SELECT asistente_id, rut, nombre_completo FROM asistente")
    asistentes = cur.fetchall()
    print(f"\nAsistentes: {len(asistentes)}")
    for a in asistentes:
        print(f"  {a[2]} ({a[1]}) -> {a[0]}")
    cur.close()
    conn.close()


def main():
    print("Iniciando seed de datos de prueba...\n")
    try:
        seed_aforo()
        seed_ventas()
        verify_data()
        print("\n✅ Seed completado exitosamente!")
        print("\nAhora puedes:")
        print("  1. Abrir http://localhost:8080 (Frontend)")
        print("  2. Ir a pestaña Ventas > Vender entrada")
        print("  3. Seleccionar evento, sección, asistente y vender")
        print("  4. Ver stock actualizado en tiempo real")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nAsegúrate de que los servicios estén corriendo:")
        print("  docker compose up -d")


if __name__ == "__main__":
    main()
