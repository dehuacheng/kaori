from pydantic import BaseModel


class WeightCreate(BaseModel):
    date: str
    weight_kg: float
    notes: str | None = None
