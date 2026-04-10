from pydantic import BaseModel, Field


class HeartbeatConfig(BaseModel):
    enabled: bool = False
    debounce_minutes: int = Field(default=5, ge=1)
    prompt_template: str | None = None


class HeartbeatConfigUpdate(BaseModel):
    enabled: bool | None = None
    debounce_minutes: int | None = Field(None, ge=1)
    prompt_template: str | None = None
