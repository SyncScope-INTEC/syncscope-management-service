"""
Tests for database mixins and serverless handling.
"""

from unittest.mock import Mock, patch

import pytest
from django.db import transaction
from django.test import TestCase, override_settings

from apps.management.db_mixins import (
    RetryableManager,
    RetryableModelMixin,
    RetryableUserManager,
    ServerlessViewMixin,
)


class TestRetryableModelMixin:
    """Test retryable model mixin functionality."""

    def setup_method(self):
        # Create a test model class with the mixin
        from django.db import models

        class TestModel(RetryableModelMixin, models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test"

        self.TestModel = TestModel
        self.instance = TestModel()

    @patch("apps.management.db_mixins.database_retry")
    def test_save_with_retry(self, mock_retry):
        """Test that save operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.instance.__class__.__bases__[1], "save"):
            self.instance.save()
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_delete_with_retry(self, mock_retry):
        """Test that delete operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.instance.__class__.__bases__[1], "delete"):
            self.instance.delete()
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_refresh_from_db_with_retry(self, mock_retry):
        """Test that refresh_from_db operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.instance.__class__.__bases__[1], "refresh_from_db"):
            self.instance.refresh_from_db()
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_objects_get_with_retry(self, mock_retry):
        """Test that objects.get operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.TestModel.objects, "get"):
            self.TestModel.objects_get(id=1)
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_objects_create_with_retry(self, mock_retry):
        """Test that objects.create operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.TestModel.objects, "create"):
            self.TestModel.objects_create(name="test")
            mock_retry.assert_called()


class TestServerlessViewMixin:
    """Test serverless view mixin functionality."""

    def setup_method(self):
        from django.views import View

        class TestView(ServerlessViewMixin, View):
            pass

        self.view = TestView()

    @patch("config.database_retry.DatabaseHealthCheck")
    @patch("config.database_retry.close_old_connections")
    def test_dispatch_healthy_database(self, mock_close_connections, mock_health_check):
        """Test dispatch with healthy database."""
        mock_health_check.is_healthy.return_value = True

        mock_request = Mock()
        mock_super_dispatch = Mock(return_value="response")

        with patch.object(self.view.__class__.__bases__[1], "dispatch", mock_super_dispatch):
            result = self.view.dispatch(mock_request)

        assert result == "response"
        mock_health_check.is_healthy.assert_called_once()
        mock_close_connections.assert_not_called()

    @patch("config.database_retry.DatabaseHealthCheck")
    @patch("config.database_retry.close_old_connections")
    def test_dispatch_unhealthy_database_recovers(self, mock_close_connections, mock_health_check):
        """Test dispatch with unhealthy database that recovers."""
        mock_health_check.is_healthy.side_effect = [False, True]

        mock_request = Mock()
        mock_super_dispatch = Mock(return_value="response")

        with patch.object(self.view.__class__.__bases__[1], "dispatch", mock_super_dispatch):
            result = self.view.dispatch(mock_request)

        assert result == "response"
        mock_close_connections.assert_called_once()

    @patch("config.database_retry.DatabaseHealthCheck")
    @patch("config.database_retry.close_old_connections")
    def test_dispatch_database_unavailable(self, mock_close_connections, mock_health_check):
        """Test dispatch with permanently unavailable database."""
        mock_health_check.is_healthy.return_value = False

        mock_request = Mock()

        response = self.view.dispatch(mock_request)

        assert response.status_code == 503
        assert "Service temporarily unavailable" in str(response.data)

    @patch("config.database_retry.DatabaseHealthCheck")
    @patch("config.database_retry.is_retryable_error")
    def test_handle_exception_retryable(self, mock_is_retryable, mock_health_check):
        """Test handle_exception with retryable error."""
        mock_is_retryable.return_value = True
        mock_exc = Exception("Database error")

        with patch.object(self.view.__class__.__bases__[1], "handle_exception") as mock_super:
            self.view.handle_exception(mock_exc)

        mock_health_check.mark_unhealthy.assert_called_once()
        mock_super.assert_called_once_with(mock_exc)


class TestRetryableManager:
    """Test retryable manager functionality."""

    def setup_method(self):
        self.manager = RetryableManager()

    @patch("apps.management.db_mixins.database_retry")
    def test_get_with_retry(self, mock_retry):
        """Test that get operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "get"):
            self.manager.get(id=1)
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_filter_with_retry(self, mock_retry):
        """Test that filter operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "filter"):
            self.manager.filter(name="test")
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_create_with_retry(self, mock_retry):
        """Test that create operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "create"):
            self.manager.create(name="test")
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_bulk_create_with_retry(self, mock_retry):
        """Test that bulk_create operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "bulk_create"):
            self.manager.bulk_create([])
            mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_count_with_retry(self, mock_retry):
        """Test that count operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "count"):
            self.manager.count()
            mock_retry.assert_called()


