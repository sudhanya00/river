"""Messages from the river: seeds only after every real message, labelled, no notes."""
import uuid

import pytest
from sqlalchemy import select, update

from app import seed
from app.models import Message, User
from app.auth import dev_user_id

pytestmark = pytest.mark.usefixtures("clean")

TEXT = "A message long enough to pass the twenty character minimum."
SEEDS = [f"Seed number {i}: drink some water, then go outside for five minutes." for i in range(3)]


@pytest.fixture
def seeded(db):
    assert seed.load(db, SEEDS) == 3
    return set(db.scalars(select(Message.id).where(Message.source == "seed")))


def refill(db, name):
    db.execute(update(User).where(User.id == dev_user_id(name)).values(free_catches=50))
    db.commit()


def test_seeds_only_come_after_every_real_message(user, db, seeded):
    a, b = user("asha"), user("bilal")
    real = {a.write(TEXT + " one"), a.write(TEXT + " two")}
    b.me()
    refill(db, "bilal")

    first_two = [b.catch() for _ in range(2)]
    assert {c["id"] for c in first_two} == real
    assert all(c["from_river"] is False for c in first_two)

    rest = [b.catch() for _ in range(3)]
    assert {uuid.UUID(c["id"]) for c in rest} == seeded
    assert all(c["from_river"] is True for c in rest)
    assert b.catch() == {"type": "river_empty"}


def test_a_new_real_message_jumps_ahead_of_remaining_seeds(user, db, seeded):
    a, b = user("asha"), user("bilal")
    b.me()
    refill(db, "bilal")
    assert b.catch()["from_river"] is True
    mid = a.write(TEXT)
    nxt = b.catch()
    assert nxt["id"] == mid and nxt["from_river"] is False


def test_seeds_take_no_notes(user, db, seeded):
    b = user("bilal")
    c = b.catch()
    assert c["from_river"]
    r = b.post(f"/messages/{c['id']}/note", {"note": "Thanks, river."})
    assert r.status_code == 422 and "don’t take notes" in r.json()["detail"]
    assert db.scalar(select(Message).where(Message.id == uuid.UUID(c["id"]))) is not None


def test_seeds_can_still_be_reported(user, seeded):
    b = user("bilal")
    c = b.catch()
    assert b.post(f"/messages/{c['id']}/report").status_code == 204


def test_seed_response_does_not_leak_the_system_author(user, seeded):
    r = user("bilal").post("/catch")
    assert str(seed.SEED_AUTHOR) not in r.text
    assert "author_id" not in r.json() and "return_at" not in r.json()


def test_loader_is_idempotent_and_parses_paragraphs(db):
    text = "# comment\nFirst seed message, long enough\nand wrapped onto a second line.\n\n\nSecond seed message, also long enough.\n"
    seeds = seed.parse(text)
    assert seeds == [
        "First seed message, long enough and wrapped onto a second line.",
        "Second seed message, also long enough.",
    ]
    assert seed.load(db, seeds) == 2
    assert seed.load(db, seeds) == 0


def test_loader_rejects_short_filtered_or_duplicate_seeds():
    errs = seed.problems(["too short", TEXT + " call 98765 43210", TEXT, TEXT])
    assert any("characters" in e for e in errs)
    assert any("filter" in e for e in errs)
    assert any("duplicate" in e for e in errs)


def test_the_shipped_seed_file_is_valid():
    seeds = seed.parse(seed.SEEDS_FILE.read_text(encoding="utf-8"))
    assert len(seeds) >= 20
    assert seed.problems(seeds) == []
