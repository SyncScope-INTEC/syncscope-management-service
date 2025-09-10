import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Add security headers to all responses"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS for HTTPS
        if request.is_secure():
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # CSP for API responses
        if request.path.startswith("/auth/"):
            response["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'none'; object-src 'none'"
            )

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Custom rate limiting middleware"""

    def process_request(self, request):
        if not getattr(settings, "RATELIMIT_ENABLE", True):
            return None

        # Skip rate limiting for admin and static files
        if request.path.startswith("/admin/") or request.path.startswith("/static/"):
            return None

        # Get client IP
        ip = self.get_client_ip(request)

        # Different rate limits for different endpoints
        if request.path.startswith("/auth/login") or request.path.startswith(
            "/auth/register"
        ):
            limit = 5  # 5 requests per minute for login/register
            window = 60
        elif request.path.startswith("/auth/"):
            limit = 30  # 30 requests per minute for other auth endpoints
            window = 60
        else:
            return None

        # Create cache key
        cache_key = f"ratelimit:{ip}:{request.path}"

        # Get current count
        current_count = cache.get(cache_key, 0)

        if current_count >= limit:
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Limit: {limit}/{window}s",
                },
                status=429,
            )

        # Increment counter
        cache.set(cache_key, current_count + 1, window)

        # Store rate limit info for response headers
        request._rate_limit_info = {
            "limit": limit,
            "remaining": max(0, limit - current_count - 1),
            "reset": window,
        }

        return None

    def process_response(self, request, response):
        # Add rate limit headers if info is available
        if hasattr(request, "_rate_limit_info"):
            info = request._rate_limit_info
            response["X-RateLimit-Limit"] = str(info["limit"])
            response["X-RateLimit-Remaining"] = str(info["remaining"])
            response["X-RateLimit-Reset"] = str(info["reset"])

        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")


class RequestLoggingMiddleware:
    """Log API requests for monitoring"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        # Log request
        logger.info(
            f"Request: {request.method} {request.path} from {self.get_client_ip(request)}"
        )

        response = self.get_response(request)

        # Log response
        duration = time.time() - start_time
        logger.info(f"Response: {response.status_code} in {duration:.3f}s")

        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")


class CorsMiddleware:
    """Custom CORS middleware for better control"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Handle CORS for auth endpoints
        if request.path.startswith("/auth/"):
            origin = request.META.get("HTTP_ORIGIN")

            # Check if origin is allowed
            allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])

            if origin in allowed_origins:
                response["Access-Control-Allow-Origin"] = origin
                response["Access-Control-Allow-Credentials"] = "true"
                response["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE, OPTIONS"
                )
                response["Access-Control-Allow-Headers"] = (
                    "Authorization, Content-Type, X-Requested-With"
                )

        return response
