from pydantic import BaseModel


class ReminderCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: str | None = None
    item_type: str = "todo"
    priority: int = 1


class ReminderUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: str | None = None
    item_type: str | None = None
    priority: int | None = None


class ReminderPush(BaseModel):
    new_date: str


class ReminderDone(BaseModel):
    is_done: bool
