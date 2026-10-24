## Problem
What was wrong, and how it was found (test, log, user report).

## Fix
What changed and why this way. Wording lives in YAML/config, not code.

## Proof
- [ ] A test that fails before the fix and passes after
- [ ] `python -m pytest -q` passes
- [ ] `npm run check` and `npm run build` pass (if `web/` changed)
- [ ] `make test-real` passes (if the script or matching changed)
- [ ] Verbatim script lines unchanged, or the owner approved the change

## Risk
What could break, and how to undo it.
