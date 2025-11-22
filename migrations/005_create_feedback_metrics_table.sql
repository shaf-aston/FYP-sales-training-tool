-- Migration: Create feedback_metrics table
-- Version: 005

CREATE TABLE IF NOT EXISTS feedback_metrics (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES feedback(id) ON DELETE CASCADE,
    metric VARCHAR(64) NOT NULL,
    value FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
