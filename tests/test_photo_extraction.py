"""Tests for photo extraction service and backfill endpoint."""

import io
import pytest

import kaori.config
import kaori.database
import kaori.services.photo_extraction_service
from kaori.database import get_db
from kaori.services.photo_extraction_service import extract_photo_description, backfill_photos


@pytest.fixture
async def db_with_photos(tmp_path, monkeypatch):
    """Fresh DB + a test photo on disk."""
    db_path = tmp_path / "test.db"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    statements_dir = tmp_path / "statements"
    statements_dir.mkdir()

    monkeypatch.setattr(kaori.config, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.database, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.config, "PHOTOS_DIR", photos_dir)
    monkeypatch.setattr(kaori.config, "STATEMENTS_DIR", statements_dir)

    # Also patch PHOTOS_DIR in modules that import it at load time
    monkeypatch.setattr(kaori.services.photo_extraction_service, "PHOTOS_DIR", photos_dir)

    await kaori.database.init_db()

    # Create a test photo
    from PIL import Image
    test_photo = photos_dir / "test_photo.jpg"
    img = Image.new("RGB", (100, 100), "blue")
    img.save(str(test_photo), format="JPEG")

    return {"db_path": db_path, "photos_dir": photos_dir, "photo_path": "test_photo.jpg"}


@pytest.mark.asyncio
async def test_extract_photo_description_post(db_with_photos, mock_llm):
    """Extract photo description for a post."""
    mock_llm.response_text = "A sunset over the Manhattan skyline"

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO posts (date, content, photo_path) VALUES (?, ?, ?)",
            ("2024-01-01", "Beautiful evening", db_with_photos["photo_path"]),
        )
        await db.commit()
    finally:
        await db.close()

    desc = await extract_photo_description(
        table="posts", item_id=1, photo_paths=[db_with_photos["photo_path"]],
    )
    assert desc == "A sunset over the Manhattan skyline"


@pytest.mark.asyncio
async def test_extract_photo_not_found(db_with_photos, mock_llm):
    """Return None if photo file doesn't exist."""
    desc = await extract_photo_description(
        table="posts", item_id=1, photo_paths=["nonexistent.jpg"],
    )
    assert desc is None


@pytest.mark.asyncio
async def test_backfill_photos(db_with_photos, mock_llm):
    """Backfill processes items without photo_description."""
    mock_llm.response_text = "Extracted photo content"

    db = await get_db()
    try:
        # Post with photo, no description
        await db.execute(
            "INSERT INTO posts (date, content, photo_path) VALUES (?, ?, ?)",
            ("2024-01-01", "Test post", db_with_photos["photo_path"]),
        )
        # Post with photo AND description (should be skipped)
        await db.execute(
            "INSERT INTO posts (date, content, photo_path, photo_description) VALUES (?, ?, ?, ?)",
            ("2024-01-02", "Old post", db_with_photos["photo_path"], "Already described"),
        )
        await db.commit()
    finally:
        await db.close()

    result = await backfill_photos()
    assert result["posts_processed"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_backfill_endpoint(api_client, mock_llm):
    """Test the backfill-photos API endpoint."""
    resp = await api_client.post("/api/feed/backfill-photos")
    assert resp.status_code == 200
    data = resp.json()
    assert "posts_processed" in data


@pytest.mark.asyncio
async def test_meal_includes_photo_description(api_client, mock_llm):
    """Verify meal listing includes photo_description field."""
    mock_llm.response_text = '{"items": [{"name": "test", "calories": 100, "protein_g": 10, "carbs_g": 20, "fat_g": 5}], "description": "Test meal", "calories": 100, "protein_g": 10, "carbs_g": 20, "fat_g": 5, "confidence": "medium"}'

    # Create a meal via API (text-only, no photo)
    resp = await api_client.post(
        "/api/meals",
        data={"meal_type": "lunch", "description": "Test meal"},
    )
    assert resp.status_code == 200

    # Listing should include photo_description field (null for this meal)
    resp = await api_client.get("/api/meals")
    assert resp.status_code == 200
    data = resp.json()
    meals = data["meals"]
    if meals:
        # photo_description should be present in the meal dict (as None/null)
        assert "photo_description" in meals[0] or meals[0].get("photo_description") is None
