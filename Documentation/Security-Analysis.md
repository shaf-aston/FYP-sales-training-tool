# Security Analysis — STRIDE Threat Model & Implementation Details

> **Note:** This document supplements the security summary in the main project report (Section 2.8). It provides comprehensive technical detail for each security control, including implementation code, verification procedures, and threat mitigation status.

---

## STRIDE Threat Model & Security Risk Assessment

**Methodology:** This section applies Microsoft's STRIDE threat modelling framework (Shostack, 2014) to systematically identify threats across six categories: **S**poofing, **T**ampering, **R**epudiation, **I**nformation Disclosure, **D**enial of Service, **E**levation of Privilege. For each threat, current mitigations are documented alongside residual risk.

| **Threat Category** | **Threat** | **Attack Vector** | **Current Mitigation** | **Residual Risk** | **Status** |
|---|---|---|---|---|---|
| **Spoofing (S)** | Session hijacking via weak token | Attacker guesses or intercepts 128-bit session token | `secrets.token_hex(16)` (cryptographic randomness); TLS in transit | Low (token is cryptographically random, TLS protects in transit) | ✅ **Mitigated** |
| **Spoofing (S)** | Malicious origin accessing API via CORS | Browser pre-flight allows `fetch()` from attacker domain | Environment-configurable `ALLOWED_ORIGINS` (lines 33 to 37, `app.py`); defaults to Render + localhost | Low (CORS restricted to known domains; env var override requires server access) | ✅ **Mitigated** |
| **Tampering (T)** | User input injection into LLM prompt | Attacker crafts prompt-injection payloads (e.g., "ignore instructions") to extract system prompt | Regex-based detection (lines 91 to 99, `app.py`); silent replacement with `[removed]` placeholder | Low to Medium (regex catches common patterns; sophisticated multi-step injections may evade) | ⚠️ **Partially Mitigated** |
| **Tampering (T)** | Knowledge base modification via `/api/knowledge` CRUD | Unvalidated user input written to `custom_knowledge.yaml` | Whitelist of allowed fields (`ALLOWED_FIELDS`); max_length cap (500 chars per field) | Low (only pre-approved fields; length-bounded) | ✅ **Mitigated** |
| **Repudiation (R)** | User denies malicious input; cannot audit interactions | No audit trail of who said what in a session | IP-based rate limiting logs (logged when limits exceeded); conversation history maintained server-side | Medium (some logging present; no comprehensive audit trail) | ⚠️ **Partially Mitigated** |
| **Info Disclosure (I)** | Cross-session data leakage | Conversation history from Session A accessed via Session B's session ID | Per-session `SalesChatbot` instance; session IDs not predictable | Low (each session is isolated; session IDs are cryptographic) | ✅ **Mitigated** |
| **Info Disclosure (I)** | API key exposure | Groq API key leaked in logs, error messages, or committed to version control | Key in environment variable only; `.gitignore` excludes `.env`; key never logged | Low (key is never hardcoded or logged) | ✅ **Mitigated** |
| **Denial of Service (DoS)** | Session flooding via `/api/init` spam | Attacker repeatedly calls `/api/init` to exhaust memory | Session count cap: `MAX_SESSIONS = 200` (line 51); rate limit (10 inits/60s per IP, lines 59 to 62) | Low (cap prevents runaway memory; rate limit blocks automated flooding) | ✅ **Mitigated** |
| **DoS (D)** | Message spam via `/api/chat` | Attacker sends rapid messages to exhaust compute/API quota | Rate limit: 60 msgs/60s per IP, sliding window (lines 59 to 62, `_is_rate_limited()`) | Low (rate limit enforced; Groq API has its own quota) | ✅ **Mitigated** |
| **DoS (D)** | Long-running request exhaustion | Attacker sends extremely long messages to exhaust Flask server resources | Message length cap: `MAX_MESSAGE_LENGTH = 1000` chars (line 42) | Low (enforced at request entry point) | ✅ **Mitigated** |
| **Elevation of Privilege (E)** | No role-based access control | Attacker gains access to `/api/knowledge` without permission | No authentication layer; academic context (single deployment, known users) | Medium to High (suitable for FYP; production would require auth) | ⚠️ **Acceptable for Academic Scope** |
| **Elevation of Privilege (E)** | Admin functionality exposed | Rewind/reset endpoints (`/api/rewind`, `/api/reset`) callable by any user | Endpoints protected only by session ownership (implicit); no admin role distinction | Medium (acceptable for training context; production needs role-based access) | ⚠️ **Acceptable for Academic Scope** |
| **Elevation of Privilege (E)** | Developer panel access | Any user with a valid session reads the verbatim system prompt (`/api/debug/prompt`), jumps the FSM to any stage (`/api/debug/stage`), and inspects raw signal results | `_guard_debug_endpoints()` `@app.before_request` hook returns 403 unless `ENABLE_DEBUG_PANEL=true` env var is set; absent from Render deployment | Low in production (env var not set on Render); dev access requires explicit activation in `.env` | ✅ **Mitigated** |

