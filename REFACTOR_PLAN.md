# Security Code Modularity Refactor Plan

## Overview
Extract all security code from `app.py` into a dedicated `security.py` module to achieve production-grade separation of concerns (9/10 modularity).

## Goal
- Security logic is completely isolated from business logic
- Easy to modify security policies without touching Flask routes
- Reusable security components across the application
- Clear responsibility boundaries
- FYP-quality architectural design

---

## Phase 1: Create src/web/security.py Module

### 1.1 Create File Structure
```
src/web/
├── app.py (refactored - clean imports from security)
├── security.py (NEW - all security code)
└── ...
```

### 1.2 Security Components to Extract

#### Component A: SecurityConfig (Centralized Constants)
**Source:** Lines 41-99 in app.py
**Includes:**
- `MAX_SESSIONS` (200)
- `_RATE_LIMITS` (10/60 for init, 60/60 for chat)
- `APP_CONFIG` (max message length, session timeouts)
- Rate limiting storage (`_RATE_STORE`, `_RATE_LOCK`)
- Injection RE pattern

**Design:**
```python
class SecurityConfig:
    MAX_SESSIONS = 200
    RATE_LIMITS = {
        "init": (10, 60),
        "chat": (60, 60),
    }
    # ... constants
```

#### Component B: RateLimiter (Sliding Window Rate Limiting)
**Source:** Lines 65-77 in app.py
**Includes:**
- `_is_rate_limited()` function
- Sliding window logic with deque
- Thread-safe access with locks

**Design:**
```python
class RateLimiter:
    """Thread-safe sliding window rate limiter per IP + bucket."""
    def __init__(self, limits: dict):
        self.limits = limits
        self._store = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, ip: str, bucket: str) -> bool:
        """Check if (ip, bucket) has exceeded rate limit."""
        # ... implementation
```

**Decorator:**
```python
def require_rate_limit(bucket: str):
    """Decorator for Flask routes to apply rate limiting."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = _client_ip()
            if rate_limiter.is_limited(ip, bucket):
                return jsonify({"error": "Too many requests..."}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
```

#### Component C: PromptInjectionValidator (Input Sanitization)
**Source:** Lines 88-112 in app.py
**Includes:**
- `_INJECTION_RE` regex pattern
- `_sanitize_message()` function
- Injection detection logging

**Design:**
```python
class PromptInjectionValidator:
    """Detects and strips prompt injection patterns."""
    INJECTION_PATTERN = re.compile(...)

    @staticmethod
    def sanitize(text: str) -> str:
        """Strip injection patterns, log on match."""
        # ... implementation

    @staticmethod
    def contains_injection(text: str) -> bool:
        """Check if text contains injection patterns."""
        # ... implementation
```

#### Component D: SecurityHeadersMiddleware (Response Headers)
**Source:** Lines 115-128 in app.py
**Includes:**
- `set_security_headers()` function
- X-Frame-Options, X-Content-Type-Options, etc.

**Design:**
```python
class SecurityHeadersMiddleware:
    """Flask after_request handler for security headers."""
    HEADERS = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        # ...
    }

    @staticmethod
    def apply(response):
        """Add security headers to response."""
        # ... implementation

    # Alternatively, return a decorator for @app.after_request
```

#### Component E: InputValidator (Message & Field Validation)
**Source:** Lines 143-150 in app.py + Lines 541-556 (knowledge validation)
**Includes:**
- `_validate_message()` function
- Knowledge field validation from /api/knowledge route

**Design:**
```python
class InputValidator:
    """General input validation utilities."""

    @staticmethod
    def validate_message(text: str, max_length: int = 1000) -> tuple:
        """Validate chat message. Returns (clean_text, error_response)."""
        # ... implementation

    @staticmethod
    def validate_knowledge_field(key: str, value: str) -> tuple:
        """Validate knowledge update fields. Returns (clean_value, error)."""
        # ... implementation
```

#### Component F: SessionSecurityManager (Session Management)
**Source:** Lines 130-138 + session-related functions
**Includes:**
- Session storage dict
- Thread-safe access with locks
- Session capacity checking

