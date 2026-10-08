"""The one door to the AI: provider call, timeout, worker pool and failure breaker."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor


class AiGate:
    """Make one per server and hand it to every seller (build_seller's `gate`): the rate limit is shared on
    purpose. After `ai_fail_limit` failures in a row the AI is left alone for `ai_rest_seconds`, so no turn
    waits on a dead provider, while one slow call doesn't silence the AI for everyone."""

    def __init__(self, cfg):
        self._timeout, self._fail_limit, self._rest = cfg["ai_timeout_seconds"], cfg["ai_fail_limit"], cfg["ai_rest_seconds"]
        self._pool = ThreadPoolExecutor(max_workers=cfg["ai_workers"], thread_name_prefix="script-ai")
        self._lock = threading.Lock()
        self._fails, self._resting_until = 0, 0.0

    def llm(self, router):
        """Adapt the provider router to llm(prompt, max_tokens) -> text. Raises on failure or timeout."""

        def call(prompt, max_tokens):
            result = router.chat_with_fallback([{"role": "user", "content": prompt}], max_tokens=max_tokens)
            if not result.ok:
                raise RuntimeError(result.response.error or "provider failed")
            return result.response.content

        def guarded(prompt, max_tokens):
            with self._lock:
                if time.monotonic() < self._resting_until:
                    raise RuntimeError("AI resting after repeated failures")
            future = self._pool.submit(call, prompt, max_tokens)
            try:
                text = future.result(self._timeout)
            except Exception:
                future.cancel()  # still queued behind a slow call: never sent
                self._failed()
                raise
            with self._lock:
                self._fails = 0
            return text

        return guarded

    def _failed(self):
        with self._lock:
            self._fails += 1
            if self._fails >= self._fail_limit:
                self._fails = 0
                self._resting_until = time.monotonic() + self._rest
