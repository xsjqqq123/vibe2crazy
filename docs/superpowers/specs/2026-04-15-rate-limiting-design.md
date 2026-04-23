# API Rate Limiting Design

## Context
vibe2crazy has no API rate limiting. Login and password endpoints are vulnerable to brute force attacks. Need to add rate limiting with different tiers for different endpoint groups.

## Requirements
- **Purpose**: Security (prevent brute force on auth endpoints)
- **Storage**: In-memory (no Redis dependency)
- **Tiers**:
  - Auth endpoints (login, change-password): 5 requests/minute/IP
  - Other API endpoints: 100 requests/minute/IP
- **Response**: 429 Too Many Requests when exceeded

## Architecture

### Library
Use `fastapi-limiter` with in-memory storage.

### Implementation

1. **`requirements.txt`** - Add `fastapi-limiter`

2. **`app/config.py`** - Add rate limit settings:
   ```python
   rate_limit_enabled: bool = True
   rate_limit_auth: str = "5/minute"
   rate_limit_default: str = "100/minute"
   ```

3. **`app/main.py`** - Initialize rate limiter on startup with in-memory backend

4. **`app/routers/auth.py`** - Apply `@limiter.limit("5/minute")` to login and change-password endpoints

5. **Other routers** - Apply `@limiter.limit("100/minute")` globally or via middleware

### Key Pattern
- Rate limit by client IP (from `request.client.host`)
- Return standard 429 JSON response with retry-after hint

## Files to Modify
- `backend/requirements.txt`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/routers/auth.py`

## Verification
1. Rapidly call POST /api/auth/login 6 times → 6th returns 429
2. Normal API usage stays under 100/min → works fine
3. Check 429 response includes rate limit headers
