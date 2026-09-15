CREATE TABLE IF NOT EXISTS evento (
    evento_id     UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    nombre_evento VARCHAR(200) NOT NULL,
    nombre_lugar  VARCHAR(200) NOT NULL,
    fecha_evento  TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS seccion (
    seccion_id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    evento_id                     UUID        NOT NULL,
    nombre_seccion                VARCHAR(200) NOT NULL,
    capacidad_total               INTEGER     NOT NULL,
    cantidad_entradas_disponibles INTEGER     NOT NULL DEFAULT 0,
    
    FOREIGN KEY (evento_id) REFERENCES evento(evento_id) ON DELETE CASCADE,

    UNIQUE (evento_id, nombre_seccion),

    CONSTRAINT seccion_disponibilidad_ok
        CHECK (capacidad_total > 0
           AND cantidad_entradas_disponibles >= 0
           AND cantidad_entradas_disponibles <= capacidad_total)
);

-- hola
CREATE INDEX IF NOT EXISTS idx_seccion_evento ON seccion(evento_id);
