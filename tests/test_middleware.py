"""
Tests for management service middleware components.
"""
import pytest
from unittest.mock import Mock, patch
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.management.middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    CorsMiddleware,
)


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = SecurityHeadersMiddleware(self.get_response)

    def test_adds_security_headers(self):
        """Test that security headers are added to responses."""
        request = self.factory.get("/")
        response = self.middleware(request)

        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response
        assert "Strict-Transport-Security" in response

    def test_preserves_existing_headers(self):
        """Test that existing headers are preserved."""
        request = self.factory.get("/")
        self.get_response.return_value = HttpResponse()
        self.get_response.return_value["Custom-Header"] = "custom-value"

        response = self.middleware(request)

        assert response["Custom-Header"] == "custom-value"
        assert response["X-Content-Type-Options"] == "nosniff"


class TestRequestLoggingMiddleware:
    """Test request logging middleware."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RequestLoggingMiddleware(self.get_response)

    @patch("apps.management.middleware.logger")
    def test_logs_request_info(self, mock_logger):
        """Test that request information is logged."""
        request = self.factory.get("/test-path/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        self.middleware(request)

        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "GET" in call_args
        assert "/test-path/" in call_args

    @patch("apps.management.middleware.logger")
    def test_logs_response_status(self, mock_logger):
        """Test that response status is logged."""
        request = self.factory.get("/")
        self.get_response.return_value = HttpResponse(status=404)

        self.middleware(request)

        assert mock_logger.info.call_count >= 1

    @patch("apps.management.middleware.logger")
    def test_handles_exception_during_logging(self, mock_logger):
        """Test that exceptions during logging don't break the request."""
        mock_logger.info.side_effect = Exception("Logging failed")
        request = self.factory.get("/")

        # Should not raise an exception
        response = self.middleware(request)

        assert response.status_code == 200


class TestCorsMiddleware:
    """Test CORS middleware."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = CorsMiddleware(self.get_response)

    @override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:3000"])
    def test_adds_cors_headers_for_allowed_origin(self):
        """Test that CORS headers are added for allowed origins."""
        request = self.factory.get("/auth/login")
        request.META["HTTP_ORIGIN"] = "http://localhost:3000"

        response = self.middleware(request)

        assert response["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert response["Access-Control-Allow-Credentials"] == "true"
        assert "GET, POST, PUT, DELETE, OPTIONS" in response["Access-Control-Allow-Methods"]

    @override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:3000"])
    def test_no_cors_headers_for_disallowed_origin(self):
        """Test that CORS headers are not added for disallowed origins."""
        request = self.factory.get("/auth/login")
        request.META["HTTP_ORIGIN"] = "http://malicious-site.com"

        response = self.middleware(request)

        assert "Access-Control-Allow-Origin" not in response

    def test_no_cors_headers_for_non_auth_paths(self):
        """Test that CORS headers are not added for non-auth paths."""
        request = self.factory.get("/api/data")
        request.META["HTTP_ORIGIN"] = "http://localhost:3000"

        response = self.middleware(request)

        assert "Access-Control-Allow-Origin" not in response

    def test_handles_missing_origin_header(self):
        """Test that missing origin header doesn't cause errors."""
        request = self.factory.get("/auth/login")
        # No HTTP_ORIGIN in META

        # Should not raise an exception
        response = self.middleware(request)

        assert response.status_code == 200


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RateLimitMiddleware(self.get_response)

    @patch("apps.management.middleware.cache")
    def test_allows_normal_requests(self, mock_cache):
        """Test that normal requests are allowed."""
        mock_cache.get.return_value = 5  # Below limit
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = self.middleware(request)

        assert response.status_code == 200
        mock_cache.set.assert_called()  # Should increment counter

    @patch("apps.management.middleware.cache")
    def test_blocks_excessive_requests(self, mock_cache):
        """Test that excessive requests are blocked."""
        mock_cache.get.return_value = 1000  # Above limit
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = self.middleware(request)

        assert response.status_code == 429

    @patch("apps.management.middleware.cache")
    def test_handles_cache_failure(self, mock_cache):
        """Test that cache failures allow requests through."""
        mock_cache.get.side_effect = Exception("Cache unavailable")
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Should allow request when cache fails
        response = self.middleware(request)

        assert response.status_code == 200

    def test_different_ips_tracked_separately(self):
        """Test that different IP addresses are tracked separately."""
        with patch("apps.management.middleware.cache") as mock_cache:
            mock_cache.get.return_value = 5

            request1 = self.factory.get("/")
            request1.META["REMOTE_ADDR"] = "127.0.0.1"

            request2 = self.factory.get("/")
            request2.META["REMOTE_ADDR"] = "192.168.1.1"

            self.middleware(request1)
            self.middleware(request2)

            # Should have different cache keys for different IPs
            assert mock_cache.get.call_count == 2
            call_args = [call[0][0] for call in mock_cache.get.call_args_list]
            assert call_args[0] != call_args[1]

    @patch("apps.management.middleware.cache")
    def test_different_rate_limits_for_endpoints(self, mock_cache):
        """Test different rate limits for different endpoints."""
        mock_cache.get.return_value = 1

        # Test login endpoint (5 requests/min)
        request1 = self.factory.post("/auth/login")
        request1.META["REMOTE_ADDR"] = "127.0.0.1"

        response1 = self.middleware(request1)
        assert response1.status_code == 200

        # Test other auth endpoint (30 requests/min)
        request2 = self.factory.get("/auth/profile")
        request2.META["REMOTE_ADDR"] = "127.0.0.1"

        response2 = self.middleware(request2)
        assert response2.status_code == 200

    def test_non_auth_paths_not_rate_limited(self):
        """Test that non-auth paths are not rate limited."""
        request = self.factory.get("/api/data")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = self.middleware.process_request(request)

        assert response is None  # No rate limiting applied

    def test_admin_paths_not_rate_limited(self):
        """Test that admin paths are not rate limited."""
        request = self.factory.get("/admin/users/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = self.middleware.process_request(request)

        assert response is None  # No rate limiting applied


@pytest.mark.django_db
class TestMiddlewareIntegration:
    """Test middleware integration with Django."""

    def test_middleware_order(self):
        """Test that middleware is properly configured in settings."""
        from django.conf import settings

        middleware = settings.MIDDLEWARE

        # Security headers should come early
        security_index = next(i for i, m in enumerate(middleware)
                            if "SecurityHeadersMiddleware" in m)

        # Request logging should come after security
        logging_index = next(i for i, m in enumerate(middleware)
                           if "RequestLoggingMiddleware" in m)

        assert security_index < logging_index

    def test_middleware_can_be_imported(self):
        """Test that all middleware classes can be imported."""
        from apps.management.middleware import (
            SecurityHeadersMiddleware,
            RequestLoggingMiddleware,
            RateLimitMiddleware,
            CorsMiddleware,
        )

        assert SecurityHeadersMiddleware is not None
        assert RequestLoggingMiddleware is not None
        assert RateLimitMiddleware is not None
        assert CorsMiddleware is not None