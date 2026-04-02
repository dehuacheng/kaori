from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from kaori.services import weight_service
from kaori.web import templates

router = APIRouter(prefix="/weight")


@router.get("/")
async def weight_page(request: Request):
    trends = await weight_service.get_trends()
    return templates.TemplateResponse(
        request,
        "weight.html",
        {
            "weights": trends["weights_asc"],
            "latest": trends["latest"],
            "avg_7d": trends["avg_7d"],
            "delta_week": trends["delta_week"],
            "today": date.today().isoformat(),
        },
    )


@router.post("/")
async def log_weight(
    weight_date: str = Form(None),
    weight_kg: float = Form(...),
    notes: str = Form(None),
):
    await weight_service.log(weight_date=weight_date, weight_kg=weight_kg, notes=notes)
    return RedirectResponse(url="/weight", status_code=303)


@router.post("/{entry_id}/update")
async def update_weight(
    entry_id: int,
    weight_kg: float = Form(...),
    notes: str = Form(None),
):
    await weight_service.update(entry_id, weight_kg=weight_kg, notes=notes)
    return RedirectResponse(url="/weight", status_code=303)


@router.post("/{entry_id}/delete")
async def delete_weight(entry_id: int):
    await weight_service.delete(entry_id)
    return RedirectResponse(url="/weight", status_code=303)
