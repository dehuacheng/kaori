"""Tests for the document service."""

import pytest

import kaori.config
import kaori.database
from kaori.services import document_service
from kaori.storage import document_repo


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """Fresh SQLite database."""
    db_path = tmp_path / "test.db"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    statements_dir = tmp_path / "statements"
    statements_dir.mkdir()

    monkeypatch.setattr(kaori.config, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.database, "DB_PATH", db_path)
    monkeypatch.setattr(kaori.config, "PHOTOS_DIR", photos_dir)
    monkeypatch.setattr(kaori.config, "STATEMENTS_DIR", statements_dir)

    await kaori.database.init_db()
    return db_path


@pytest.mark.asyncio
async def test_create_document(db):
    """Create a document record."""
    doc_id = await document_repo.create(
        filename="test.pdf",
        original_type="pdf",
        raw_file_path="documents/abc.pdf",
    )
    assert doc_id > 0

    doc = await document_repo.get(doc_id)
    assert doc is not None
    assert doc["filename"] == "test.pdf"
    assert doc["original_type"] == "pdf"
    assert doc["status"] == "processing"


@pytest.mark.asyncio
async def test_update_extraction(db):
    """Update a document with extracted text and summary."""
    doc_id = await document_repo.create(
        filename="test.pdf",
        original_type="pdf",
        raw_file_path="documents/abc.pdf",
    )

    await document_repo.update_extraction(
        doc_id, extracted_text="Hello world", summary="A greeting",
    )

    doc = await document_repo.get(doc_id)
    assert doc["extracted_text"] == "Hello world"
    assert doc["summary"] == "A greeting"
    assert doc["status"] == "done"


@pytest.mark.asyncio
async def test_set_failed(db):
    """Mark a document as failed."""
    doc_id = await document_repo.create(
        filename="bad.pdf",
        original_type="pdf",
        raw_file_path="documents/bad.pdf",
    )

    await document_repo.set_failed(doc_id, "Parse error")

    doc = await document_repo.get(doc_id)
    assert doc["status"] == "failed"
    assert doc["error_message"] == "Parse error"


@pytest.mark.asyncio
async def test_list_and_search(db):
    """List all documents and search by keyword."""
    doc_id = await document_repo.create(
        filename="invoice.pdf",
        original_type="pdf",
        raw_file_path="documents/invoice.pdf",
    )
    await document_repo.update_extraction(
        doc_id, extracted_text="Invoice #123 for $500", summary="An invoice for five hundred dollars",
    )

    # List all
    docs = await document_repo.list_all()
    assert len(docs) == 1
    assert docs[0]["filename"] == "invoice.pdf"

    # Search by summary
    results = await document_repo.search("invoice")
    assert len(results) == 1

    # Search by extracted text
    results = await document_repo.search("$500")
    assert len(results) == 1

    # Search with no match
    results = await document_repo.search("nonexistent")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_delete_document(db):
    """Delete a document."""
    doc_id = await document_repo.create(
        filename="to_delete.pdf",
        original_type="pdf",
        raw_file_path="documents/delete.pdf",
    )

    deleted = await document_repo.delete(doc_id)
    assert deleted is True

    doc = await document_repo.get(doc_id)
    assert doc is None

    # Delete nonexistent
    deleted = await document_repo.delete(99999)
    assert deleted is False


@pytest.mark.asyncio
async def test_service_list_and_get(db):
    """Test service layer list and get."""
    doc_id = await document_repo.create(
        filename="contract.pdf",
        original_type="pdf",
        raw_file_path="documents/contract.pdf",
    )
    await document_repo.update_extraction(
        doc_id, extracted_text="Contract terms...", summary="Legal contract",
    )

    docs = await document_service.list_documents()
    assert len(docs) == 1

    doc = await document_service.get_document(doc_id)
    assert doc is not None
    assert doc["extracted_text"] == "Contract terms..."

    results = await document_service.search_documents("contract")
    assert len(results) == 1
