-- Migration: Create audit_log table for tracking schema and data changes
-- Version: 017

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    operation VARCHAR(32) NOT NULL,
    record_id INTEGER,
    changed_by VARCHAR(64),
    change_details JSONB,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
