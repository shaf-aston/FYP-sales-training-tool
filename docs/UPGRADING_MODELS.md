# AI Model Upgrade Process

This guide describes a safe, repeatable process to upgrade the language model used by the service.

## Inputs
- Target model ID (e.g., `Qwen/Qwen2.5-1.5B-Instruct`)
- CPU/GPU availability
- Time budget for validation

## Steps
1. Staging configuration
   - Set env `MODEL_ID=<new-id>` or update `config/model_config.py` if used.
   - Start the app in staging mode and verify the model loads successfully.
2. Sanity checks
   - Call `POST /api/chat` with a short prompt; verify latency and correctness.
   - Run `tests/verify_optimizations.py` or basic smoke tests.
3. Regression prompts
   - Use a small fixed set of role-play prompts (greetings, pricing, objections, closing) to compare responses from old vs new model.
4. Performance budget
   - Confirm median end-to-end latency is within target (e.g., 3–7s CPU).
   - Adjust `max_new_tokens` and decoding strategy if needed.
5. Rollout
   - Deploy to production behind a feature flag `USE_NEW_MODEL=1`.
   - Monitor `/api/chat` response time and failure rates for 24–48h.
6. Cleanup
   - Remove flag after confidence; update docs and default config.

## Notes
- Keep `max_new_tokens` small (e.g., 32–64) for responsiveness.
- Use caching in `ChatService` to reduce duplicate generations.
