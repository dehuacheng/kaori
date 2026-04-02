from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from kaori.services import profile_service
from kaori.web import templates

router = APIRouter(prefix="/profile")


@router.get("/")
async def profile_page(request: Request):
    profile = await profile_service.get_profile()
    return templates.TemplateResponse(request, "profile.html", {"profile": profile})


@router.post("/")
async def update_profile(
    request: Request,
    display_name: str = Form(None),
    height_cm: float = Form(None),
    gender: str = Form(None),
    birth_date: str = Form(None),
    protein_per_kg: float = Form(None),
    carbs_per_kg: float = Form(None),
    calorie_adjustment_pct: float = Form(None),
    llm_mode: str = Form(None),
    notes: str = Form(None),
):
    await profile_service.update_profile(
        display_name=display_name,
        height_cm=height_cm,
        gender=gender,
        birth_date=birth_date,
        protein_per_kg=protein_per_kg,
        carbs_per_kg=carbs_per_kg,
        calorie_adjustment_pct=calorie_adjustment_pct,
        llm_mode=llm_mode,
        notes=notes,
    )
    return RedirectResponse(url="/profile", status_code=303)
