import os, time

os.environ.setdefault("TZ", "Europe/London")
try:
    time.tzset()
except:
    pass

try:
    import thinc.util as _thinc_util
    _orig_fix = _thinc_util.fix_random_seed
    def _safe_fix_random_seed(seed):
        try:
            return _orig_fix(seed)
        except:
            try:
                s = int(seed) % (2 ** 32)
            except:
                s = 0
            return _orig_fix(s)
    _thinc_util.fix_random_seed = _safe_fix_random_seed
except:
    pass

def pytest_configure(config):
    return
