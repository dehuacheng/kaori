from pydantic import BaseModel, Field


# --- Response models ---

class AgentSession(BaseModel):
    id: str
    title: str | None = None
    status: str = "active"
    backend: str | None = None
    model: str | None = None
    message_count: int = 0
    token_count_approx: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AgentMessage(BaseModel):
    id: int
    session_id: str
    seq: int
    role: str
    content: str  # JSON-encoded backend message dict
    token_count_approx: int = 0
    created_at: str | None = None


class AgentSessionDetail(BaseModel):
    """Session with its messages."""
    session: AgentSession
    messages: list[AgentMessage] = []


class AgentMemoryEntry(BaseModel):
    id: int
    key: str
    value: str
    category: str = "general"
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentPrompt(BaseModel):
    id: int
    name: str
    prompt_text: str
    is_active: bool = False
    created_at: str | None = None
    updated_at: str | None = None


# --- Request models ---

class SessionCreate(BaseModel):
    backend: str | None = None
    model: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    status: str | None = Field(None, pattern=r"^(active|archived|deleted)$")


class MemoryUpsert(BaseModel):
    value: str
    category: str = "general"


class PromptCreate(BaseModel):
    name: str
    prompt_text: str


class PromptUpdate(BaseModel):
    name: str | None = None
    prompt_text: str | None = None


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
