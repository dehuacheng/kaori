import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

from kaori.config import PHOTOS_DIR
from kaori.services import document_service

router = APIRouter(prefix="/documents", tags=["api-documents"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/heic": "image",
    "image/heif": "image",
}


@router.post("/upload")
async def upload_document(
    files: list[UploadFile] = File(...),
):
    """Upload one or more files as a single grouped document.

    Multiple images are treated as pages of the same document and
    extracted together via multi-image LLM analysis.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    docs_dir = PHOTOS_DIR / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    all_bytes: list[tuple[bytes, str]] = []  # (data, media_type)
    first_filename = None
    detected_type = None

    for f in files:
        content_type = f.content_type or "application/octet-stream"
        orig_type = ALLOWED_TYPES.get(content_type)
        if not orig_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. Supported: PDF, JPEG, PNG, HEIC",
            )
        file_bytes = await f.read()
        if not file_bytes:
            continue

        if first_filename is None:
            first_filename = f.filename or "document"
        if detected_type is None:
            detected_type = orig_type

        # Save raw file to disk
        ext = ".pdf" if orig_type == "pdf" else ".jpg"
        raw_filename = f"{uuid.uuid4().hex}{ext}"
        raw_path = docs_dir / raw_filename
        raw_path.write_bytes(file_bytes)
        saved_paths.append(str(raw_path.relative_to(PHOTOS_DIR)))
        all_bytes.append((file_bytes, content_type))

    if not saved_paths:
        raise HTTPException(status_code=400, detail="All files were empty")

    page_count = len(saved_paths)
    display_name = first_filename
    if page_count > 1:
        display_name = f"{first_filename} (+{page_count - 1} more)"

    doc_id = await document_service.upload_and_extract(
        filename=display_name,
        original_type=detected_type,
        raw_file_path=saved_paths[0],
        raw_file_paths=saved_paths,
        page_count=page_count,
        file_bytes_list=all_bytes,
    )

    return {"id": doc_id, "filename": display_name, "status": "processing", "page_count": page_count}


@router.get("")
async def list_documents():
    return await document_service.list_documents()


@router.get("/search")
async def search_documents(q: str = ""):
    if not q.strip():
        return await document_service.list_documents()
    return await document_service.search_documents(q)


@router.get("/{doc_id}")
async def get_document(doc_id: int):
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}")
async def delete_document(doc_id: int):
    deleted = await document_service.delete_document(doc_id)
    return {"id": doc_id, "deleted": deleted}
