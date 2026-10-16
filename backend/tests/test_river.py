import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, update

from app import clock, river
from app.auth import dev_user_id
from app.config import get_settings
from app.db import SessionLocal
from app.models import Message, User

from .conftest import wipe

pytestmark = pytest.mark.usefixtures("clean")

TEXT = "A message long enough to pass the twenty character minimum."


def seed(db, author: str, n: int, return_in_days: int = 400) -> list[uuid.UUID]:
    """Insert messages directly, bypassing the daily write limit."""
    author_id = dev_user_id(author)
    river.ensure_user(db, author_id)
    msgs = [
        Message(
            author_id=author_id,
            text=f"{TEXT} #{author}-{i}",
            return_option="any",
            return_at=clock.now() + timedelta(days=return_in_days),
        )
        for i in range(n)
    ]
    db.add_all(msgs)
    db.commit()
    return [m.id for m in msgs]


def set_catches(db, name: str, free: int, bonus: int = 0) -> None:
    db.execute(update(User).where(User.id == dev_user_id(name)).values(free_catches=free, bonus_catches=bonus))
    db.commit()


# ---- the phase 1 "done" scenario ----------------------------------------------

def test_two_users_write_catch_and_get_a_reveal(user, db):
    a, b = user("asha"), user("bilal")
    a_ids = {a.write(TEXT + " from asha one"), a.write(TEXT + " from asha two")}
    b_ids = {b.write(TEXT + " from bilal")}

    caught_by_b = {b.catch()["id"], b.catch()["id"]}
    assert caught_by_b == a_ids
    assert b.catch() == {"type": "river_empty"}

    first = a.catch()
    assert first["type"] == "message" and first["id"] in b_ids
    assert first["catch_number"] == 1
    assert a.catch() == {"type": "river_empty"}

    # Bilal leaves a note on one of Asha's messages.
    noted = sorted(caught_by_b)[0]
    assert b.post(f"/messages/{noted}/note", {"note": "This found me on the right day."}).status_code == 204

    # Force Asha's messages due: the next catches are reveals, oldest return first.
    assert a.post("/dev/force-due").json() == {"made_due": 2}
    before = a.me()
    reveal = a.catch()
    assert reveal["type"] == "reveal" and reveal["id"] in a_ids
    assert reveal["seen_count"] == 1
    assert a.me()["free_catches"] == before["free_catches"]  # reveal is free

    # Reveals repeat until kept; then the next one comes.
    assert a.catch()["id"] == reveal["id"]
    assert a.post(f"/messages/{reveal['id']}/keep").status_code == 204
    second = a.catch()
    assert second["type"] == "reveal" and second["id"] != reveal["id"]
    assert a.post(f"/messages/{second['id']}/keep").status_code == 204

    yours = a.get("/yours").json()
    assert yours["drifting"] == 0
    by_id = {m["id"]: m for m in yours["returned"]}
    assert by_id[noted]["notes"] == ["This found me on the right day."]
    assert all(m["seen_count"] == 1 for m in yours["returned"])


# ---- no repeats, never your own -----------------------------------------------

@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    sizes=st.lists(st.integers(min_value=0, max_value=6), min_size=2, max_size=4),
    script=st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=40),
)
def test_no_user_sees_a_message_twice_or_their_own(client, sizes, script):
    wipe()
    from .conftest import Dev

    names = [f"u{i}" for i in range(len(sizes))]
    with SessionLocal() as db:
        owned = {n: set(seed(db, n, k)) for n, k in zip(names, sizes)}
        for n in names:
            set_catches(db, n, free=1000)
    users = {n: Dev(client, n) for n in names}

    seen = {n: [] for n in names}
    for step in script:
        name = names[step % len(names)]
        r = users[name].catch()
        if r["type"] == "message":
            seen[name].append(uuid.UUID(r["id"]))
        else:
            assert r["type"] == "river_empty"
            others = set().union(*(owned[m] for m in names if m != name))
            assert set(seen[name]) == others

    for n in names:
        assert len(seen[n]) == len(set(seen[n])), "repeat catch"
        assert not set(seen[n]) & owned[n], "caught own message"


