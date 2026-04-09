"""Tests for the document upload API."""

import io
import pytest


@pytest.mark.asyncio
async def test_upload_document_pdf(api_client, mock_llm):
    """Upload a PDF and verify response."""
    mock_llm.response_text = "Extracted text from document"

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    files = [("files", ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    resp = await api_client.post("/api/documents/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] > 0
    assert data["filename"] == "test.pdf"
    assert data["status"] == "processing"
    assert data["page_count"] == 1


@pytest.mark.asyncio
async def test_upload_document_image(api_client, mock_llm):
    """Upload an image and verify response."""
    mock_llm.response_text = "Extracted text from screenshot"

    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), "red")
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = [("files", ("screenshot.jpg", buf, "image/jpeg"))]
    resp = await api_client.post("/api/documents/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] > 0
    assert data["status"] == "processing"


@pytest.mark.asyncio
async def test_upload_multiple_images(api_client, mock_llm):
    """Upload multiple images grouped as one document."""
    mock_llm.response_text = "Extracted multi-page content"

    from PIL import Image
    bufs = []
    for color in ("red", "blue", "green"):
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), color).save(buf, format="JPEG")
        buf.seek(0)
        bufs.append(buf)

    files = [
        ("files", ("page1.jpg", bufs[0], "image/jpeg")),
        ("files", ("page2.jpg", bufs[1], "image/jpeg")),
        ("files", ("page3.jpg", bufs[2], "image/jpeg")),
    ]
    resp = await api_client.post("/api/documents/upload", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] > 0
    assert data["page_count"] == 3
    assert "+2 more" in data["filename"]


@pytest.mark.asyncio
async def test_upload_unsupported_type(api_client):
    """Reject unsupported file types."""
    files = [("files", ("test.txt", io.BytesIO(b"text"), "text/plain"))]
    resp = await api_client.post("/api/documents/upload", files=files)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_empty_file(api_client):
    """Reject empty files."""
    files = [("files", ("empty.pdf", io.BytesIO(b""), "application/pdf"))]
    resp = await api_client.post("/api/documents/upload", files=files)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_documents(api_client, mock_llm):
    """List documents after uploading one."""
    mock_llm.response_text = "Test content"

    pdf_bytes = b"%PDF-1.4 content"
    files = [("files", ("doc1.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    await api_client.post("/api/documents/upload", files=files)

    resp = await api_client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    assert docs[0]["filename"] == "doc1.pdf"


@pytest.mark.asyncio
async def test_get_document(api_client, mock_llm):
    """Get a specific document by ID."""
    mock_llm.response_text = "Extracted"

    pdf_bytes = b"%PDF-1.4 content"
    files = [("files", ("doc2.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    upload_resp = await api_client.post("/api/documents/upload", files=files)
    doc_id = upload_resp.json()["id"]

    resp = await api_client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["id"] == doc_id
    assert doc["filename"] == "doc2.pdf"
    assert doc["original_type"] == "pdf"


@pytest.mark.asyncio
async def test_get_document_not_found(api_client):
    """404 for nonexistent document."""
    resp = await api_client.get("/api/documents/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document(api_client, mock_llm):
    """Delete a document."""
    mock_llm.response_text = "Extracted"

    pdf_bytes = b"%PDF-1.4 content"
    files = [("files", ("to_delete.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    upload_resp = await api_client.post("/api/documents/upload", files=files)
    doc_id = upload_resp.json()["id"]

    resp = await api_client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify it's gone
    resp = await api_client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_documents(api_client, mock_llm):
    """Search documents by query."""
    mock_llm.response_text = "Extracted"

    resp = await api_client.get("/api/documents/search", params={"q": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json() == []

    # Empty query should list all
    resp = await api_client.get("/api/documents/search", params={"q": ""})
    assert resp.status_code == 200
