"""River rules: writing, catching, notes, returns. Everything that touches return_at lives here."""
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import clock, content_filter
from .config import get_settings
from .models import Catch, Message, Report, User


class RiverError(Exception):
    """A rule was broken. `status` is the HTTP status, `reason` is shown to the user."""

    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


# ---- users -----------------------------------------------------------------

def ensure_user(db: Session, user_id: uuid.UUID, tz: str | None = None) -> None:
    """Creates the user on first sight. `tz` (the browser's IANA zone) is only used then."""
    s = get_settings()
    tz = tz or s.default_tz
    now = clock.now()
    today = now.astimezone(ZoneInfo(tz)).date()
    db.execute(
        insert(User)
        .values(
            id=user_id,
            created_at=now,
            tz=tz,
            free_catches=s.free_catches_per_day,
            free_refilled_on=today,
            writes_counted_on=today,
        )
        .on_conflict_do_nothing(index_elements=[User.id])
    )
    db.commit()


def _lock_user(db: Session, user_id: uuid.UUID) -> User:
    """Row lock serialises everything that spends catches or writes for one user."""
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one()
    _refresh_daily(user)
    return user


def _local_today(user: User) -> date:
    return clock.now().astimezone(ZoneInfo(user.tz)).date()


def _refresh_daily(user: User) -> None:
    s = get_settings()
    today = _local_today(user)
    # "!=" rather than "<": the dev clock can move back, and a stored date ahead of today
    # would otherwise block refills until real time caught up.
    if user.free_refilled_on != today:
        user.free_catches = s.free_catches_per_day
        user.free_refilled_on = today
    if user.writes_counted_on != today:
        user.writes_today = 0
        user.writes_counted_on = today


def _drifting_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.author_id == user_id, Message.returned_at.is_(None), Message.status != "deleted")
    )


@dataclass
class Me:
    tz: str
    free_catches: int
    bonus_catches: int
    writes_left: int
    drifting: int


def me(db: Session, user_id: uuid.UUID) -> Me:
    user = _lock_user(db, user_id)
    result = Me(
        tz=user.tz,
        free_catches=user.free_catches,
        bonus_catches=user.bonus_catches,
        writes_left=max(0, get_settings().writes_per_day - user.writes_today),
        drifting=_drifting_count(db, user_id),
    )
    db.commit()
    return result


# ---- writing ---------------------------------------------------------------

def _validate_message(text: str) -> None:
    s = get_settings()
    if len(text) < s.message_min:
        raise RiverError(422, "Write at least 20 characters so it means something to whoever catches it.")
    if len(text) > s.message_max:
        raise RiverError(422, "Keep it under 500 characters.")
    if reason := content_filter.check(text):
        raise RiverError(422, reason)


def write(db: Session, user_id: uuid.UUID, text: str, return_option: str) -> uuid.UUID:
    s = get_settings()
    text = text.strip()
    if return_option not in s.return_ranges:
        raise RiverError(422, "Pick when it should come back to you.")

    user = _lock_user(db, user_id)
    try:
        if user.writes_today >= s.writes_per_day:
            raise RiverError(422, "You’ve sent today’s messages. You can write more tomorrow.")
        _validate_message(text)
    except RiverError:
        db.rollback()
        raise

    # The cooling period wins over a range configured below it.
    lo, hi = s.return_ranges[return_option]
    lo = max(lo, s.cooling_days)
    hi = max(hi, lo)
    now = clock.now()
    return_at = now + timedelta(seconds=random.randint(lo * 86400, hi * 86400))

    msg = Message(author_id=user_id, text=text, return_option=return_option, created_at=now, return_at=return_at)
    db.add(msg)
    user.writes_today += 1
    db.commit()
    return msg.id


# ---- catching --------------------------------------------------------------

@dataclass
class Caught:
    id: uuid.UUID
    text: str
    catch_number: int
    from_river: bool  # a seed message: labelled in the app, takes no notes


@dataclass
class Reveal:
    id: uuid.UUID
    text: str
    written_at: datetime
    seen_count: int
    notes: list[str]


def _seen_count(db: Session, message_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Catch).where(Catch.message_id == message_id))


def _notes(db: Session, message_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(Catch.note)
            .where(Catch.message_id == message_id, Catch.note.is_not(None))
            .order_by(Catch.noted_at)
        )
    )


def _pick_random(db: Session, user_id: uuid.UUID) -> Message | None:
    """A random unseen message from someone else. Seeds only once every real message has been seen."""
    already_seen = exists().where(Catch.user_id == user_id, Catch.message_id == Message.id)
    for source in ("user", "seed"):
        base = select(Message).where(
            Message.source == source,
            Message.status == "active",
            Message.author_id != user_id,
            ~already_seen,
        )
        r = random.random()
        msg = db.scalars(base.where(Message.rand_key >= r).order_by(Message.rand_key).limit(1)).first()
        if msg is None:  # wrap around from 0
            msg = db.scalars(base.where(Message.rand_key < r).order_by(Message.rand_key).limit(1)).first()
        if msg is not None:
            return msg
    return None


