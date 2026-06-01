"""API-key authentication and tenant resolution.

SDKs authenticate with a Bearer token (their API key). We never store the raw
key — only its SHA-256 hash, looked up via an indexed column. Tenant scoping for
every request derives from the authenticated key, which is what makes the audit
trail attributable and prevents cross-tenant access.
"""
import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.session import get_db
from src.models.tenant import Tenant

API_KEY_PREFIX = "ask_"  # AgentShield Key
_PREFIX_DISPLAY_LEN = 12


def generate_api_key() -> str:
    """Generate a new, high-entropy API key. Show this to the user exactly once."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(raw_key: str) -> str:
    """Return the hex SHA-256 of a key. Lookups and storage use only this."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def key_prefix(raw_key: str) -> str:
    """Non-secret leading chars, safe to display and log."""
    return raw_key[:_PREFIX_DISPLAY_LEN]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise _unauthorized("Authorization header must be 'Bearer <api_key>'")
    return parts[1].strip()


async def get_current_tenant(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """FastAPI dependency: resolve the authenticated tenant or raise 401."""
    token = extract_bearer_token(authorization)
    result = await db.execute(
        select(Tenant).where(Tenant.api_key_hash == hash_api_key(token))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise _unauthorized("Invalid API key")
    return tenant
