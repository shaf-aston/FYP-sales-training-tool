-- Migration: Create voice_logs table
-- Version: 007

CREATE TABLE IF NOT EXISTS voice_logs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    audio_path VARCHAR(256) NOT NULL,
    transcript TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