**Design:**
```python
class SessionSecurityManager:
    """Thread-safe session lifecycle management with capacity limits."""

    def __init__(self, max_sessions: int = 200):
        self.sessions = {}
        self.max_sessions = max_sessions
        self._lock = threading.Lock()

    def get(self, session_id: str):
        """Retrieve session safely."""
        # ... implementation

    def create(self, session_id: str, bot) -> bool:
        """Create new session. Returns False if capacity exceeded."""
        # ... implementation

    def cleanup_expired(self, timeout_minutes: int = 60):
        """Remove idle sessions (background thread safe)."""
        # ... implementation
```

#### Component G: ClientIPExtractor (Request Handling)
**Source:** Lines 80-85 in app.py
**Includes:**
- `_client_ip()` function
- X-Forwarded-For handling for proxied requests

**Design:**
```python
class ClientIPExtractor:
    """Extract client IP from request, handling proxies."""

    @staticmethod
    def get_ip(request_obj) -> str:
        """Best-effort client IP extraction."""
        # ... implementation
```

---

## Phase 2: Refactor app.py

### 2.1 Import Security Module
Replace inline imports with:
```python
from security import (
    SecurityConfig,
    RateLimiter,
    PromptInjectionValidator,
    SecurityHeadersMiddleware,
    InputValidator,
    SessionSecurityManager,
    ClientIPExtractor,
    require_rate_limit,  # Decorator
    get_client_ip,       # Reexport
)
```

### 2.2 Update Global State
Replace:
```python
# OLD: Scattered in app.py
MAX_SESSIONS = 200
_RATE_STORE = defaultdict(deque)
sessions = {}
_session_lock = threading.Lock()
```

With:
```python
# NEW: Use security module
config = SecurityConfig()
rate_limiter = RateLimiter(config.RATE_LIMITS)
session_manager = SessionSecurityManager(config.MAX_SESSIONS)
injection_validator = PromptInjectionValidator()
```

### 2.3 Update Route Handlers
Replace inline security checks with module calls:

**Before (Lines 270 - inline rate limit check):**
```python
@app.route('/api/chat', methods=['POST'])
def chat():
    if _is_rate_limited(_client_ip(), "chat"):
        return jsonify({"error": "Too many messages..."}), 429
```

**After (using decorator):**
```python
@app.route('/api/chat', methods=['POST'])
@require_rate_limit("chat")
def chat():
    # Rate limit already checked by decorator
```

**Before (Lines 291-295 - inline session cap check):**
```python
with _session_lock:
    if len(sessions) >= MAX_SESSIONS:
        app.logger.warning(...)
        return jsonify({"error": "Server at capacity..."}), 503
```

**After (using security manager):**
```python
if not session_manager.can_create():
    return jsonify({"error": "Server at capacity..."}), 503
```

### 2.4 Update Message Validation
Replace inline calls:
```python
# Before
user_message, err = _validate_message(data.get('message', ''))

# After
user_message, err = InputValidator.validate_message(
    data.get('message', ''),
    max_length=config.MAX_MESSAGE_LENGTH
)
```

### 2.5 Update Injection Detection
Replace inline calls:
```python
# Before
text = _sanitize_message(text.strip())

# After
text = injection_validator.sanitize(text.strip())
```

### 2.6 Wire Security Headers Middleware
Replace inline decorator:
```python
# Before
@app.after_request
def set_security_headers(response):
    # ... 5 header assignments

# After
app.after_request(SecurityHeadersMiddleware.apply)
# OR create a decorator that returns a function
```

---

## Phase 3: Implementation Tasks

### Task 1: Create security.py with all 7 components
- Import required modules (threading, deque, re, logging, functools)
- Implement SecurityConfig dataclass
- Implement RateLimiter class with thread-safe deque operations
- Implement PromptInjectionValidator with regex pattern
- Implement SecurityHeadersMiddleware
- Implement InputValidator with knowledge field validation logic (copy from lines 541-556)
- Implement SessionSecurityManager with capacity limits
- Implement ClientIPExtractor
- Export decorator functions (require_rate_limit, get_client_ip)
- **Estimated lines:** 280-320 well-organized, documented code

### Task 2: Update app.py
- Remove all security function definitions (lines 65-128, save 64 lines)
- Remove global security variables (lines 44, 51, 57-58, 135-138)
- Add import statement at top
- Replace all inline security calls with module method calls
- Update route decorators to use @require_rate_limit
- Replace session lock access with session_manager API calls
- **Estimated changes:** 20-30 replace operations, net savings ~100-150 lines

