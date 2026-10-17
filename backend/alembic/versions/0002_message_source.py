"""messages.source: 'user' for people, 'seed' for messages from the river itself

Seeds are only caught once a user has seen every real message, never take notes, and are labelled
"From the river" in the app.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# uuid5(_DEV_NAMESPACE, "river-seed"): the system author app/seed.py has always used.
SEED_AUTHOR = "1f94b030-5bad-5e01-ad21-be23f35b41ea"


def upgrade() -> None:
    op.execute(
        """
        alter table messages add column source text not null default 'user'
          constraint source check (source in ('user','seed'));
        drop index ix_messages_status_rand;
        create index ix_messages_source_status_rand on messages (source, status, rand_key);
        """
    )
    op.execute(f"update messages set source = 'seed' where author_id = '{SEED_AUTHOR}'")


def downgrade() -> None:
    op.execute(
        """
        drop index ix_messages_source_status_rand;
        create index ix_messages_status_rand on messages (status, rand_key);
        alter table messages drop column source;
        """
    )
