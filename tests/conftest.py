"""Shared test fixtures for the Kaori backend test suite."""

import pytest

import kaori.config
import kaori.database
from tests.mock_llm import MockLLMBackend


@pytest.fixture
async def test_db(tmp_path, monkeypatch):
    """Fresh SQLite database per test, pointing all storage at a temp directory."""
    db_path = tmp_path / "test.db"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    statements_dir = tmp_path / "statements"
    statements_dir.mkdir()

    # Redirect DB and file paths to temp dir
    monkeypatch.setattr(kaori.config, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.database, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.config, "PHOTOS_DIR", photos_dir)
    monkeypatch.setattr(kaori.config, "STATEMENTS_DIR", statements_dir)

    # Initialize schema + seed data
    await kaori.database.init_db()
    return db_path


@pytest.fixture
def mock_llm(monkeypatch):
    """MockLLMBackend injected via monkeypatch on get_llm_backend."""
    backend = MockLLMBackend()

    def _get_mock(mode=None):
        return backend

    monkeypatch.setattr("kaori.llm.get_llm_backend", _get_mock)
    return backend


@pytest.fixture
async def seed_profile(test_db):
    """Insert a standard test profile for tests that need computed targets."""
    db = await kaori.database.get_db()
    try:
        await db.execute(
            "UPDATE user_profile SET height_cm=180, gender='male', "
            "birth_date='1994-01-15', protein_per_kg=1.6, carbs_per_kg=3.0, "
            "calorie_adjustment_pct=0 WHERE id=1"
        )
        await db.commit()
    finally:
        await db.close()


@pytest.fixture
async def api_client(test_db):
    """Async httpx client wired to the FastAPI app."""
    from httpx import AsyncClient, ASGITransport
    from kaori.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer dev-token"},
    ) as client:
        yield client
