# Rate limiter configuration for Vibe2Crazy

from pyrate_limiter import Limiter, Rate, Duration
from fastapi_limiter.depends import RateLimiter
from fastapi_limiter.identifier import default_identifier
from fastapi_limiter.callback import default_callback

# Create limiter with in-memory storage (default)
# Auth endpoints: 5 requests per minute
auth_limiter = Limiter(Rate(5, Duration.MINUTE))

# Default endpoints: 100 requests per minute
default_limiter = Limiter(Rate(100, Duration.MINUTE))

# Create RateLimiter instances for dependency injection
auth_rate_limiter = RateLimiter(limiter=auth_limiter, identifier=default_identifier, callback=default_callback)
default_rate_limiter = RateLimiter(limiter=default_limiter, identifier=default_identifier, callback=default_callback)