class TestRetryableUserManager:
    """Test retryable user manager functionality."""

    def setup_method(self):
        self.manager = RetryableUserManager()
        # Mock the model
        from django.contrib.auth.models import AbstractUser

        self.manager.model = AbstractUser

    @patch("apps.management.db_mixins.database_retry")
    def test_create_user_with_retry(self, mock_retry):
        """Test that create_user operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with (
            patch.object(self.manager, "normalize_email", return_value="test@example.com"),
            patch.object(self.manager.model, "set_password"),
            patch.object(self.manager.model, "save"),
        ):

            # Mock the model instance
            mock_user = Mock()
            with patch.object(self.manager, "model", return_value=mock_user):
                user = self.manager.create_user("test@example.com", "password")
                mock_retry.assert_called()

    @patch("apps.management.db_mixins.database_retry")
    def test_create_superuser_with_retry(self, mock_retry):
        """Test that create_superuser operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager, "create_user") as mock_create_user:
            self.manager.create_superuser("admin@example.com", "password")
            mock_create_user.assert_called_once()

            # Check that superuser fields are set
            call_args = mock_create_user.call_args
            extra_fields = call_args[1]
            assert extra_fields["is_staff"] is True
            assert extra_fields["is_superuser"] is True

    def test_create_superuser_validation(self):
        """Test superuser validation."""
        with pytest.raises(ValueError, match="Superuser must have is_staff=True"):
            with patch.object(self.manager, "create_user"):
                self.manager.create_superuser("admin@example.com", "password", is_staff=False)

    @patch("apps.management.db_mixins.database_retry")
    def test_get_or_create_with_retry(self, mock_retry):
        """Test that get_or_create operations use retry logic."""
        mock_retry.return_value = lambda func: func

        with patch.object(self.manager.__class__.__bases__[0], "get_or_create"):
            self.manager.get_or_create(email="test@example.com")
            mock_retry.assert_called()


@pytest.mark.django_db
class TestMixinIntegration:
    """Test mixin integration with actual Django models and views."""

    def test_mixins_can_be_imported(self):
        """Test that all mixins can be imported."""
        from apps.management.db_mixins import (
            RetryableManager,
            RetryableModelMixin,
            RetryableUserManager,
            ServerlessViewMixin,
        )

        assert RetryableModelMixin is not None
        assert RetryableManager is not None
        assert RetryableUserManager is not None
        assert ServerlessViewMixin is not None

    def test_mixin_inheritance(self):
        """Test that mixins can be properly inherited."""
        from django.db import models

        class TestModel(RetryableModelMixin, models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test"

        model = TestModel()
        assert hasattr(model, "save")
        assert hasattr(model, "delete")
        assert hasattr(TestModel, "objects_create")

    @patch("config.database_retry.DatabaseHealthCheck")
    def test_serverless_mixin_with_actual_request(self, mock_health_check):
        """Test serverless mixin with actual request object."""
        from django.test import RequestFactory
        from django.views import View

        mock_health_check.is_healthy.return_value = True

        factory = RequestFactory()
        request = factory.get("/")

        class TestView(ServerlessViewMixin, View):
            def get(self, request):
                return "response"

        view = TestView()

        with patch.object(view.__class__.__bases__[1], "dispatch", return_value="response"):
            response = view.dispatch(request)

        mock_health_check.is_healthy.assert_called_once()

    def test_retryable_manager_integration(self):
        """Test retryable manager integration."""
        manager = RetryableManager()

        # Test that all expected methods exist
        assert hasattr(manager, "get")
        assert hasattr(manager, "filter")
        assert hasattr(manager, "create")
        assert hasattr(manager, "bulk_create")
        assert hasattr(manager, "count")
