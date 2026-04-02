import asyncio
from datetime import date

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from kaori.services import meal_service
from kaori.storage import meal_repo
from kaori.storage.file_store import save_photo
from kaori.web import templates

router = APIRouter(prefix="/meals")

MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/jpeg",
}


@router.get("/")
async def list_meals(request: Request, date: str | None = None):
    from datetime import timedelta
    target = __import__("datetime").date.fromisoformat(date) if date else __import__("datetime").date.today()
    target_date = target.isoformat()
    prev_date = (target - timedelta(days=1)).isoformat()
    next_date = (target + timedelta(days=1)).isoformat()
    meals = await meal_service.list_by_date(target_date)
    totals = await meal_service.get_totals(target_date)
    has_pending = any(
        m.get("analysis_status") in ("pending", "analyzing") for m in meals
    )
    return templates.TemplateResponse(
        request,
        "meals.html",
        {"meals": meals, "target_date": target_date, "prev_date": prev_date,
         "next_date": next_date, "totals": totals, "has_pending": has_pending},
    )


@router.get("/{meal_id}/status")
async def meal_status(meal_id: int):
    """HTMX polling endpoint for analysis progress."""
    meal = await meal_service.get_by_id(meal_id)
    if not meal:
        return HTMLResponse("")

    still_processing = meal.get("analysis_status") in ("pending", "analyzing")

    photo_html = ""
    if meal.get("photo_path"):
        photo_html = f'<img src="/photos/{meal["photo_path"]}" class="list-item-thumb" alt="meal photo">'

    status = meal.get("analysis_status", "done")
    if status in ("pending", "analyzing"):
        badge = '<span class="badge analyzing">Analyzing...</span>'
        cal_text = "..."
        protein_text = ""
    elif status == "failed":
        badge = '<span class="badge failed">Failed</span>'
        cal_text = "?"
        protein_text = ""
    else:
        badge = '<span class="badge">AI</span>' if meal.get("is_estimated") else ""
        cal_text = f'{meal.get("calories") or 0} kcal'
        protein_text = f'<span class="list-item-sub">P:{int(meal.get("protein_g") or 0)}g</span>'

    poll_attr = (
        f'hx-get="/meals/{meal_id}/status" hx-trigger="every 3s" hx-swap="outerHTML"'
        if still_processing else ""
    )

    html = f"""
    <a href="/meals/{meal["id"]}" class="list-item" id="meal-{meal["id"]}" {poll_attr}>
        {photo_html}
        <div class="list-item-content">
            <span class="list-item-title">
                {(meal.get("meal_type") or "snack").capitalize()}
                {badge}
            </span>
            <span class="list-item-sub">{meal.get("description") or ""}</span>
        </div>
        <div class="list-item-right">
            <span class="list-item-value">{cal_text}</span>
            {protein_text}
        </div>
    </a>
    """
    return HTMLResponse(html)


@router.post("/")
async def create_meal(
    request: Request,
    meal_date: str = Form(None),
    meal_type: str = Form("snack"),
    description: str = Form(None),
    notes: str = Form(None),
    photo: UploadFile | None = File(None),
):
    today = meal_date or date.today().isoformat()
    photo_path = None

    if photo and photo.size and photo.size > 0:
        image_bytes = await photo.read()
        media_type = MEDIA_TYPE_MAP.get(photo.content_type, "image/jpeg")
        ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
        photo_path = save_photo(image_bytes, ext)

    meal_type = meal_service.auto_detect_meal_type(meal_type)

    meal_id, needs_analysis = await meal_service.create(
        meal_date=today, meal_type=meal_type,
        description=description, photo_path=photo_path, notes=notes,
    )

    if needs_analysis:
        asyncio.create_task(meal_service.run_analysis(
            meal_id, photo_path=photo_path, description=description, notes=notes,
        ))

    return RedirectResponse(url=f"/meals?date={today}", status_code=303)


@router.get("/{meal_id}")
async def meal_detail(request: Request, meal_id: int):
    meal = await meal_service.get_by_id(meal_id)
    if not meal:
        return RedirectResponse(url="/meals", status_code=303)
    analyses = await meal_service.list_analyses(meal_id)
    return templates.TemplateResponse(request, "meal_detail.html", {"meal": meal, "analyses": analyses})


@router.post("/{meal_id}/reprocess")
async def reprocess_meal(meal_id: int):
    raw = await meal_repo.get_raw(meal_id)
    if not raw:
        return RedirectResponse(url="/meals", status_code=303)

    await meal_service.reprocess_meal(meal_id)
    asyncio.create_task(meal_service.run_analysis(
        meal_id, photo_path=raw.get("photo_path"),
        description=raw.get("description"), notes=raw.get("notes"),
    ))

    return RedirectResponse(url=f"/meals/{meal_id}", status_code=303)


@router.post("/{meal_id}/analyses/{analysis_id}/activate")
async def activate_analysis(meal_id: int, analysis_id: int):
    await meal_service.rollback_analysis(meal_id, analysis_id)
    return RedirectResponse(url=f"/meals/{meal_id}", status_code=303)


@router.post("/{meal_id}/update")
async def update_meal(
    meal_id: int,
    meal_date: str = Form(None),
    meal_type: str = Form(None),
    description: str = Form(None),
    calories: int = Form(None),
    protein_g: float = Form(None),
    carbs_g: float = Form(None),
    fat_g: float = Form(None),
    notes: str = Form(None),
    reanalyze: str = Form("0"),
):
    meal_date = await meal_service.update(
        meal_id, date=meal_date, meal_type=meal_type, description=description,
        calories=calories, protein_g=protein_g, carbs_g=carbs_g,
        fat_g=fat_g, notes=notes,
    )

    if reanalyze == "1":
        raw = await meal_repo.get_raw(meal_id)
        if raw:
            await meal_service.reprocess_meal(meal_id)
            asyncio.create_task(meal_service.run_analysis(
                meal_id, photo_path=raw.get("photo_path"),
                description=raw.get("description"), notes=raw.get("notes"),
            ))
        return RedirectResponse(url=f"/meals/{meal_id}", status_code=303)

    return RedirectResponse(url=f"/meals?date={meal_date or date.today().isoformat()}", status_code=303)


@router.post("/{meal_id}/delete")
async def delete_meal(meal_id: int):
    meal_date = await meal_service.delete(meal_id)
    return RedirectResponse(url=f"/meals?date={meal_date or date.today().isoformat()}", status_code=303)