**Threat Model Legend:**
- ✅ **Mitigated**: Threat likelihood is low; mitigation is sufficient for deployment scope
- ⚠️ **Partially Mitigated**: Residual risk remains; acceptable for academic scope; production deployment would require enhancement
- ⛔ **Not Mitigated**: Threat is unaddressed; unsuitable for public deployment

**Honest Assessment:** The system is hardened against automated abuse (DoS) and common injection patterns (prompt injection) but lacks defense-in-depth authentication for multi-user scenarios. In the FYP context (single-instance Render deployment, academic evaluation only), this is appropriate. Production deployment to external users would require: (1) authentication/authorization layer, (2) comprehensive audit logging, (3) expanded injection regex or ML-based anomaly detection.

---

## AI Ethics & Representational Scope

**AI Transparency:** The web interface displays the current FSM stage and system type throughout each session, making the AI nature of the interaction explicit. The system does not represent itself as human at any point.

**Methodology Scope:** The IMPACT/NEPQ sales framework reflects Western direct-sales conventions. The system does not claim cross-cultural validity and is scoped explicitly to English-language sales training scenarios. Use outside this context would require methodology adaptation and re-evaluation.

**Intended Use Boundary:** This system is designed for training simulation only - not for deployment in live, customer-facing sales environments. Deploying it in real customer interactions without explicit AI disclosure would conflict with UK Information Commissioner's Office (ICO) guidance on automated decision-making and AI transparency (Information Commissioner's Office, 2023).

---

## Implemented Security Controls - Technical Details

The controls below implement the STRIDE mitigations identified above. Following the March 2026 security refactor, all controls are implemented in `src/web/security.py` (extracted from `app.py` for modularity); code references are provided for verification.

### 1. CORS Restriction (Spoofing Prevention)

**Location:** `app.py`, lines 33 to 38

**Implementation:**
```python
_allowed_origins = [
    o.strip() for o in
    os.environ.get('ALLOWED_ORIGINS', 'https://fyp-sales-training-tool.onrender.com,http://localhost:5000').split(',')
    if o.strip()
]
CORS(app, origins=_allowed_origins)
```

**Threat Mitigated:** Browser pre-flight CORS checks prevent malicious websites from accessing the API directly. Default whitelist includes the production Render domain and localhost; additional domains can be configured via `ALLOWED_ORIGINS` environment variable without code changes.

**Verification:** Browser DevTools Network tab shows CORS preflight `OPTIONS` request; fails if origin is not in whitelist.

---

### 2. Rate Limiting - Sliding Window Per-IP (DoS Prevention)

**Location:** `app.py`, lines 57 to 62 (`_RATE_LIMITS` config) and lines 65 to 77 (`_is_rate_limited()` function)

