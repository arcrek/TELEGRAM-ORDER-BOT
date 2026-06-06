"""
Shared slowapi Limiter instance.

Extracted from main.py to avoid circular imports when routers need to use the
@limiter.limit() decorator (importing from main.py would create a cycle).

main.py imports this module and assigns `app.state.limiter = limiter` plus
registers the RateLimitExceeded handler — that is all the decorator mode needs.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
