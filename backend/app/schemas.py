"""Response shapes. These are the only things that leave the server: no author_id, no return_at."""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class MeOut(BaseModel):
    tz: str  # IANA zone; refills happen at local midnight here
    free_catches: int
    bonus_catches: int
    writes_left: int
    drifting: int


class CaughtOut(BaseModel):
    type: Literal["message"] = "message"
    id: uuid.UUID
    text: str
    catch_number: int
    from_river: bool  # a seed message, not written by a person; takes no notes


class RevealOut(BaseModel):
    type: Literal["reveal"] = "reveal"
    id: uuid.UUID
    text: str
    written_at: datetime
    seen_count: int
    notes: list[str]


class OutOfCatches(BaseModel):
    type: Literal["out_of_catches"] = "out_of_catches"


class RiverEmpty(BaseModel):
    type: Literal["river_empty"] = "river_empty"


CatchOut = Annotated[CaughtOut | RevealOut | OutOfCatches | RiverEmpty, Field(discriminator="type")]


class WriteIn(BaseModel):
    text: str
    return_option: str


class WriteOut(BaseModel):
    id: uuid.UUID


class NoteIn(BaseModel):
    note: str


class ReturnedOut(BaseModel):
    id: uuid.UUID
    text: str
    written_at: datetime
    returned_at: datetime
    seen_count: int
    notes: list[str]


class YoursOut(BaseModel):
    drifting: int
    returned: list[ReturnedOut]


class DevClockIn(BaseModel):
    """Dev only. Move the clock forward by some days, or back to real time."""

    add_days: int = Field(default=0, ge=0, le=36500)
    reset: bool = False


class DevClockOut(BaseModel):
    now: datetime
    offset_days: float
