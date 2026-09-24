CREATE TABLE IF NOT EXISTS api_key (
    key VARCHAR(64) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert default API key for development
INSERT INTO api_key (key, nombre) VALUES ('dev-key-123', 'Desarrollo') ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS asistente (
    asistente_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rut VARCHAR(20)  NOT NULL UNIQUE,
    nombre_completo VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS venta (
    venta_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    asistente_id UUID NOT NULL,
    fecha_venta TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('VENDIDA', 'ANULADA')),
    id_seccion_aforo UUID NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 1 CHECK (cantidad >= 1),
    nombre_evento VARCHAR(200) NOT NULL,
    nombre_seccion VARCHAR(200) NOT NULL,

    FOREIGN KEY (asistente_id) REFERENCES asistente(asistente_id)
);

-- hola
CREATE INDEX IF NOT EXISTS idx_venta_asistente ON venta(asistente_id);

CREATE TABLE IF NOT EXISTS idempotencia (
    clave VARCHAR(64) PRIMARY KEY,
    hash_body VARCHAR(64) NOT NULL,
    venta_id UUID,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