# ---- returns ------------------------------------------------------------------

def test_message_never_returns_early_and_returns_on_first_catch_after(user, db, monkeypatch):
    a = user("asha")
    mid = uuid.UUID(a.write(TEXT))
    return_at = db.scalar(select(Message.return_at).where(Message.id == mid))
    seed(db, "other", 3)

    monkeypatch.setattr(clock, "now", lambda: return_at - timedelta(seconds=1))
    r = a.catch()
    assert r["type"] == "message"  # not the reveal yet

    monkeypatch.setattr(clock, "now", lambda: return_at)
    r = a.catch()
    assert r == {**r, "type": "reveal", "id": str(mid)}


@pytest.mark.parametrize("option", ["near", "any", "far"])
def test_return_date_is_inside_its_hidden_range(user, db, option):
    a = user("asha")
    s = get_settings()
    lo, hi = s.return_ranges[option]
    lo = max(lo, s.cooling_days)
    before = datetime.now(timezone.utc)
    mid = uuid.UUID(a.write(TEXT, option))
    m = db.get(Message, mid)
    assert before + timedelta(days=lo) - timedelta(seconds=5) <= m.return_at
    assert m.return_at <= datetime.now(timezone.utc) + timedelta(days=hi)


def test_inactive_author_gets_the_return_on_next_catch(user, db, monkeypatch):
    a = user("asha")
    mid = a.write(TEXT)
    later = clock.now() + timedelta(days=2000)
    monkeypatch.setattr(clock, "now", lambda: later)
    assert a.catch()["id"] == mid


# ---- spending -----------------------------------------------------------------

def test_reveal_works_and_is_free_with_zero_catches(user, db):
    a = user("asha")
    mid = a.write(TEXT)
    a.post("/dev/force-due")
    set_catches(db, "asha", free=0)
    r = a.catch()
    assert r["type"] == "reveal" and r["id"] == mid
    assert a.me()["free_catches"] == 0


def test_empty_river_does_not_spend(user):
    a = user("asha")
    before = a.me()["free_catches"]
    assert a.catch() == {"type": "river_empty"}
    assert a.me()["free_catches"] == before


def test_out_of_catches_then_bonus_spends_after_free(user, db):
    a = user("asha")
    seed(db, "other", 5)
    set_catches(db, "asha", free=1, bonus=1)
    assert a.catch()["type"] == "message"
    assert a.me() == {**a.me(), "free_catches": 0, "bonus_catches": 1}
    assert a.catch()["type"] == "message"
    assert a.me()["bonus_catches"] == 0
    assert a.catch() == {"type": "out_of_catches"}


def test_two_simultaneous_catches_cannot_both_spend_the_last_catch(user, db):
    a = user("asha")
    a.me()
    seed(db, "other", 5)
    set_catches(db, "asha", free=1)
    uid = dev_user_id("asha")

    barrier = threading.Barrier(2)
    results = []

    def go():
        with SessionLocal() as s:
            barrier.wait()
            results.append(river.catch(s, uid))

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    kinds = sorted("message" if isinstance(r, river.Caught) else r for r in results)
    assert kinds == ["message", "out_of_catches"]
    assert db.get(User, uid, populate_existing=True).free_catches == 0


def test_daily_refill_uses_local_midnight(user, db, monkeypatch):
    a = user("asha")
    set_catches(db, "asha", free=0)
    db.execute(
        update(User).where(User.id == dev_user_id("asha")).values(free_refilled_on=datetime(2026, 10, 15).date())
    )
    db.commit()
    # 18:29 UTC on 15 Oct is 23:59 in Kolkata: still the same day.
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 10, 15, 18, 29, tzinfo=timezone.utc))
    assert a.me()["free_catches"] == 0
    # 18:31 UTC is 00:01 on 16 Oct in Kolkata: refilled.
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 10, 15, 18, 31, tzinfo=timezone.utc))
    assert a.me()["free_catches"] == get_settings().free_catches_per_day


