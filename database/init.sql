-- ============================================
-- LIMPIEZA (orden correcto por dependencias)
-- ============================================

DROP TABLE IF EXISTS heatmap_points;
DROP TABLE IF EXISTS area_state;
DROP TABLE IF EXISTS area_events;
DROP TABLE IF EXISTS areas;

-- ============================================
-- TABLA DE ÁREAS
-- ============================================

CREATE TABLE areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    x1 INT NOT NULL,
    y1 INT NOT NULL,
    x2 INT NOT NULL,
    y2 INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLA DE EVENTOS
-- ============================================

CREATE TABLE area_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    area_id INT NOT NULL,
    track_id INT NOT NULL,
    event VARCHAR(20) NOT NULL,
    dwell REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_area_events_area
        FOREIGN KEY (area_id) REFERENCES areas(id)
        ON DELETE CASCADE
);

-- ============================================
-- TABLA DE ESTADO
-- ============================================

CREATE TABLE area_state (
    area_id INT PRIMARY KEY,
    people_count INT NOT NULL DEFAULT 0,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_area_state_area
        FOREIGN KEY (area_id) REFERENCES areas(id)
        ON DELETE CASCADE
);

-- ============================================
-- HEATMAP
-- ============================================

CREATE TABLE heatmap_points (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    area_id INT,
    track_id INT NOT NULL,
    cx INT NOT NULL,
    cy INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_heatmap_area
        FOREIGN KEY (area_id) REFERENCES areas(id)
        ON DELETE SET NULL
);

-- ============================================
-- TABLA DE USUARIOS
-- ============================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- ============================================
-- ÍNDICES (para rendimiento)
-- ============================================

CREATE INDEX idx_area_events_area_id ON area_events(area_id);
CREATE INDEX idx_area_events_timestamp ON area_events(timestamp);

CREATE INDEX idx_heatmap_area_id ON heatmap_points(area_id);
CREATE INDEX idx_heatmap_timestamp ON heatmap_points(timestamp);