# Migration Scripts

This folder contains versioned migration scripts for evolving the database schema.

## How to Use

1. Apply migrations in order:
   - `001_create_sessions_and_quality_metrics.sql`
   - `002_add_feedback_table.sql`
   - `003_create_personas_table.sql`
   - `004_create_scenarios_table.sql`
   - `005_create_feedback_metrics_table.sql`
   - `006_create_conversation_analysis_table.sql`
   - `007_create_voice_logs_table.sql`
   - `008_create_user_table.sql`
   - `009_create_session_persona_link_table.sql`
   - `010_create_session_scenario_link_table.sql`
   - `011_create_model_training_logs_table.sql`
   - `012_create_regression_test_results_table.sql`
   - `013_create_conversation_feedback_link_table.sql`
   - `014_create_quality_metric_types_table.sql`
   - `015_alter_quality_metrics_add_type_id.sql`
   - `016_create_indexes_and_constraints.sql`
   - `017_create_audit_log_table.sql`
   - `018_create_health_check_table.sql`
   - `019_create_message_table.sql`
   - `020_create_persona_history_table.sql`
   - `021_create_scenario_history_table.sql`
2. Use Alembic or a manual SQL tool to apply these scripts to your PostgreSQL database.
3. On each schema change, create a new migration script with a sequential version number and a clear description.
4. Always review and test migrations before applying to production.

## Migration History
- **001**: Create `sessions` and `quality_metrics` tables
- **002**: Add `feedback` table
- **003**: Add `personas` table
- **004**: Add `scenarios` table
- **005**: Add `feedback_metrics` table
- **006**: Add `conversation_analysis` table
- **007**: Add `voice_logs` table
- **008**: Add `users` table
- **009**: Add `session_persona_link` table
- **010**: Add `session_scenario_link` table
- **011**: Add `model_training_logs` table
- **012**: Add `regression_test_results` table
- **013**: Add `conversation_feedback_link` table
- **014**: Add `quality_metric_types` table
- **015**: Alter `quality_metrics` to add `type_id`
- **016**: Add indexes and constraints
- **017**: Add `audit_log` table
- **018**: Add `health_check` table
- **019**: Add `messages` table
- **020**: Add `persona_history` table
- **021**: Add `scenario_history` table

## Rollback
- To rollback, reverse the changes in the latest migration script or use Alembic's downgrade feature.

## Best Practices
- Keep all migration scripts in this folder, in order.
- Document each migration with a clear description.
- Test migrations in staging before production.
- Use indexes and constraints for performance and integrity.
- Track changes with audit and history tables for compliance and debugging.