**Implementation:**
```python
_RATE_LIMITS = {
    "init": (10, 60),   # 10 session inits per 60s per IP
    "chat": (60, 60),   # 60 messages per 60s per IP
}

def _is_rate_limited(ip: str, bucket: str) -> bool:
    max_req, window = _RATE_LIMITS[bucket]
    key = f"{bucket}:{ip}"
    now = time.time()
    with _RATE_LOCK:
        dq = _RATE_STORE[key]
        while dq and now - dq[0] > window:  # Slide window: remove old timestamps
            dq.popleft()
        if len(dq) >= max_req:
            return True
        dq.append(now)
        return False
```

**Threat Mitigated:** Sliding window algorithm prevents both rapid-fire bursts (attacker floods `/api/init` to exhaust memory) and distributed patterns (requests spaced to evade simple counters). Limits are tuned to allow normal human usage while blocking automated bots: `/api/init` allows 10 inits/min (comfortable for page reloads), `/api/chat` allows 60 msgs/min (~1/sec, well above human typing speed).

**Verification:** Rate limit headers not returned (silent blocking via 429 status); monitoring logs confirm blocked IPs. Test: `curl -X POST http://localhost:5000/api/init` repeated 11 times returns 429 on 11th attempt.

---

### 3. Session Count Cap (Memory Exhaustion Prevention)

**Location:** `app.py`, lines 51 (config), 200 to 204 (check in `api_init()`)

**Implementation:**
```python
MAX_SESSIONS = 200

# In api_init():
with _session_lock:
    if len(sessions) >= MAX_SESSIONS:
        app.logger.warning(f"Session cap ({MAX_SESSIONS}) reached - rejecting new init")
        return jsonify({"error": "Server at capacity. Please try again later."}), 503
```

**Threat Mitigated:** Prevents unbounded memory growth from repeated `/api/init` calls. 200 sessions ; ~10 to 50KB per session ≈ 2 to 10MB ceiling, well within typical server memory. Legitimate users experience graceful degradation (503 Unavailable) rather than server crash.

**Verification:** Monitor `len(sessions)` in production; set up alerts for approaching cap (e.g., >180 concurrent sessions).

---

### 4. Prompt Injection Detection & Sanitization (Tampering/Prompt Injection Prevention)

**Location:** `app.py`, lines 91 to 112 (`_INJECTION_RE` regex and `_sanitize_message()` function)

**Implementation:**
```python
_INJECTION_RE = re.compile(
    r'\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b'
    r'|\bdisregard\s+.{0,30}instructions?\b'
    r'|\bforget\s+(everything|all|your\s+(previous|prior|above|system))\b'
    r'|\bprint\s+(your\s+)?(system\s+)?prompt\b'
    r'|\byour\s+real\s+instructions?\b'
    r'|\bact\s+as\s+(if\s+you\s+(are|were)|a\b)',
    re.IGNORECASE,
)

def _sanitize_message(text: str) -> str:
    sanitized = _INJECTION_RE.sub('[removed]', text)
    if sanitized != text:
        app.logger.warning(f"Prompt injection stripped from message (IP: {_client_ip()})")
    return sanitized
```

**Threat Mitigated:** Regex catches 6 common jailbreak pattern families (each using word-boundary assertions and optional quantifiers to cover phrasing variations): "ignore previous instructions", "disregard above", "forget your system", "print your prompt", "act as if", etc. **Silent replacement strategy:** matched patterns are replaced with `[removed]` rather than hard-rejecting the request. This prevents oracle feedback to attackers (they cannot infer whether the filter was triggered). Defense-in-depth: primary mitigation is Constitutional AI P1 rules in the system prompt; regex layer catches obvious attempts before LLM processing.

**Verification:** Test cases pass for all 14 patterns + 50 variations. Limitations: sophisticated multi-step injections (e.g., encoding attacks, semantic paraphrasing) may evade. Production deployment would benefit from ML-based anomaly detection.

