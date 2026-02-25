"""Authentication API endpoints."""

import re
import time
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.models import UserDB
from app.api.deps import get_current_user, get_current_admin
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
    get_user_by_username,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------- Rate limiting ----------

_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_LOCK = threading.Lock()
_MAX_ATTEMPTS = 5  # max attempts per window
_WINDOW_SECONDS = 300  # 5 minute window


_MAX_TRACKED_IPS = 10000  # max IPs to track before full cleanup

def _check_rate_limit(key: str) -> bool:
    """Return True if the request is allowed, False if rate-limited.

    Only checks the counter — does NOT record an attempt.
    Call _record_failed_attempt() after a failed login.
    """
    now = time.time()
    with _LOGIN_LOCK:
        # Purge all expired entries when dict grows too large
        if len(_LOGIN_ATTEMPTS) > _MAX_TRACKED_IPS:
            expired_keys = [
                k for k, v in _LOGIN_ATTEMPTS.items()
                if not v or now - v[-1] >= _WINDOW_SECONDS
            ]
            for k in expired_keys:
                del _LOGIN_ATTEMPTS[k]
        attempts = _LOGIN_ATTEMPTS[key]
        # Remove expired attempts for this key
        _LOGIN_ATTEMPTS[key] = [t for t in attempts if now - t < _WINDOW_SECONDS]
        if len(_LOGIN_ATTEMPTS[key]) >= _MAX_ATTEMPTS:
            return False
        return True


def _record_failed_attempt(key: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS[key].append(now)


_MIN_PASSWORD_LENGTH = 8

def _validate_password(password: str) -> None:
    """Validate password meets minimum requirements."""
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {_MIN_PASSWORD_LENGTH} characters",
        )


_USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.\-]+$')
_MAX_USERNAME_LENGTH = 64

def _validate_username(username: str) -> None:
    """Validate username meets requirements."""
    username = username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )
    if len(username) > _MAX_USERNAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username must be at most {_MAX_USERNAME_LENGTH} characters",
        )
    if not _USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain letters, numbers, underscores, dots, and hyphens",
        )


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (for DB compatibility).

    Replaces deprecated datetime.utcnow() while remaining compatible
    with TIMESTAMP WITHOUT TIME ZONE columns.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------- Schemas ----------

class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    has_users: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserInfo
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    role: str = "user"


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # Reset password


# ---------- Public endpoints ----------

@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(db: AsyncSession = Depends(get_db)):
    """Check if auth is enabled and if any users exist."""
    settings = get_settings()
    result = await db.execute(select(func.count(UserDB.id)))
    count = result.scalar() or 0
    return AuthStatusResponse(
        auth_enabled=settings.auth_enabled,
        has_users=count > 0,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT tokens."""
    # Rate limiting by IP — check BEFORE username validation to prevent
    # attackers from probing username format rules without being rate-limited
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    _validate_username(body.username)

    settings = get_settings()

    user = await authenticate_user(db, body.username, body.password)
    if not user:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    access_token = create_access_token(
        user.id, user.username, user.role,
        settings.effective_jwt_secret,
        settings.jwt_access_token_expire_hours,
    )
    refresh_token = create_refresh_token(
        user.id,
        settings.effective_jwt_secret,
        settings.jwt_refresh_token_expire_days,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ),
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh an access token using a refresh token."""
    settings = get_settings()

    try:
        payload = decode_token(body.refresh_token, settings.effective_jwt_secret)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Reject refresh tokens issued before the last password change
    if user.password_changed_at and payload.get("iat"):
        # Truncate to integer seconds — JWT iat is integer, so compare fairly
        changed_ts = int(user.password_changed_at.replace(tzinfo=timezone.utc).timestamp())
        if payload["iat"] < changed_ts:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalidated by password change",
            )

    access_token = create_access_token(
        user.id, user.username, user.role,
        settings.effective_jwt_secret,
        settings.jwt_access_token_expire_hours,
    )

    return RefreshResponse(access_token=access_token)


# ---------- Protected endpoints ----------

@router.get("/me", response_model=UserInfo)
async def get_me(user: UserDB = Depends(get_current_user)):
    """Get current user info."""
    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    _validate_password(body.new_password)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = _utcnow()
    user.updated_at = _utcnow()
    db.add(user)
    await db.flush()
    return {"message": "Password changed successfully"}


# ---------- Admin endpoints ----------

@router.get("/users", response_model=list[UserInfo])
async def list_users(
    admin: UserDB = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    result = await db.execute(select(UserDB).order_by(UserDB.created_at))
    users = result.scalars().all()
    return [
        UserInfo(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("/users", response_model=UserInfo, status_code=201)
async def create_user(
    body: CreateUserRequest,
    admin: UserDB = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only)."""
    _validate_username(body.username)
    _validate_password(body.password)

    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )

    if body.role not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'user'",
        )

    now = _utcnow()
    new_user = UserDB(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(new_user)
    await db.flush()

    return UserInfo(
        id=new_user.id,
        username=new_user.username,
        display_name=new_user.display_name,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=now.isoformat(),
    )


@router.put("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: UserDB = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user (admin only)."""
    target = await get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Self-protection: cannot demote/deactivate yourself
    if target.id == admin.id:
        if body.role is not None and body.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote yourself",
            )
        if body.is_active is not None and not body.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )

    if body.display_name is not None:
        target.display_name = body.display_name
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'admin' or 'user'",
            )
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.password is not None:
        _validate_password(body.password)
        target.password_hash = hash_password(body.password)
        target.password_changed_at = _utcnow()

    target.updated_at = _utcnow()
    db.add(target)
    await db.flush()

    return UserInfo(
        id=target.id,
        username=target.username,
        display_name=target.display_name,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: UserDB = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (admin only, cannot delete self)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    target = await get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(target)
    await db.flush()
    return {"message": f"User '{target.username}' deleted"}
