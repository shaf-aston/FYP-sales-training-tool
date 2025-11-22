-- Migration: Create model_training_logs table
-- Version: 011

CREATE TABLE IF NOT EXISTS model_training_logs (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(128) NOT NULL,
    training_start TIMESTAMP NOT NULL,
    training_end TIMESTAMP,
    config_json JSONB,
    metrics_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
