from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    date: str | None = None
    title: str | None = None
    content: str = Field(..., max_length=10000)


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = Field(None, max_length=10000)
    is_pinned: bool | None = None
