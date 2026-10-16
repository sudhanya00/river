import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from . import clock


def _now() -> datetime:
    # Looked up at call time so the dev clock offset (and test patches of clock.now) apply.
    return clock.now()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    tz: Mapped[str] = mapped_column(Text, server_default="Asia/Kolkata")
    free_catches: Mapped[int] = mapped_column(Integer, server_default="5")
    free_refilled_on: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    bonus_catches: Mapped[int] = mapped_column(Integer, server_default="0")
    writes_today: Mapped[int] = mapped_column(Integer, server_default="0")
    writes_counted_on: Mapped[date] = mapped_column(Date, server_default=func.current_date())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("char_length(text) between 20 and 500", name="text_length"),
        CheckConstraint("return_option in ('near','any','far')", name="return_option"),
        CheckConstraint("status in ('active','hidden','deleted')", name="status"),
        Index("ix_messages_status_rand", "status", "rand_key"),
        Index(
            "ix_messages_author_due",
            "author_id",
            "return_at",
            postgresql_where=text("returned_at is null"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    return_option: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    return_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="active")
    report_count: Mapped[int] = mapped_column(Integer, server_default="0")
    rand_key: Mapped[float] = mapped_column(Double, server_default=func.random())


class Catch(Base):
    __tablename__ = "catches"
    __table_args__ = (
        CheckConstraint(
            "note is null or char_length(note) between 2 and 140", name="note_length"
        ),
        Index("ix_catches_message", "message_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    caught_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)
    noted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("target_type in ('message','note')", name="target_type"),
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_type: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(Text)
    provider_ref: Mapped[str] = mapped_column(Text, unique=True)
    catches: Mapped[int] = mapped_column(Integer)
    amount_paise: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
