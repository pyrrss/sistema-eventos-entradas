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
    nombre_evento VARCHAR(200) NOT NULL,
    nombre_seccion VARCHAR(200) NOT NULL,

    FOREIGN KEY (asistente_id) REFERENCES asistente(asistente_id)
);

-- hola
CREATE INDEX IF NOT EXISTS idx_venta_asistente ON venta(asistente_id);