# ---- writing rules ------------------------------------------------------------

def test_write_limits_and_reasons(user):
    a = user("asha")
    r = a.post("/messages", {"text": "too short", "return_option": "any"})
    assert r.status_code == 422 and "20 characters" in r.json()["detail"]
    r = a.post("/messages", {"text": TEXT + " call 98765 43210", "return_option": "any"})
    assert r.status_code == 422 and "phone" in r.json()["detail"]
    r = a.post("/messages", {"text": TEXT, "return_option": "tomorrow"})
    assert r.status_code == 422

    for _ in range(3):
        a.write(TEXT)
    r = a.post("/messages", {"text": TEXT, "return_option": "any"})
    assert r.status_code == 422 and "tomorrow" in r.json()["detail"]
    assert a.me()["writes_left"] == 0 and a.me()["drifting"] == 3


# ---- notes ----------------------------------------------------------------------

def test_notes_only_on_caught_messages_and_only_once(user, db):
    a, b = user("asha"), user("bilal")
    mid = a.write(TEXT)
    assert b.post(f"/messages/{mid}/note", {"note": "hello"}).status_code == 404
    b.catch()
    assert b.post(f"/messages/{mid}/note", {"note": "x"}).status_code == 422
    assert b.post(f"/messages/{mid}/note", {"note": "mail me a@b.co"}).status_code == 422
    assert b.post(f"/messages/{mid}/note", {"note": "hello"}).status_code == 204
    assert b.post(f"/messages/{mid}/note", {"note": "again"}).status_code == 409


def test_notes_are_not_shown_to_other_catchers(user, db):
    a, b, c = user("asha"), user("bilal"), user("chitra")
    mid = a.write(TEXT)
    b.catch()
    b.post(f"/messages/{mid}/note", {"note": "secret note for asha"})
    r = c.catch()
    assert "secret note" not in json.dumps(r)


# ---- reports --------------------------------------------------------------------

def test_reports_auto_hide_after_threshold(user, db):
    a = user("asha")
    mid = a.write(TEXT)
    for name in ["r1", "r2", "r3"]:
        r = user(name)
        assert r.catch()["id"] == mid
        assert r.post(f"/messages/{mid}/report").status_code == 204
        r.post(f"/messages/{mid}/report")  # repeat report from same user doesn't count
    assert db.get(Message, uuid.UUID(mid), populate_existing=True).status == "hidden"
    assert user("r4").catch() == {"type": "river_empty"}


# ---- leaks ------------------------------------------------------------------------

def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_no_response_includes_author_id_or_return_at(user, db):
    a, b = user("asha"), user("bilal")
    mid = a.write(TEXT)
    b_mid = b.write(TEXT + " bilal")
    m = db.get(Message, uuid.UUID(mid))
    secrets = [str(dev_user_id("asha")), str(dev_user_id("bilal")), m.return_at.isoformat()[:16]]

    responses = [
        a.get("/me"),
        b.post("/catch"),
        b.post(f"/messages/{mid}/note", {"note": "nice one"}),
        a.post("/catch"),
        a.post("/dev/force-due"),
        a.post("/catch"),
        a.post(f"/messages/{mid}/keep"),
        a.get("/yours"),
        b.get("/yours"),
        b.post(f"/messages/{b_mid}/report"),
    ]
    for r in responses:
        assert r.status_code < 500, r.text
        if not r.content:
            continue
        body = r.json()
        assert not {"author_id", "return_at", "return_option", "rand_key"} & set(_keys(body)), r.text
        for s in secrets:
            assert s not in r.text, f"{s} leaked in {r.request.url}: {r.text}"
