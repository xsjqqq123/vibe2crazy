# API Rate Limiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add rate limiting to protect auth endpoints from brute force attacks using fastapi-limiter with in-memory storage.

**Architecture:** Use fastapi-limiter library with in-memory storage backend. Apply different rate limits to auth endpoints (strict) vs other endpoints (loose). Configure via app.config settings.

**Tech Stack:** fastapi-limiter, in-memory storage (no Redis)

---

## File Structure

| File | Purpose |
|------|---------|
| `backend/requirements.txt` | Add fastapi-limiter dependency |
| `backend/app/config.py` | Add rate limit config settings |
| `backend/app/main.py` | Initialize rate limiter middleware |
| `backend/app/routers/auth.py` | Apply strict rate limit to auth endpoints |
| `backend/app/routers/*.py` | Apply default rate limit to other endpoints |

---

## Tasks

### Task 1: Add fastapi-limiter dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add fastapi-limiter to requirements**

Modify `backend/requirements.txt` to add:
```
fastapi-limiter>=0.1.5
```

- [ ] **Step 2: Install the dependency**

Run: `cd backend && source venv/bin/activate && pip install fastapi-limiter>=0.1.5`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add fastapi-limiter dependency"
```

---

### Task 2: Add rate limit config settings

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Read current config.py**

Read `backend/app/config.py` to find the Settings class.

- [ ] **Step 2: Add rate limit settings to Settings class**

Add these fields to the Settings class:
```python
# Rate limiting
rate_limit_enabled: bool = True
rate_limit_auth: str = "5/minute"
rate_limit_default: str = "100/minute"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add rate limit config settings"
```

---

### Task 3: Initialize rate limiter in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Read main.py imports section**

Read `backend/app/main.py` lines 1-25.

- [ ] **Step 2: Add limiter imports**

Add after existing imports:
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
```

Note: We import redis.asyncio but will use in-memory storage instead.

- [ ] **Step 3: Create rate limiter dependency function**

Add this function before `get_frontend_path()`:
```python
from fastapi import Request

async def default_rate_limit_callback(request: Request, response: JSONResponse):
    response.body = b'{"detail":"Too Many Requests"}'
    response.headers["X-RateLimit-Limit"] = settings.rate_limit_default
    return response
```

- [ ] **Step 4: Add limiter initialization in lifespan**

Find the lifespan function (or create one) and add:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize rate limiter with in-memory storage
    if settings.rate_limit_enabled:
        await FastAPILimiter.init()
    yield
    # Cleanup
    await FastAPILimiter.close()
```

- [ ] **Step 5: Add lifespan to app**

Add `lifespan=lifespan` to FastAPI app creation:
```python
app = FastAPI(
    ...
    lifespan=lifespan
)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: initialize fastapi-limiter with in-memory storage"
```

---

### Task 4: Apply strict rate limit to auth endpoints

**Files:**
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Read current auth.py**

Read `backend/app/routers/auth.py` to see the login and change-password endpoints.

- [ ] **Step 2: Add limiter import and dependency**

Add after existing imports:
```python
from fastapi_limiter import Limiter
from fastapi_limiter.depends import RateLimiter
from fastapi import Request
```

Add this function after imports:
```python
def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    return request.client.host if request.client else "unknown"

# Create limiter instance
limiter = Limiter(key_func=get_client_ip)
```

- [ ] **Step 3: Apply rate limit to login endpoint**

Find the login endpoint and add decorator:
```python
@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.rate_limit_auth)
async def login(
    request: Request,
    login_request: LoginRequest,
    db: Session = Depends(get_db)
):
```

- [ ] **Step 4: Apply rate limit to change-password endpoint**

Find the change-password endpoint and add decorator:
```python
@router.post("/change-password", response_model=ChangePasswordResponse)
@limiter.limit(settings.rate_limit_auth)
async def change_password(
    request: Request,
    request_body: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
```

- [ ] **Step 5: Update LoginRequest reference**

Change `request: LoginRequest` to `login_request: LoginRequest` in login endpoint since `request` is now FastAPI Request object.

- [ ] **Step 6: Update LoginRequest usage inside login function**

Replace all `request.password` with `login_request.password` inside the login function body.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/auth.py
git commit -m "feat: apply strict rate limit to auth endpoints"
```

---

### Task 5: Apply default rate limit to other endpoints (optional, for consistency)

**Files:**
- Modify: All other router files (projects, tasks, files, git, etc.)

- [ ] **Step 1: Apply default rate limit to critical routers**

For `backend/app/routers/tasks.py`, `backend/app/routers/projects.py`, `backend/app/routers/files.py`:

Add at top of each file:
```python
from fastapi_limiter import Limiter
from fastapi import Request
from app.config import settings

def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=get_client_ip)
```

Add decorator to POST/PUT/DELETE endpoints:
```python
@router.post("/", ...)
@limiter.limit(settings.rate_limit_default)
async def create_...(...):
```

Note: GET endpoints typically don't need rate limiting as they don't modify state.

- [ ] **Step 2: Commit each changed router**

```bash
git add backend/app/routers/tasks.py backend/app/routers/projects.py backend/app/routers/files.py
git commit -m "feat: apply default rate limit to critical endpoints"
```

---

## Verification

1. **Test auth rate limit:**
   ```bash
   # Reset password in DB first
   curl -X POST http://localhost:8863/api/auth/change-password \
     -H "Content-Type: application/json" \
     -d '{"new_password": "TestPass123"}'

   # Try login 6 times quickly
   for i in {1..6}; do
     curl -s -X POST http://localhost:8863/api/auth/login \
       -H "Content-Type: application/json" \
       -d '{"password": "TestPass123"}'
   done
   ```
   Expected: First 5 return 200/401, 6th returns 429 with `{"detail":"Too Many Requests"}`

2. **Test normal API still works:**
   ```bash
   # Call a simple GET endpoint multiple times
   curl -s http://localhost:8863/api/auth/password-status
   ```
   Expected: Returns normally (under 100/min limit)

3. **Test rate limit resets:**
   ```bash
   # Wait 60 seconds, then try again
   sleep 60
   curl -s -X POST http://localhost:8863/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"password": "TestPass123"}'
   ```
   Expected: Returns 200/401 (rate limit reset after 1 minute)

---

## Notes

- Rate limits are per-IP address
- In-memory storage means limits reset on server restart
- Auth endpoints get 5/minute, other endpoints get 100/minute
- fastapi-limiter auto-applies 429 status code with default message