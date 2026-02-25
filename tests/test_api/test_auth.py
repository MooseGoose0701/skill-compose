"""
Tests for authentication API endpoints.

These tests enable auth (AUTH_ENABLED=true) to test the full auth flow.

Endpoints tested:
- GET  /api/v1/auth/status
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- GET  /api/v1/auth/me
- POST /api/v1/auth/change-password
- GET  /api/v1/auth/users         (admin)
- POST /api/v1/auth/users         (admin)
- PUT  /api/v1/auth/users/{id}    (admin)
- DELETE /api/v1/auth/users/{id}  (admin)
"""

import os
import pytest
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserDB
from app.services.auth_service import hash_password, create_access_token, create_refresh_token


# ---------- Helpers ----------

def _get_secret():
    """Get the effective JWT secret from current settings."""
    from app.config import get_settings
    return get_settings().effective_jwt_secret


def _make_admin(db_session) -> UserDB:
    """Create an admin user (not yet added to session)."""
    now = datetime.utcnow()
    return UserDB(
        username="admin",
        password_hash=hash_password("admin123"),
        display_name="Admin User",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_user(db_session) -> UserDB:
    """Create a regular user (not yet added to session)."""
    now = datetime.utcnow()
    return UserDB(
        username="testuser",
        password_hash=hash_password("user123"),
        display_name="Test User",
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _admin_token(user_id: str) -> str:
    return create_access_token(user_id, "admin", "admin", _get_secret(), 24)


def _user_token(user_id: str) -> str:
    return create_access_token(user_id, "testuser", "user", _get_secret(), 24)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# All tests in this module run with AUTH_ENABLED=true
@pytest.fixture(autouse=True)
def _enable_auth():
    """Enable auth for all tests in this module by setting env var and clearing settings cache."""
    from app.config import get_settings
    from app.api.v1.auth import _LOGIN_ATTEMPTS, _LOGIN_LOCK

    old_value = os.environ.get("AUTH_ENABLED")
    os.environ["AUTH_ENABLED"] = "true"
    get_settings.cache_clear()
    # Clear rate limiter state between tests
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.clear()
    yield
    if old_value is not None:
        os.environ["AUTH_ENABLED"] = old_value
    else:
        os.environ.pop("AUTH_ENABLED", None)
    get_settings.cache_clear()
    # Clear rate limiter state after test
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.clear()


class TestAuthStatus:
    """Tests for GET /api/v1/auth/status."""

    async def test_status_returns_auth_enabled(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["auth_enabled"] is True
        assert "has_users" in data

    async def test_status_no_users_initially(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/status")
        data = response.json()
        assert data["has_users"] is False

    async def test_status_has_users_after_create(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        response = await client.get("/api/v1/auth/status")
        data = response.json()
        assert data["has_users"] is True


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        assert "must_change_password" in data

    async def test_login_wrong_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_wrong_username(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "admin123"},
        )
        assert response.status_code == 401

    async def test_login_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        admin.is_active = False
        db_session.add(admin)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 401


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        refresh = create_refresh_token(admin.id, _get_secret(), 7)
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        # Use an access token instead of refresh token
        access = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access},
        )
        assert response.status_code == 401


class TestGetMe:
    """Tests for GET /api/v1/auth/me."""

    async def test_me_with_valid_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.get(
            "/api/v1/auth/me", headers=_auth_header(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    async def test_me_without_token(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_me_with_expired_token(self, client: AsyncClient):
        # Create a token with 0 hours expiry (already expired)
        token = create_access_token("fake-id", "test", "user", _get_secret(), 0)
        response = await client.get(
            "/api/v1/auth/me", headers=_auth_header(token)
        )
        assert response.status_code == 401


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password."""

    async def test_change_password_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "admin123", "new_password": "newpass456"},
            headers=_auth_header(token),
        )
        assert response.status_code == 200

    async def test_change_password_wrong_current(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrongpass", "new_password": "newpass456"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400


class TestAdminUserCRUD:
    """Tests for admin user management endpoints."""

    async def test_list_users(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.get(
            "/api/v1/auth/users", headers=_auth_header(token)
        )
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 1
        assert any(u["username"] == "admin" for u in users)

    async def test_create_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={
                "username": "newuser",
                "password": "password123",
                "display_name": "New User",
                "role": "user",
            },
            headers=_auth_header(token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "user"

    async def test_create_duplicate_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        # Create user first
        await client.post(
            "/api/v1/auth/users",
            json={"username": "dupuser", "password": "password123", "role": "user"},
            headers=_auth_header(token),
        )
        # Try creating same username
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "dupuser", "password": "password123", "role": "user"},
            headers=_auth_header(token),
        )
        assert response.status_code == 409

    async def test_create_user_invalid_role(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "baduser", "password": "password123", "role": "superadmin"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400

    async def test_update_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        user = _make_user(db_session)
        db_session.add(admin)
        db_session.add(user)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.put(
            f"/api/v1/auth/users/{user.id}",
            json={"display_name": "Updated Name", "role": "admin"},
            headers=_auth_header(token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["role"] == "admin"

    async def test_update_user_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.put(
            "/api/v1/auth/users/nonexistent-id",
            json={"display_name": "Test"},
            headers=_auth_header(token),
        )
        assert response.status_code == 404

    async def test_delete_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        user = _make_user(db_session)
        db_session.add(admin)
        db_session.add(user)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.delete(
            f"/api/v1/auth/users/{user.id}",
            headers=_auth_header(token),
        )
        assert response.status_code == 200

    async def test_delete_self_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.delete(
            f"/api/v1/auth/users/{admin.id}",
            headers=_auth_header(token),
        )
        assert response.status_code == 400

    async def test_demote_self_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.put(
            f"/api/v1/auth/users/{admin.id}",
            json={"role": "user"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400

    async def test_deactivate_self_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.put(
            f"/api/v1/auth/users/{admin.id}",
            json={"is_active": False},
            headers=_auth_header(token),
        )
        assert response.status_code == 400


class TestNonAdminForbidden:
    """Tests that non-admin users cannot access admin endpoints."""

    async def test_non_admin_list_users(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = _make_user(db_session)
        db_session.add(user)
        await db_session.flush()

        token = _user_token(user.id)
        response = await client.get(
            "/api/v1/auth/users", headers=_auth_header(token)
        )
        assert response.status_code == 403

    async def test_non_admin_create_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = _make_user(db_session)
        db_session.add(user)
        await db_session.flush()

        token = _user_token(user.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "evil", "password": "password123", "role": "admin"},
            headers=_auth_header(token),
        )
        assert response.status_code == 403

    async def test_non_admin_delete_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = _make_user(db_session)
        db_session.add(user)
        await db_session.flush()

        token = _user_token(user.id)
        response = await client.delete(
            "/api/v1/auth/users/some-id",
            headers=_auth_header(token),
        )
        assert response.status_code == 403


class TestProtectedEndpoints:
    """Tests that protected endpoints return 401 without token."""

    async def test_me_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_change_password_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "x", "new_password": "y"},
        )
        assert response.status_code == 401

    async def test_users_list_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/users")
        assert response.status_code == 401


class TestPasswordValidation:
    """Tests for password complexity validation."""

    async def test_create_user_short_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "shortpw", "password": "short", "role": "user"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

    async def test_change_password_short_new(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "admin123", "new_password": "short"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

    async def test_update_user_short_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        user = _make_user(db_session)
        db_session.add(admin)
        db_session.add(user)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.put(
            f"/api/v1/auth/users/{user.id}",
            json={"password": "short"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]


class TestMustChangePassword:
    """Tests for forced password change on default admin."""

    async def test_login_returns_must_change_flag(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Default admin should have must_change_password=True."""
        now = datetime.utcnow()
        admin = UserDB(
            username="defaultadmin",
            password_hash=hash_password("admin123"),
            display_name="Default Admin",
            role="admin",
            is_active=True,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(admin)
        await db_session.flush()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "defaultadmin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["must_change_password"] is True

    async def test_change_password_clears_flag(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Changing password should clear the must_change_password flag."""
        now = datetime.utcnow()
        admin = UserDB(
            username="flagadmin",
            password_hash=hash_password("admin123"),
            display_name="Flag Admin",
            role="admin",
            is_active=True,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "admin123", "new_password": "newpassword123"},
            headers=_auth_header(token),
        )
        assert response.status_code == 200

        # Login again to verify flag is cleared
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "flagadmin", "password": "newpassword123"},
        )
        assert response.status_code == 200
        assert response.json()["must_change_password"] is False


class TestRefreshTokenInvalidation:
    """Tests for refresh token invalidation after password change."""

    async def test_refresh_token_invalid_after_password_change(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Refresh token issued before password change should be rejected."""
        import asyncio

        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        # Issue a refresh token
        refresh = create_refresh_token(admin.id, _get_secret(), 7)

        # Wait so password_changed_at is strictly after the token's iat (integer seconds)
        await asyncio.sleep(1.1)

        # Change password (this sets password_changed_at)
        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "admin123", "new_password": "newpassword123"},
            headers=_auth_header(token),
        )
        assert response.status_code == 200

        # Old refresh token should now be rejected
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert response.status_code == 401
        assert "password change" in response.json()["detail"].lower()

    async def test_refresh_token_valid_after_reissue(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """New refresh token issued after password change should work."""
        import asyncio

        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        # Change password
        token = _admin_token(admin.id)
        await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "admin123", "new_password": "newpassword123"},
            headers=_auth_header(token),
        )

        # Wait so new token's iat is strictly after password_changed_at
        await asyncio.sleep(1.1)

        # Login with new password to get new tokens
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "newpassword123"},
        )
        assert response.status_code == 200
        new_refresh = response.json()["refresh_token"]

        # New refresh token should work
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_refresh},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestUsernameValidation:
    """Tests for username validation."""

    async def test_login_empty_username(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": "password123"},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    async def test_login_invalid_chars_username(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "user name!", "password": "password123"},
        )
        assert response.status_code == 400

    async def test_create_user_empty_username(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "  ", "password": "password123", "role": "user"},
            headers=_auth_header(token),
        )
        assert response.status_code == 400

    async def test_create_user_valid_username_chars(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Usernames with letters, numbers, underscores, dots, hyphens should work."""
        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        token = _admin_token(admin.id)
        response = await client.post(
            "/api/v1/auth/users",
            json={"username": "test_user.name-123", "password": "password123", "role": "user"},
            headers=_auth_header(token),
        )
        assert response.status_code == 201


class TestRateLimiting:
    """Tests for login rate limiting."""

    async def test_rate_limit_on_repeated_failures(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """After 5 failed attempts, should return 429."""
        from app.api.v1.auth import _LOGIN_ATTEMPTS, _LOGIN_LOCK

        # Clear any existing rate limit state
        with _LOGIN_LOCK:
            _LOGIN_ATTEMPTS.clear()

        admin = _make_admin(db_session)
        db_session.add(admin)
        await db_session.flush()

        # Make 5 failed attempts
        for _ in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrongpassword"},
            )

        # 6th attempt should be rate limited
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 429

        # Clean up
        with _LOGIN_LOCK:
            _LOGIN_ATTEMPTS.clear()
