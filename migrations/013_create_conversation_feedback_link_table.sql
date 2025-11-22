-- Migration: Create conversation_feedback_link table
-- Version: 013

CREATE TABLE IF NOT EXISTS conversation_feedback_link (
    id SERIAL PRIMARY KEY,
    conversation_analysis_id INTEGER REFERENCES conversation_analysis(id) ON DELETE CASCADE,
    feedback_id INTEGER REFERENCES feedback(id) ON DELETE CASCADE,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
