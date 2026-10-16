"""Phase 1: fake dev auth. Phase 2 swaps in Supabase JWT verification behind the same dependency."""
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import river
from .config import get_settings
from .db import get_db

_DEV_NAMESPACE = uuid.UUID("5d0f3a4e-6c1b-4f4e-9a57-7a0d2b9c1e11")


def dev_user_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_DEV_NAMESPACE, name.strip().lower())


def current_user_id(
    db: Annotated[Session, Depends(get_db)],
    x_dev_user: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    if not get_settings().dev_mode:
        raise HTTPException(401, "Sign in to continue.")
    if not x_dev_user or not x_dev_user.strip():
        raise HTTPException(401, "Missing X-Dev-User header.")
    user_id = dev_user_id(x_dev_user)
    river.ensure_user(db, user_id)
    return user_id


UserId = Annotated[uuid.UUID, Depends(current_user_id)]
