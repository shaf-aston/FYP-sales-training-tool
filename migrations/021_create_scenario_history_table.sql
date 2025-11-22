-- Migration: Create scenario_history table for tracking scenario changes
-- Version: 021

CREATE TABLE IF NOT EXISTS scenario_history (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
    changed_by VARCHAR(64),
    change_details JSONB,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
