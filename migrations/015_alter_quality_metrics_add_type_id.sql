-- Migration: Alter quality_metrics to add type_id
-- Version: 015

ALTER TABLE quality_metrics
ADD COLUMN type_id INTEGER REFERENCES quality_metric_types(id);
