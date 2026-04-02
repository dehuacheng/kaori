from pydantic import BaseModel


class MealCreate(BaseModel):
    date: str
    meal_type: str = "snack"
    description: str | None = None
    notes: str | None = None


class MealUpdate(BaseModel):
    meal_type: str | None = None
    description: str | None = None
    calories: int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    notes: str | None = None


class FoodAnalysis(BaseModel):
    description: str
    items: list[str]
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: str  # "high", "medium", "low"
