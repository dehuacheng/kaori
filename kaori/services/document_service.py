"""Document upload, extraction, and indexing service."""

import asyncio
import json
import logging

import kaori.llm
from kaori.llm import LLMError
from kaori.storage import document_repo

logger = logging.getLogger(__name__)


async def upload_and_extract(
    *,
    filename: str,
    original_type: str,
    raw_file_path: str,
    raw_file_paths: list[str],
    page_count: int,
    file_bytes_list: list[tuple[bytes, str]],
) -> int:
    """Save document metadata and kick off background extraction."""
    doc_id = await document_repo.create(
        filename=filename,
        original_type=original_type,
        raw_file_path=raw_file_path,
        raw_file_paths=json.dumps(raw_file_paths),
        page_count=page_count,
    )
    asyncio.create_task(_extract_document(doc_id, original_type, file_bytes_list))
    return doc_id


async def _extract_document(
    doc_id: int, original_type: str, file_bytes_list: list[tuple[bytes, str]],
) -> None:
    """Background task: call LLM to extract text and generate summary."""
    try:
        backend = kaori.llm.get_llm_backend(mode="codex_cli")

        extract_prompt = (
            "Extract ALL text and information from these document pages/images. "
            "Preserve the structure (headings, lists, tables) as plain text. "
            "If there are multiple pages, combine them in order. "
            "Output ONLY the extracted content, no commentary."
        )

        if len(file_bytes_list) == 1:
            data, media_type = file_bytes_list[0]
            if original_type == "pdf":
                response = await backend.analyze_image(
                    data, extract_prompt, media_type="application/pdf",
                )
            else:
                response = await backend.analyze_image(
                    data, extract_prompt, media_type="image/jpeg",
                )
        else:
            # Multiple files — use analyze_images for grouped extraction
            response = await backend.analyze_images(
                file_bytes_list, extract_prompt,
            )

        extracted_text = response.text.strip()

        # Generate summary
        summary_prompt = (
            f"Summarize the following document in 2-3 sentences. "
            f"Focus on the key information, purpose, and any actionable items.\n\n"
            f"Document:\n{extracted_text[:4000]}"
        )
        summary_response = await backend.complete(summary_prompt)
        summary = summary_response.text.strip()

        await document_repo.update_extraction(
            doc_id, extracted_text=extracted_text, summary=summary,
        )
        logger.info("Document %d extracted successfully (%d pages)", doc_id, len(file_bytes_list))

    except (LLMError, Exception):
        logger.exception("Document %d extraction failed", doc_id)
        await document_repo.set_failed(doc_id, "Extraction failed")


async def list_documents() -> list[dict]:
    return await document_repo.list_all()


async def get_document(doc_id: int) -> dict | None:
    return await document_repo.get(doc_id)


async def search_documents(query: str) -> list[dict]:
    return await document_repo.search(query)


async def delete_document(doc_id: int) -> bool:
    return await document_repo.delete(doc_id)
