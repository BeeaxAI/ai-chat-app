"""Simple in-memory rate limiter middleware."""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.window = 60  # seconds
        self.max_requests = settings.MAX_REQUESTS_PER_MINUTE

    async def dispatch(self, request: Request, call_next):
        # Only rate limit API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Use IP + auth token as key
        client_ip = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization", "")
        key = f"{client_ip}:{auth[:20]}"

        now = time.time()
        # Clean old entries
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]

        if len(self.requests[key]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per minute.",
            )

        self.requests[key].append(now)
        return await call_next(request)
