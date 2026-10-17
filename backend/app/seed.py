"""Load the reviewed messages in app/seeds.txt into the river as seeds. Run: python -m app.seed

Seeds are "from the river": caught only once a user has seen every real message, labelled in the
app, no notes. Safe to re-run: texts already in the river are skipped.
"""
import random
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, content_filter
from .auth import dev_user_id
from .config import get_settings
from .db import SessionLocal
from .models import Message
from .river import ensure_user

SEEDS_FILE = Path(__file__).with_name("seeds.txt")
SEED_AUTHOR = dev_user_id("river-seed")  # system author; never signs in, so seeds never return


def parse(text: str) -> list[str]:
    """Paragraphs separated by blank lines; '#' lines are comments. Lines in a paragraph are joined."""
    seeds, para = [], []
    for line in text.splitlines() + [""]:
        line = line.strip()
        if line.startswith("#"):
            continue
        if line:
            para.append(line)
        elif para:
            seeds.append(" ".join(para))
            para = []
    return seeds


def problems(seeds: list[str]) -> list[str]:
    s = get_settings()
    out = []
    for i, text in enumerate(seeds, 1):
        if not s.message_min <= len(text) <= s.message_max:
            out.append(f"#{i} is {len(text)} characters (needs {s.message_min}-{s.message_max}): {text[:60]}")
        elif reason := content_filter.check(text):
            out.append(f"#{i} blocked by the filter ({reason}): {text[:60]}")
    dupes = {t for t in seeds if seeds.count(t) > 1}
    out += [f"duplicate: {t[:60]}" for t in dupes]
    return out


def load(db: Session, seeds: list[str]) -> int:
    ensure_user(db, SEED_AUTHOR)
    existing = set(db.scalars(select(Message.text).where(Message.source == "seed")))
    added = 0
    for text in seeds:
        if text in existing:
            continue
        db.add(
            Message(
                author_id=SEED_AUTHOR,
                text=text,
                source="seed",
                return_option="far",
                return_at=clock.now() + timedelta(days=3650 + random.randint(0, 365)),
            )
        )
        added += 1
    db.commit()
    return added


def main() -> None:
    seeds = parse(SEEDS_FILE.read_text(encoding="utf-8"))
    if errs := problems(seeds):
        print(f"{SEEDS_FILE.name} has problems; nothing was loaded:", *errs, sep="\n  ")
        sys.exit(1)
    with SessionLocal() as db:
        added = load(db, seeds)
    print(f"Added {added} seeds ({len(seeds) - added} already in the river).")


if __name__ == "__main__":
    main()
