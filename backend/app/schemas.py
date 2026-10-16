"""Response shapes. These are the only things that leave the server: no author_id, no return_at."""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class MeOut(BaseModel):
    free_catches: int
    bonus_catches: int
    writes_left: int
    drifting: int


class CaughtOut(BaseModel):
    type: Literal["message"] = "message"
    id: uuid.UUID
    text: str
    catch_number: int


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