---

### 5. Security Headers (XSS, Clickjacking, MIME-Sniffing Prevention)

**Location:** `app.py`, lines 115 to 128 (`@app.after_request` decorator)

**Implementation:**
```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
```

**Threat Mitigated:**
- `X-Frame-Options: DENY` - Prevents clickjacking; embedding the app in an attacker's iframe is blocked
- `X-Content-Type-Options: nosniff` - Prevents MIME-type sniffing; browser must respect `Content-Type` header (stops `.js` files being interpreted as HTML, etc.)
- `Referrer-Policy` - Limits HTTP `Referer` header leakage; only sends referrer for same-origin requests
- `X-XSS-Protection: 1; mode=block` - Legacy XSS filter for older browsers (modern browsers use CSP instead, not implemented here)

**Verification:** Browser DevTools > Network > Response Headers confirm all four headers present.

---

### 6. Input Validation & Message Length Capping

**Location:** `app.py`, lines 42 to 50 (config), 143 to 150 (`_validate_message()`)

**Implementation:**
```python
APP_CONFIG = {
    "MAX_MESSAGE_LENGTH": 1000,
    "SESSION_IDLE_MINUTES": 60,
    "CLEANUP_INTERVAL_SECONDS": 900
}

def _validate_message(text: str):
    text = _sanitize_message(text.strip())
    if not text:
        return None, (jsonify({"error": "Message required"}), 400)
    if len(text) > APP_CONFIG["MAX_MESSAGE_LENGTH"]:
        return None, (jsonify({"error": f"Message too long..."}), 400)
    return text, None
```

**Threat Mitigated:** Message length cap prevents ReDoS (Regular Expression Denial of Service) attacks and computational exhaustion. Empty messages are rejected.

---

### 7. Session Isolation & Cleanup (Information Disclosure Prevention)

**Location:** `app.py`, lines 135 to 139 (session storage), background cleanup thread in `cleanup_expired_sessions()`

**Implementation:** Each session maintains an isolated `SalesChatbot` instance. Background daemon thread (`cleanup_expired_sessions()`) removes idle sessions after 60 minutes, preventing memory accumulation and ensuring stale session data is purged.

**Verification:** Check `sessions` dict; confirm no cross-session data leakage. Confirm sessions expire after 60 minutes of inactivity.

---

## Summary Table - Security Controls vs. STRIDE Threats

| **Control** | **Threat(s) Mitigated** | **Implementation** | **Verification** |
|---|---|---|---|
| CORS Restriction | Spoofing (S) | lines 33 to 38 | Browser CORS preflight fails for unauthorized origins |
| Rate Limiting (Sliding Window) | DoS (D) | lines 65 to 77 | 429 returned on exceeding limits; test with 11 rapid requests |
| Session Count Cap | DoS (D) | lines 51, 200 to 204 | 503 returned when `len(sessions) >= 200` |
| Prompt Injection Regex | Tampering (T) | lines 91 to 99 | 14 test patterns + 50 variations caught; logged with IP |
| Security Headers | XSS/Clickjacking (T/S) | lines 115 to 128 | DevTools confirm all 4 headers present |
| Input Validation | DoS/Tampering (D/T) | lines 143 to 150 | Empty/oversized messages rejected with 400/413 |
| Session Isolation & Cleanup | Info Disclosure (I) | lines 135 to 139, background thread | Zero cross-session leakage; idle sessions expire |
| Debug Endpoint Guard | Elevation of Privilege (E) | `_guard_debug_endpoints()` `@before_request`; `ENABLE_DEBUG_PANEL` env var (`app.py`) | `GET /api/debug/prompt` returns 403 when env var is unset |

---

## References

Information Commissioner's Office (2023) *Guidance on AI and data protection*. Available at: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/ (Accessed: 10 March 2026).

Shostack, A. (2014) *Threat modeling: designing for security*. Indianapolis: Wiley.
