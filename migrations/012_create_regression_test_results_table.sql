-- Migration: Create regression_test_results table
-- Version: 012

CREATE TABLE IF NOT EXISTS regression_test_results (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(128) NOT NULL,
    run_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_json JSONB NOT NULL,
    model_name VARCHAR(128),
    notes TEXT
);
