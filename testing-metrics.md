# Testing Metrics

Last updated: 2026-04-09
Evidence owner: Developer-executed verification runs

This file is the single source of truth for Section 3 (Verification Phase).

## 1) Automated Regression (Current-Date Evidence)

### Full suite run
Command:
```bash
"c:/Users/Shaf/Downloads/Final Year Project pack folder/Sales roleplay chatbot/.venv/Scripts/python.exe" -m pytest tests/ -v
```
Result:
- Collected: 443 tests
- Passed: 443
- Failed: 0
- Duration: 9.05s
- Summary line: `============================= 443 passed in 9.05s =============================`

Interpretation:
- Regression baseline is currently green (no failing automated tests).
- This confirms strong functional stability for covered paths.

## 2) Coverage Evidence

Command:
```bash
"c:/Users/Shaf/Downloads/Final Year Project pack folder/Sales roleplay chatbot/.venv/Scripts/python.exe" -m pytest tests/ --cov=src/chatbot --cov=src/web --cov-report=term-missing
```

Result:
- Total statements: 3021
- Missed statements: 1215
- Total coverage: 60%
- Test summary: `443 passed in 15.57s`

High-confidence areas (selected):
- `src/chatbot/analysis.py`: 93%
- `src/chatbot/flow.py`: 91%
- `src/chatbot/analytics/session_analytics.py`: 94%
- `src/chatbot/utils.py`: 95%
- `src/chatbot/prompts.py`: 97%

Low-coverage areas (selected):
- `src/chatbot/providers/voice_provider.py`: 0%
- `src/web/routes/voice.py`: 20%
- `src/web/routes/prospect.py`: 22%
- `src/web/routes/debug.py`: 25%
- `src/chatbot/prospect/prospect.py`: 34%
- `src/web/routes/chat.py`: 34%
- `src/web/routes/session.py`: 37%
- `src/web/routes/analytics.py`: 39%
- `src/chatbot/training/trainer.py`: 43%

Interpretation:
- Core control logic (analysis/flow/stage handling) is strongly covered.
- Route-layer and voice/prospect pathways are the largest verification gaps.

## 3) Load Testing Evidence

Target:
- `http://127.0.0.1:5000`

Tool:
```bash
"c:/Users/Shaf/Downloads/Final Year Project pack folder/Sales roleplay chatbot/.venv/Scripts/python.exe" tests/load_test.py --url http://127.0.0.1:5000 --users <N> --duration 30 --ramp-up <R>
```

Script criteria (from `tests/load_test.py`):
- Fail if error rate > 10%
- Warning if p95 > 5000ms

### Observed runs (2026-04-09)

| Run | Users | Duration | Completed | Success | Failed | Error Rate | Avg (ms) | P95 (ms) | Throughput (req/s) | Outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 10 | 30s | 24 | 22 | 2 | 8.3% | 9830.53 | 22939.69 | 0.80 | PASS with warning |
| B | 3 | 30s | 19 | 0 | 19 | 100.0% | n/a | n/a | 0.63 | FAIL (intermittent anomaly run) |
| C | 3 | 30s | 13 | 13 | 0 | 0.0% | 3839.23 | 13888.13 | 0.43 | PASS with warning |
| D | 5 | 30s | 22 | 22 | 0 | 0.0% | 2870.58 | 5892.78 | 0.73 | PASS with warning |

Notes:
- Run B produced HTTP 400/connection errors in that specific execution window, then did not reproduce on immediate rerun (Run C).
- All passing runs still exceeded the p95 <= 5000ms target, so performance remains a known inefficiency.

## 4) Manual Endpoint Probe (Sanity Check)

Command (Python requests snippet):
- `POST /api/init` then `POST /api/chat`

Observed:
- `init`: HTTP 200 with valid `session_id`
- `chat`: HTTP 200 with returned response payload, latency field, provider/model metadata

Interpretation:
- Core request path is functioning end-to-end.

## 5) Verification Interpretation (Submission-Ready Statement)

Current status is sufficient evidence of systematic verification, but not yet release-grade.

Why this is sufficient for systematic verification:
- Full regression suite is green (443/443 pass).
- Coverage report identifies exactly where verification is strong and weak.
- Load tests were executed with explicit thresholds and repeat runs.

Why this is not yet release-grade:
- Total coverage is 60% with low coverage in several route-level modules.
- p95 latency exceeds the 5s threshold across passing load runs.
- Intermittent failure behavior was observed in one load run and should be treated as an open performance/reliability risk until repeated stabilization confirms closure.

## 6) Final Lock Checklist Before Submission Refresh

1. Re-run full suite (`pytest tests/ -v`) and archive output.
2. Re-run coverage command and update percentages in this file.
3. Re-run at least two load profiles and require:
   - error rate <= 10%
   - p95 <= 5000ms (or explicitly justify if exceeded)
4. Update Section 3 narrative to match latest numbers exactly.
