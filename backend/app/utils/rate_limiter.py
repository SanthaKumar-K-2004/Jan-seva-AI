"""
Jan-Seva AI — Rate Limiter Middleware
Prevents abuse with per-IP and per-endpoint rate limiting.
Uses in-memory store (no Redis needed — zero cost).
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.
    Default: 60 requests per minute per IP.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window = 60  # seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        self._store[client_ip] = [
            t for t in self._store[client_ip] if now - t < self.window
        ]

        # Check rate
        if len(self._store[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a minute and try again.",
            )

        # Record request
        self._store[client_ip].append(now)

        response = await call_next(request)
        return response
