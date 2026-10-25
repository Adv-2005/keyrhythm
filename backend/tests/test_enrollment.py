import asyncio
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, TypingSample, get_db
from app.main import app
from app.schemas import CHALLENGE_LENGTH


def test_startup_creates_sqlite_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    main = importlib.import_module("app.main")
    engine = create_engine(f"sqlite:///{(tmp_path / 'startup.sqlite3').as_posix()}")
    monkeypatch.setattr(main, "engine", engine)

    async def start() -> None:
        async with main.app.router.lifespan_context(main.app):
            assert set(inspect(engine).get_table_names()) == {
                "baseline_artifacts",
                "experiments",
                "profiles",
                "siamese_artifacts",
                "typing_samples",
            }

    asyncio.run(start())
    engine.dispose()


@pytest.fixture
def client_db(tmp_path: Path) -> Iterator[tuple[AsyncClient, sessionmaker[Session]]]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    yield client, factory
    asyncio.run(client.aclose())
    app.dependency_overrides.clear()
    engine.dispose()


def sample_payload() -> dict:
    n = CHALLENGE_LENGTH
    return {
        "consent_acknowledged": True,
        "session_id": "747a3880-e54c-4d99-a010-d9ab67999a46",
        "challenge_version": "fixed-1",
        "feature_version": "timing-1",
        "timing_sequence": {
            "hold_ms": [80.0] * n,
            "down_down_ms": [150.0] * (n - 1),
            "flight_ms": [70.0] * (n - 1),
            "long_pauses": [False] * (n - 1),
            "total_ms": 150.0 * (n - 1) + 80.0,
        },
    }


def test_profile_sample_lifecycle_and_privacy(
    client_db: tuple[AsyncClient, sessionmaker[Session]],
) -> None:
    client, factory = client_db

    async def exercise() -> None:
        invalid_profile = await client.post(
            "/api/v1/profiles", json={"display_name": "   "}
        )
        assert invalid_profile.status_code == 422
        created = await client.post(
            "/api/v1/profiles", json={"display_name": "  Participant 01  "}
        )
        assert created.status_code == 201
        profile_id = created.json()["id"]
        assert created.json()["display_name"] == "Participant 01"
        assert created.json()["sample_count"] == 0

        saved = await client.post(
            f"/api/v1/profiles/{profile_id}/samples", json=sample_payload()
        )
        assert saved.status_code == 201
        assert saved.json()["sample_count"] == 1
        assert "timing_sequence" not in saved.json()
        listed = await client.get("/api/v1/profiles")
        assert listed.json()[0]["sample_count"] == 1
        metadata = await client.get(f"/api/v1/profiles/{profile_id}/samples")
        assert metadata.json()["sample_count"] == 1
        assert "timing_sequence" not in metadata.text
        assert "key" not in metadata.text.lower()

        with factory() as db:
            row = db.scalar(select(TypingSample))
            assert row is not None
            assert set(row.timing_sequence) == {
                "hold_ms",
                "down_down_ms",
                "flight_ms",
                "long_pauses",
                "total_ms",
            }

        deleted = await client.delete(f"/api/v1/profiles/{profile_id}")
        assert deleted.status_code == 204
        assert (await client.get("/api/v1/profiles")).json() == []
        assert (
            await client.get(f"/api/v1/profiles/{profile_id}/samples")
        ).status_code == 404
        with factory() as db:
            assert db.scalar(select(TypingSample)) is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["timing_sequence"]["hold_ms"].pop(),
        lambda p: p["timing_sequence"]["hold_ms"].__setitem__(0, -1),
        lambda p: p["timing_sequence"]["hold_ms"].__setitem__(0, None),
        lambda p: p["timing_sequence"]["hold_ms"].__setitem__(0, "NaN"),
        lambda p: p["timing_sequence"]["flight_ms"].__setitem__(0, 999),
        lambda p: p["timing_sequence"]["long_pauses"].__setitem__(0, True),
        lambda p: p.__setitem__("challenge_version", "other"),
        lambda p: p.__setitem__("consent_acknowledged", False),
        lambda p: p.__setitem__("typed_text", "private content"),
        lambda p: p["timing_sequence"].__setitem__("keys", ["a"]),
    ],
)
def test_rejects_invalid_or_text_bearing_samples(
    client_db: tuple[AsyncClient, sessionmaker[Session]], change
) -> None:
    client, _ = client_db

    async def exercise() -> None:
        profile_id = (
            await client.post("/api/v1/profiles", json={"display_name": "P1"})
        ).json()["id"]
        payload = deepcopy(sample_payload())
        change(payload)
        response = await client.post(
            f"/api/v1/profiles/{profile_id}/samples", json=payload
        )
        assert response.status_code == 422
        assert "private content" not in response.text
        assert (await client.get(f"/api/v1/profiles/{profile_id}/samples")).json()[
            "sample_count"
        ] == 0

    asyncio.run(exercise())
