-- API Keys: solo se almacena el SHA-256 de la clave (nunca la clave tal cual).
-- Roles: 'lectura' (solo GET) y 'admin' (GET + POST/PUT/DELETE).

CREATE TABLE IF NOT EXISTS api_key (
    key_hash VARCHAR(64) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'lectura' CHECK (rol IN ('admin', 'lectura')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert default API key for development
-- key_hash = SHA-256 de la clave en claro (auth.py hashea la cabecera recibida y busca por hash).
--   admin   -> 'dev-key-123'
--   lectura -> 'dev-read-456'
INSERT INTO api_key (key_hash, nombre, rol) VALUES
    ('0f11c9ecaecabe613512ae472855ae9cb7d9639bc8c3fe85e0357efbf4739cd4', 'Desarrollo (admin)', 'admin'),
    ('c9e89e85b0621e6dc8ffa74d85251351bd3977ca582f3587baba2cf40027830a', 'Desarrollo (solo lectura)', 'lectura')
ON CONFLICT (key_hash) DO NOTHING;

CREATE TABLE IF NOT EXISTS asistente (
    asistente_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rut VARCHAR(20)  NOT NULL UNIQUE,
    nombre_completo VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS venta (
    venta_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    asistente_id UUID NOT NULL,
    fecha_venta TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('VENDIDA', 'ANULADA')),
    id_seccion_aforo UUID NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 1 CHECK (cantidad >= 1),
    nombre_evento VARCHAR(200) NOT NULL,
    nombre_seccion VARCHAR(200) NOT NULL,

    FOREIGN KEY (asistente_id) REFERENCES asistente(asistente_id)
);

-- hola
-- chao
CREATE INDEX IF NOT EXISTS idx_venta_asistente ON venta(asistente_id);

CREATE TABLE IF NOT EXISTS idempotencia (
    clave VARCHAR(64) PRIMARY KEY,
    hash_body VARCHAR(64) NOT NULL,
    venta_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
