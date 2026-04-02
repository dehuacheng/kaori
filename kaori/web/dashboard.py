from datetime import date

from fastapi import APIRouter, Request

from kaori.services import meal_service, weight_service
from kaori.web import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    today = date.today().isoformat()
    meals = await meal_service.list_by_date(today)
    totals = await meal_service.get_totals(today)
    trends = await weight_service.get_trends()
    profile = await weight_service.get_profile()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "today": today,
            "meals": meals,
            "totals": totals,
            "latest_weight": trends["latest"],
            "weights": trends["weights_asc"],
            "profile": profile,
        },
    )