### Task 3: Update Session Management Functions
- `get_session()` → `session_manager.get()`
- `set_session()` → `session_manager.set()`
- `cleanup_expired_sessions()` → `session_manager.cleanup_expired()`
- `_client_ip()` → `get_client_ip()` (reexported from security module)
- `_validate_message()` → `InputValidator.validate_message()`
- `_sanitize_message()` → `injection_validator.sanitize()`

### Task 4: Update /api/knowledge Route Validation
- Move validation logic from lines 541-556 to `InputValidator.validate_knowledge_field()`
- Update route handler to call validator instead of inline checks
- Maintain exact validation logic (field presence, length limits, JSON parsing)

---

## Phase 4: Testing Strategy

### Type of Tests
1. **Unit Tests (security.py components)**
   - `test_security.py` (new file)
   - Test RateLimiter with concurrent request simulation
   - Test PromptInjectionValidator with payload examples
   - Test InputValidator with edge cases
   - Test SessionSecurityManager capacity limits

2. **Integration Tests (app.py + security.py)**
   - `/api/init` with rate limiting applied
   - `/api/chat` with injection detection applied
   - `/api/knowledge` with field validation applied
   - Session creation with capacity ceiling

3. **Regression Tests**
   - Run existing test suites (test_all.py, test_human_flow.py, etc.)
   - Verify no functionality broken
   - Verify security behavior unchanged

### Test Approach
- Create `src/web/test_security.py` for security module unit tests
- Run existing tests to verify app.py behavior unchanged
- No changes to core chatbot logic (flow.py, content.py, analysis.py)

---

## Phase 5: Validation & Cleanup

### Validation Checklist
- [ ] security.py imports cleanly without circular dependencies
- [ ] All security functions moved and tested
- [ ] app.py imports from security.py successfully
- [ ] All route handlers use security module functions
- [ ] Rate limiting works (test with rapid requests)
- [ ] Injection detection works (test with payload)
- [ ] Session capacity ceiling enforced
- [ ] Security headers present in responses
- [ ] Input validation rejects invalid data
- [ ] Existing tests pass (150/156)

### Cleanup
- Remove inline security function definitions from app.py
- Remove security constants from app.py module level
- Verify no duplicate code between app.py and security.py
- Add docstrings to security.py explaining each component

---

## Success Criteria

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Modularity Score | 6.5/10 | 9/10 | ✓ |
| Security Code in app.py | ~150 lines (mixed) | 0 lines (all in module) | ✓ |
| Code Organization | Scattered | Centralized & reusable | ✓ |
| New Module Lines | N/A | 280-320 | ✓ |
| app.py Line Savings | N/A | ~100-150 | ✓ |
| Tests Passing | 150/156 | 150/156 (unchanged) | ✓ |
| Breaking Changes | N/A | None | ✓ |

---

## Risk Mitigation

### Risk 1: Circular Import
**Mitigation:** security.py has NO dependencies on app.py (one-way import only)

### Risk 2: Lost Functionality
**Mitigation:** Each function extracted as-is; behavior unchanged. Regression tests verify.

### Risk 3: Thread Safety Broken
**Mitigation:** Re-implement thread-safe patterns in RateLimiter and SessionSecurityManager with explicit locks

### Risk 4: Rate Limiting Decorator Complexity
**Mitigation:** Use functools.wraps to preserve Flask metadata; test with mock requests

---

## Timeline Estimate
- **Phase 1:** 45 min (create security.py with all components)
- **Phase 2:** 30 min (refactor app.py imports and calls)
- **Phase 3:** 20 min (update session management, knowledge validation)
- **Phase 4:** 30 min (write tests, run regression suite)
- **Phase 5:** 15 min (validation, cleanup, documentation)

**Total: ~2-2.5 hours** (faster than Option B estimate due to clear scope)

---

## Success Outcome
- ✅ All security code isolated in single, reusable module
- ✅ app.py clean and readable (business logic only)
- ✅ Easy to modify security policies without touching routes
- ✅ FYP-quality architectural design demonstrating separation of concerns
- ✅ Production-grade modularity (9/10)
- ✅ Zero breaking changes to existing functionality
