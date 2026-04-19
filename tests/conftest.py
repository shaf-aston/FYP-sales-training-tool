import os
import sys
import time

# Add src/ to path for all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Dummy API key so chatbot can be instantiated without real provider
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("TZ", "Europe/London")

# Set timezone only on systems that support tzset (skip Windows)
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

# Workaround: thinc's random seed fix fails on some systems with large seeds.
# Clamp to 32-bit range to prevent overflow.
try:
    import thinc.util
    _orig_fix = thinc.util.fix_random_seed
    thinc.util.fix_random_seed = lambda seed: _orig_fix(int(seed) % (2**32) if isinstance(seed, int) else seed)
except Exception:
    pass
