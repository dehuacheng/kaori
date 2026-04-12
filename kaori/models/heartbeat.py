from pydantic import BaseModel, Field


class HeartbeatConfig(BaseModel):
    enabled: bool = False
    debounce_minutes: int = Field(default=5, ge=1)
    prompt_template: str | None = None
    schedule_enabled: bool = False
    schedule_time: str = "21:00"
    nightly_prompt_template: str | None = None


class HeartbeatConfigUpdate(BaseModel):
    enabled: bool | None = None
    debounce_minutes: int | None = Field(None, ge=1)
    prompt_template: str | None = None
    schedule_enabled: bool | None = None
    schedule_time: str | None = None
    nightly_prompt_template: str | None = None
