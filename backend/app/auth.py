"""Who is calling. Supabase Auth access tokens (Bearer) in all modes; the fake X-Dev-User header only in dev mode."""
import uuid
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import river
from .config import get_settings
from .db import get_db

_DEV_NAMESPACE = uuid.UUID("5d0f3a4e-6c1b-4f4e-9a57-7a0d2b9c1e11")
_ASYMMETRIC = ("ES256", "RS256", "EdDSA")


def dev_user_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_DEV_NAMESPACE, name.strip().lower())


class AuthError(Exception):
    pass


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    # Caches the key set; refetches when a token names a key id it hasn't seen (key rotation).
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


def _signing_key(token: str):
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError as e:
        raise AuthError("malformed token") from e
    if alg == "HS256":
        if not s.supabase_jwt_secret:
            raise AuthError("HS256 tokens are not accepted: no JWT secret configured")
        return s.supabase_jwt_secret, alg
    if alg in _ASYMMETRIC:
        if not s.supabase_url:
            raise AuthError("no Supabase URL configured")
        try:
            key = _jwks_client(s.supabase_issuer + "/.well-known/jwks.json").get_signing_key_from_jwt(token)
        except jwt.PyJWTError as e:
            raise AuthError(f"no signing key: {e}") from e
        return key.key, alg
    raise AuthError(f"unsupported alg {alg!r}")


def verify_token(token: str) -> uuid.UUID:
    """Checks signature, expiry, audience (and issuer when a Supabase URL is set). Returns the user id."""
    s = get_settings()
    key, alg = _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=s.supabase_jwt_audience,
            issuer=s.supabase_issuer if s.supabase_url else None,
            options={"require": ["exp", "sub", "aud"]},
            leeway=30,
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as e:
        raise AuthError(str(e)) from e


def _browser_tz(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return value


def current_user_id(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user: Annotated[str | None, Header()] = None,
    x_timezone: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            user_id = verify_token(token.strip())
        except AuthError:
            raise HTTPException(401, "Your sign-in has expired. Sign in again.", {"WWW-Authenticate": "Bearer"})
    elif get_settings().dev_mode and x_dev_user and x_dev_user.strip():
        user_id = dev_user_id(x_dev_user)
    else:
        raise HTTPException(401, "Sign in to continue.", {"WWW-Authenticate": "Bearer"})
    # The browser's time zone is only used the first time we see this user.
    river.ensure_user(db, user_id, _browser_tz(x_timezone))
    return user_id


UserId = Annotated[uuid.UUID, Depends(current_user_id)]
