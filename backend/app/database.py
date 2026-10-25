"""Local SQLite persistence for profiles and numeric timing samples."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    samples: Mapped[list["TypingSample"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    baseline_artifact: Mapped["BaselineArtifact | None"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False
    )


class TypingSample(Base):
    __tablename__ = "typing_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    challenge_version: Mapped[str] = mapped_column(String(24), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(24), nullable=False)
    timing_sequence: Mapped[dict] = mapped_column(JSON, nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="samples")


class BaselineArtifact(Base):
    __tablename__ = "baseline_artifacts"

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    model_version: Mapped[str] = mapped_column(String(48), nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="baseline_artifact")


class SiameseArtifact(Base):
    __tablename__ = "siamese_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    model_version: Mapped[str] = mapped_column(String(48), nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_name: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)


default_path = Path(__file__).resolve().parents[1] / "data" / "keyrhythm.sqlite3"
database_url = os.environ.get(
    "KEYRHYTHM_DATABASE_URL", f"sqlite:///{default_path.as_posix()}"
)
if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
    Path(database_url.removeprefix("sqlite:///")).parent.mkdir(
        parents=True, exist_ok=True
    )

engine = create_engine(database_url, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")  # type: ignore[attr-defined]


SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