def catch(db: Session, user_id: uuid.UUID) -> Caught | Reveal | str:
    """One catch, in one transaction. Returns Caught, Reveal, 'out_of_catches' or 'river_empty'."""
    user = _lock_user(db, user_id)

    # 1. A due message of your own comes back first, free, even with 0 catches left.
    due = db.scalars(
        select(Message)
        .where(
            Message.author_id == user_id,
            Message.returned_at.is_(None),
            Message.return_at <= clock.now(),
            Message.status != "deleted",
        )
        .order_by(Message.return_at)
        .limit(1)
    ).first()
    if due is not None:
        reveal = Reveal(
            id=due.id,
            text=due.text,
            written_at=due.created_at,
            seen_count=_seen_count(db, due.id),
            notes=_notes(db, due.id),
        )
        db.commit()
        return reveal

    # 2. Out of catches.
    if user.free_catches + user.bonus_catches <= 0:
        db.commit()
        return "out_of_catches"

    # 3. Random unseen message from someone else. An empty river costs nothing.
    msg = _pick_random(db, user_id)
    if msg is None:
        db.commit()
        return "river_empty"

    # 4. Record and spend.
    db.add(Catch(user_id=user_id, message_id=msg.id, caught_at=clock.now()))
    if user.free_catches > 0:
        user.free_catches -= 1
    else:
        user.bonus_catches -= 1
    db.flush()
    caught = Caught(
        id=msg.id, text=msg.text, catch_number=_seen_count(db, msg.id), from_river=msg.source == "seed"
    )
    db.commit()
    return caught


def keep(db: Session, user_id: uuid.UUID, message_id: uuid.UUID) -> None:
    now = clock.now()
    res = db.execute(
        update(Message)
        .where(
            Message.id == message_id,
            Message.author_id == user_id,
            Message.returned_at.is_(None),
            Message.return_at <= now,
        )
        .values(returned_at=now)
    )
    db.commit()
    if res.rowcount == 0:
        raise RiverError(404, "Nothing to keep here.")


# ---- notes and reports -----------------------------------------------------

def add_note(db: Session, user_id: uuid.UUID, message_id: uuid.UUID, note: str) -> None:
    s = get_settings()
    note = note.strip()
    if len(note) < s.note_min:
        raise RiverError(422, "Write something first.")
    if len(note) > s.note_max:
        raise RiverError(422, "Keep notes under 140 characters.")
    if reason := content_filter.check(note):
        raise RiverError(422, reason)

    is_seed = exists().where(Message.id == message_id, Message.source == "seed")
    res = db.execute(
        update(Catch)
        .where(Catch.user_id == user_id, Catch.message_id == message_id, Catch.note.is_(None), ~is_seed)
        .values(note=note, noted_at=clock.now())
    )
    db.commit()
    if res.rowcount == 0:
        if db.scalar(select(is_seed)):
            raise RiverError(422, "Messages from the river don’t take notes.")
        if _has_caught(db, user_id, message_id):
            raise RiverError(409, "You’ve already left a note on this one.")
        raise RiverError(404, "You can only leave notes on messages you caught.")


def _has_caught(db: Session, user_id: uuid.UUID, message_id: uuid.UUID) -> bool:
    return db.scalar(select(exists().where(Catch.user_id == user_id, Catch.message_id == message_id)))


def report_message(db: Session, user_id: uuid.UUID, message_id: uuid.UUID) -> None:
    """The reporter has already caught it, so the no-repeats rule hides it from them."""
    if not _has_caught(db, user_id, message_id):
        raise RiverError(404, "You can only report messages you caught.")
    # RETURNING, not rowcount: ORM-executed inserts report rowcount -1, which would count repeats.
    inserted = db.execute(
        insert(Report)
        .values(reporter_id=user_id, target_type="message", target_id=str(message_id), created_at=clock.now())
        .on_conflict_do_nothing()
        .returning(Report.reporter_id)
    ).first()
    if inserted is not None:
        db.execute(
            update(Message).where(Message.id == message_id).values(report_count=Message.report_count + 1)
        )
        db.execute(
            update(Message)
            .where(
                Message.id == message_id,
                Message.status == "active",
                Message.report_count >= get_settings().report_hide_threshold,
            )
            .values(status="hidden")
        )
    db.commit()


# ---- yours -----------------------------------------------------------------

@dataclass
class Returned:
    id: uuid.UUID
    text: str
    written_at: datetime
    returned_at: datetime
    seen_count: int
    notes: list[str]


def yours(db: Session, user_id: uuid.UUID) -> tuple[int, list[Returned]]:
    msgs = db.scalars(
        select(Message)
        .where(Message.author_id == user_id, Message.returned_at.is_not(None), Message.status != "deleted")
        .order_by(Message.returned_at.desc())
    ).all()
    ids = [m.id for m in msgs]
    counts: dict[uuid.UUID, int] = {}
    notes: dict[uuid.UUID, list[str]] = {i: [] for i in ids}
    if ids:
        counts = dict(
            db.execute(
                select(Catch.message_id, func.count())
                .where(Catch.message_id.in_(ids))
                .group_by(Catch.message_id)
            ).all()
        )
        for mid, note in db.execute(
            select(Catch.message_id, Catch.note)
            .where(Catch.message_id.in_(ids), Catch.note.is_not(None))
            .order_by(Catch.noted_at)
        ):
            notes[mid].append(note)
    returned = [
        Returned(
            id=m.id,
            text=m.text,
            written_at=m.created_at,
            returned_at=m.returned_at,
            seen_count=counts.get(m.id, 0),
            notes=notes[m.id],
        )
        for m in msgs
    ]
    drifting = _drifting_count(db, user_id)
    db.commit()
    return drifting, returned


# ---- dev only --------------------------------------------------------------

def dev_force_due(db: Session, user_id: uuid.UUID) -> int:
    res = db.execute(
        update(Message)
        .where(Message.author_id == user_id, Message.returned_at.is_(None))
        .values(return_at=clock.now())
    )
    db.commit()
    return res.rowcount


def dev_refill(db: Session, user_id: uuid.UUID) -> None:
    s = get_settings()
    db.execute(
        update(User).where(User.id == user_id).values(free_catches=s.free_catches_per_day, writes_today=0)
    )
    db.commit()
