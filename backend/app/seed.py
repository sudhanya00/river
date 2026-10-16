"""Seed the river with the prototype's messages under a system author. Run: python -m app.seed"""
import random
from datetime import timedelta

from sqlalchemy import select

from . import clock
from .auth import dev_user_id
from .db import SessionLocal
from .models import Message
from .river import ensure_user

SEEDS = [
    "If you're reading this on a bad day: it passes. I didn't believe that either, and here I am writing to a stranger.",
    "Called my dadi today just to hear her complain about the weather. Call yours if you still can.",
    "I quit the job everyone said was safe. It's been four months. I'm broke and I've never slept better.",
    "Somebody, somewhere, is proud of you and hasn't said it. I'm saying it for them.",
    "The chai at the station tastes better than any café chai. I will not be taking questions.",
    "I'm 34 and learning to swim. The kids in my class are 7. They're better than me and very kind about it.",
    "Today I finally told her. She said no. I'm weirdly relieved. Now I know.",
    "Whoever catches this: drink some water, then go outside for five minutes. That's the whole message.",
    "My mother learned WhatsApp just to send me good-morning flowers every day. I never reply. I should.",
    "Monsoon smell. That's it. If you know, you know.",
    "Rode 400 km alone this weekend. Didn't talk to anyone. Came back feeling like a person again.",
    "To the person who held the lift door for me on 3rd Feb: I was having the worst day. Thank you.",
    "It's okay to outgrow people. It's okay to miss them anyway.",
    "Learning guitar at 29. My fingers hurt. My neighbours hurt more.",
    "I keep a list of small things that went right. Today: the auto driver had change.",
    "Failed my exam for the second time. Trying a third. If you're also trying again, we're in this together.",
    "Grandpa planted a mango tree the year I was born. This summer it finally fruited. He didn't get to see it. I ate one for him.",
    "Write the email. Send the message. Book the ticket. The worst they can say is no.",
    "Moving to a new city means eating alone a lot. It gets better. Find one good dhaba.",
    "I think I'm finally happy and I'm scared to say it out loud. So I'm saying it here, where it floats away.",
    "Be patient with your parents' phones. They were patient with your handwriting.",
    "Saw the sunrise from a mountain today. Felt very small in the best way.",
    "Whatever you're waiting for, I hope it arrives on a random Tuesday when you least expect it.",
]

SEED_AUTHOR = dev_user_id("river-seed")


def main() -> None:
    with SessionLocal() as db:
        ensure_user(db, SEED_AUTHOR)
        existing = set(db.scalars(select(Message.text).where(Message.author_id == SEED_AUTHOR)))
        added = 0
        for text in SEEDS:
            if text in existing:
                continue
            # The seed author never catches, so park the return far away.
            db.add(
                Message(
                    author_id=SEED_AUTHOR,
                    text=text,
                    return_option="far",
                    return_at=clock.now() + timedelta(days=3650 + random.randint(0, 365)),
                )
            )
            added += 1
        db.commit()
        print(f"Seeded {added} messages ({len(existing)} already there).")


if __name__ == "__main__":
    main()
