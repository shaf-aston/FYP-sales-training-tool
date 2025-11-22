-- Migration: Create quality_metric_types table
-- Version: 014

CREATE TABLE IF NOT EXISTS quality_metric_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
