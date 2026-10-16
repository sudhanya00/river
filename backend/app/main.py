import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import river
from .auth import UserId
from .config import get_settings
from .db import get_db
from .schemas import (
    CatchOut,
    CaughtOut,
    MeOut,
    NoteIn,
    OutOfCatches,
    RevealOut,
    RiverEmpty,
    WriteIn,
    WriteOut,
    YoursOut,
)

Db = Annotated[Session, Depends(get_db)]

app = FastAPI(title="River")


@app.exception_handler(river.RiverError)
def _river_error(_: Request, exc: river.RiverError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.reason})


api = APIRouter(prefix="/api")


@api.get("/me", response_model=MeOut)
def get_me(db: Db, user_id: UserId):
    return asdict(river.me(db, user_id))


@api.post("/catch", response_model=CatchOut)
def post_catch(db: Db, user_id: UserId):
    result = river.catch(db, user_id)
    if result == "out_of_catches":
        return OutOfCatches()
    if result == "river_empty":
        return RiverEmpty()
    if isinstance(result, river.Reveal):
        return RevealOut(**asdict(result))
    return CaughtOut(**asdict(result))


@api.post("/messages", response_model=WriteOut, status_code=201)
def post_message(body: WriteIn, db: Db, user_id: UserId):
    return WriteOut(id=river.write(db, user_id, body.text, body.return_option))


@api.post("/messages/{message_id}/keep", status_code=204)
def post_keep(message_id: uuid.UUID, db: Db, user_id: UserId):
    river.keep(db, user_id, message_id)


@api.post("/messages/{message_id}/note", status_code=204)
def post_note(message_id: uuid.UUID, body: NoteIn, db: Db, user_id: UserId):
    river.add_note(db, user_id, message_id, body.note)


@api.post("/messages/{message_id}/report", status_code=204)
def post_report(message_id: uuid.UUID, db: Db, user_id: UserId):
    river.report_message(db, user_id, message_id)


@api.get("/yours", response_model=YoursOut)
def get_yours(db: Db, user_id: UserId):
    drifting, returned = river.yours(db, user_id)
    return YoursOut(drifting=drifting, returned=[asdict(r) for r in returned])


app.include_router(api)

if get_settings().dev_mode:
    dev = APIRouter(prefix="/api/dev", tags=["dev"])

    @dev.post("/force-due")
    def post_force_due(db: Db, user_id: UserId):
        return {"made_due": river.dev_force_due(db, user_id)}

    @dev.post("/refill", status_code=204)
    def post_refill(db: Db, user_id: UserId):
        river.dev_refill(db, user_id)

    app.include_router(dev)
