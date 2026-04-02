from typing import Literal

from pydantic import BaseModel
from fastapi import APIRouter

from kaori.services import profile_service

router = APIRouter(prefix="/profile", tags=["api-profile"])


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    height_cm: float | None = None
    gender: str | None = None
    birth_date: str | None = None
    protein_per_kg: float | None = None
    carbs_per_kg: float | None = None
    calorie_adjustment_pct: float | None = None
    llm_mode: Literal["claude_cli", "claude_api", "codex_cli"] | None = None
    notes: str | None = None
    unit_body_weight: Literal["kg", "lb"] | None = None
    unit_height: Literal["cm", "in"] | None = None
    unit_exercise_weight: Literal["kg", "lb"] | None = None


@router.get("")
async def get_profile():
    return await profile_service.get_profile()


@router.put("")
async def update_profile(body: ProfileUpdate):
    return await profile_service.update_profile(
        display_name=body.display_name,
        height_cm=body.height_cm,
        gender=body.gender,
        birth_date=body.birth_date,
        protein_per_kg=body.protein_per_kg,
        carbs_per_kg=body.carbs_per_kg,
        calorie_adjustment_pct=body.calorie_adjustment_pct,
        llm_mode=body.llm_mode,
        notes=body.notes,
        unit_body_weight=body.unit_body_weight,
        unit_height=body.unit_height,
        unit_exercise_weight=body.unit_exercise_weight,
    )
