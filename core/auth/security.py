"""
Web Security & Remote Access Authentication Module
Provides JWT-based Session Management, Role-Based Access Control,
and Secure Remote Login for Anywhere Dashboard Access.
"""

import hashlib
import hmac
import os
import time
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.config.settings import settings


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
    user: dict[str, Any]


class UserProfile(BaseModel):
    username: str
    role: str = "admin"
    permissions: list[str] = ["view_dashboard", "manage_agents", "emergency_kill_switch", "execute_trades"]


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    ).hex()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash or direct match."""
    if "$" not in stored_hash:
        # Fallback to direct comparison if plain string in config
        return hmac.compare_digest(password, stored_hash)
    salt, original_hash = stored_hash.split("$", 1)
    new_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    ).hex()
    return hmac.compare_digest(new_hash, original_hash)


def create_access_token(user_data: dict[str, Any], expires_hours: int | None = None) -> str:
    """Create a cryptographically signed JWT token."""
    exp_hours = expires_hours or settings.JWT_EXPIRY_HOURS
    payload = {
        "sub": user_data.get("username", "admin"),
        "role": user_data.get("role", "admin"),
        "permissions": user_data.get("permissions", []),
        "iat": int(time.time()),
        "exp": int(time.time()) + (exp_hours * 3600),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except Exception:
        return None


security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security_scheme)] = None,
) -> dict[str, Any]:
    """FastAPI dependency to enforce JWT Authentication on protected endpoints."""
    if settings.AUTH_REQUIRED:
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token missing or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = decode_access_token(credentials.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    # In local testing mode without AUTH_REQUIRED, accept valid token if supplied
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload:
            return payload

    return {"sub": "system", "role": "admin", "permissions": ["all"]}


def require_admin(current_user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    """FastAPI dependency ensuring caller possesses admin / superadmin privileges."""
    role = current_user.get("role", "")
    if role not in ["admin", "SUPER_ADMIN", "SYSTEM"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative clearance required for this operation",
        )
    return current_user


def authenticate_user(username: str, password: str) -> UserProfile | None:
    """Validate username and password against configured administrative credentials."""
    admin_user = settings.ADMIN_USERNAME
    admin_pass = settings.ADMIN_PASSWORD

    if not admin_pass or not password:
        return None

    if username == admin_user and (password == admin_pass or verify_password(password, admin_pass)):
        return UserProfile(
            username=username,
            role="SUPER_ADMIN",
            permissions=[
                "view_dashboard",
                "trigger_scans",
                "manage_agents",
                "emergency_kill_switch",
                "modify_risk_limits",
                "view_treasury",
                "execute_trades",
            ],
        )
    return None

