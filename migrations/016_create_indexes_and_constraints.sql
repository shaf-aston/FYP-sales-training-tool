-- Migration: Add indexes and constraints for optimization and integrity
-- Version: 016

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_session_id ON quality_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_voice_logs_session_id ON voice_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_analysis_session_id ON conversation_analysis(session_id);
CREATE INDEX IF NOT EXISTS idx_session_persona_link_session_id ON session_persona_link(session_id);
CREATE INDEX IF NOT EXISTS idx_session_scenario_link_session_id ON session_scenario_link(session_id);

-- Unique constraints and referential integrity
ALTER TABLE personas ADD CONSTRAINT unique_persona_name UNIQUE (name);
ALTER TABLE scenarios ADD CONSTRAINT unique_scenario_title UNIQUE (title);
ALTER TABLE users ADD CONSTRAINT unique_username UNIQUE (username);
ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE (email);
