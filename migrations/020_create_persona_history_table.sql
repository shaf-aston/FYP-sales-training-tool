-- Migration: Create persona_history table for tracking persona changes
-- Version: 020

CREATE TABLE IF NOT EXISTS persona_history (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER REFERENCES personas(id) ON DELETE CASCADE,
    changed_by VARCHAR(64),
    change_details JSONB,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
