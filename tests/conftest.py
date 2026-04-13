import os
import sys
import time

# Add src/ to path for all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Dummy API key so chatbot can be instantiated without real provider
os.environ.setdefault("GROQ_API_KEY", "test_key")

os.environ.setdefault("TZ", "Europe/London")
# time.tzset may not exist on all platforms (Windows). Call only if available
tzset = getattr(time, "tzset", None)
if tzset:
    try:
        tzset()
    except Exception:
        pass

try:
    import thinc.util as _thinc_util

    _orig_fix = _thinc_util.fix_random_seed

    def _safe_fix_random_seed(seed):
        try:
            return _orig_fix(seed)
        except Exception:
            try:
                s = int(seed) % (2**32)
            except Exception:
                s = 0
            return _orig_fix(s)

    _thinc_util.fix_random_seed = _safe_fix_random_seed
except Exception:
    pass


def pytest_configure(config):
    return
