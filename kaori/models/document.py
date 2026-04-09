from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    status: str  # "processing" or "done"


class DocumentSummary(BaseModel):
    id: int
    filename: str
    original_type: str
    summary: str | None = None
    created_at: str | None = None


class DocumentDetail(BaseModel):
    id: int
    filename: str
    original_type: str
    extracted_text: str | None = None
    summary: str | None = None
    created_at: str | None = None
