"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table users (
          id uuid primary key,
          created_at timestamptz not null default now(),
          tz text not null default 'Asia/Kolkata',
          free_catches int not null default 5,
          free_refilled_on date not null default current_date,
          bonus_catches int not null default 0 check (bonus_catches >= 0),
          writes_today int not null default 0,
          writes_counted_on date not null default current_date,
          check (free_catches >= 0)
        );

        create table messages (
          id uuid primary key default gen_random_uuid(),
          author_id uuid not null references users(id) on delete cascade,
          text text not null constraint text_length check (char_length(text) between 20 and 500),
          return_option text not null constraint return_option check (return_option in ('near','any','far')),
          created_at timestamptz not null default now(),
          return_at timestamptz not null,
          returned_at timestamptz,
          status text not null default 'active' constraint status check (status in ('active','hidden','deleted')),
          report_count int not null default 0,
          rand_key double precision not null default random()
        );
        create index ix_messages_status_rand on messages (status, rand_key);
        create index ix_messages_author_due on messages (author_id, return_at) where returned_at is null;

        create table catches (
          user_id uuid not null references users(id) on delete cascade,
          message_id uuid not null references messages(id) on delete cascade,
          caught_at timestamptz not null default now(),
          note text constraint note_length check (note is null or char_length(note) between 2 and 140),
          noted_at timestamptz,
          primary key (user_id, message_id)
        );
        create index ix_catches_message on catches (message_id);

        create table reports (
          reporter_id uuid not null references users(id) on delete cascade,
          target_type text not null constraint target_type check (target_type in ('message','note')),
          target_id text not null,
          created_at timestamptz not null default now(),
          primary key (reporter_id, target_type, target_id)
        );

        create table purchases (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null references users(id),
          provider text not null,
          provider_ref text not null unique,
          catches int not null,
          amount_paise int not null,
          created_at timestamptz not null default now()
        );
        """
    )


def downgrade() -> None:
    op.execute("drop table purchases, reports, catches, messages, users")
