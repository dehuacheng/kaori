from collections import OrderedDict
from datetime import date, timedelta

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse

from kaori.services import workout_service
from kaori.storage.file_store import save_photo
from kaori.web import templates

MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/jpeg",
}

EXERCISE_CATEGORIES = [
    "chest", "back", "legs", "shoulders", "arms", "core", "cardio", "full_body",
]

# Category icons for exercises without photos
CATEGORY_ICONS = {
    "chest": "🏋️",
    "back": "🔙",
    "legs": "🦵",
    "shoulders": "💪",
    "arms": "💪",
    "core": "🎯",
    "cardio": "🏃",
    "full_body": "🏋️",
}

router = APIRouter(prefix="/workouts")


# ---------------------------------------------------------------------------
# Exercise type management (MUST be before /{workout_id} routes)
# ---------------------------------------------------------------------------

def _group_exercise_types(types: list[dict]) -> OrderedDict:
    """Group exercise types by category for template display."""
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for et in types:
        cat = et.get("category") or "other"
        grouped.setdefault(cat, []).append(et)
    return grouped


@router.get("/exercises/manage")
async def exercise_management_page(request: Request, identified: int | None = None):
    exercise_types = await workout_service.list_exercise_types()
    grouped = _group_exercise_types(exercise_types)

    # Pending exercises without a category go into a separate section
    uncategorized_pending = [
        et for et in exercise_types
        if et.get("status") == "pending" and not et.get("category")
    ]

    identification_result = None
    if identified:
        identification_result = await workout_service.get_exercise_type(identified)

    return templates.TemplateResponse(
        request,
        "exercises.html",
        {
            "grouped_types": grouped,
            "categories": EXERCISE_CATEGORIES,
            "category_icons": CATEGORY_ICONS,
            "identification_result": identification_result,
            "uncategorized_pending": uncategorized_pending,
        },
    )


@router.get("/exercises/{type_id}/status")
async def exercise_status(request: Request, type_id: int):
    """HTMX polling endpoint: returns updated identification result card."""
    et = await workout_service.get_exercise_type(type_id)
    if not et:
        return templates.TemplateResponse(request, "exercises_status.html", {"et": None})
    return templates.TemplateResponse(request, "exercises_status.html", {"et": et})


@router.post("/exercises/add")
async def add_custom_exercise(
    name: str = Form(...),
    category: str = Form(None),
    notes: str = Form(None),
):
    await workout_service.create_exercise_type(
        name=name, category=category or None, notes=notes or None,
    )
    return RedirectResponse(url="/workouts/exercises/manage", status_code=303)


@router.post("/exercises/identify")
async def identify_exercise_web(
    photo: UploadFile = File(...),
    hint: str = Form(None),
):
    import asyncio
    image_bytes = await photo.read()
    if not image_bytes:
        return RedirectResponse(url="/workouts/exercises/manage", status_code=303)
    media_type = MEDIA_TYPE_MAP.get(photo.content_type, "image/jpeg")
    ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
    photo_path = save_photo(image_bytes, ext)

    # Create exercise type immediately, then LLM fills metadata in background
    result = await workout_service.create_exercise_from_photo(photo_path, user_hint=hint)
    asyncio.create_task(
        workout_service.run_exercise_identification(result["id"], photo_path, user_hint=hint)
    )
    return RedirectResponse(
        url=f"/workouts/exercises/manage?identified={result['id']}", status_code=303,
    )


@router.post("/exercises/{type_id}/toggle")
async def toggle_exercise_type(type_id: int, enable: int = Form(...)):
    await workout_service.toggle_exercise_type(type_id, enabled=bool(enable))
    return RedirectResponse(url="/workouts/exercises/manage", status_code=303)


@router.post("/exercises/{type_id}/delete")
async def delete_exercise_type(type_id: int):
    try:
        await workout_service.delete_exercise_type(type_id)
    except ValueError:
        pass
    return RedirectResponse(url="/workouts/exercises/manage", status_code=303)


# ---------------------------------------------------------------------------
# Workout list and creation
# ---------------------------------------------------------------------------

@router.get("/")
async def workouts_page(request: Request, d: str | None = None):
    target_date = d or date.today().isoformat()
    workouts = await workout_service.list_workouts(target_date=target_date)
    exercise_types = await workout_service.list_enabled_exercise_types()

    # Compute prev/next dates
    dt = date.fromisoformat(target_date)
    prev_date = (dt - timedelta(days=1)).isoformat()
    next_date = (dt + timedelta(days=1)).isoformat()

    return templates.TemplateResponse(
        request,
        "workouts.html",
        {
            "workouts": workouts,
            "exercise_types": exercise_types,
            "target_date": target_date,
            "prev_date": prev_date,
            "next_date": next_date,
            "today": date.today().isoformat(),
        },
    )


@router.post("/")
async def create_workout(
    workout_date: str = Form(None),
    notes: str = Form(None),
):
    target_date = workout_date or date.today().isoformat()
    result = await workout_service.create_workout(workout_date=target_date, notes=notes)
    return RedirectResponse(url=f"/workouts/{result['id']}", status_code=303)


# ---------------------------------------------------------------------------
# Workout detail (MUST be after /exercises/* routes)
# ---------------------------------------------------------------------------

@router.get("/{workout_id}")
async def workout_detail(request: Request, workout_id: int):
    workout = await workout_service.get_workout(workout_id)
    if not workout:
        return RedirectResponse(url="/workouts", status_code=303)
    exercise_types = await workout_service.list_enabled_exercise_types()
    analysis = await workout_service.get_workout_analysis(workout_id)
    return templates.TemplateResponse(
        request,
        "workout_detail.html",
        {
            "workout": workout,
            "exercise_types": exercise_types,
            "category_icons": CATEGORY_ICONS,
            "analysis": analysis,
        },
    )


@router.post("/{workout_id}/exercises")
async def add_exercise(
    workout_id: int,
    exercise_type_id: int = Form(...),
    notes: str = Form(None),
):
    workout = await workout_service.get_workout(workout_id)
    order_index = len(workout["exercises"]) if workout else 0
    await workout_service.add_exercise(
        workout_id=workout_id,
        exercise_type_id=exercise_type_id,
        order_index=order_index,
        notes=notes,
    )
    return RedirectResponse(url=f"/workouts/{workout_id}", status_code=303)


@router.post("/{workout_id}/exercises/{exercise_id}/sets")
async def add_set(
    workout_id: int,
    exercise_id: int,
    set_number: int = Form(...),
    reps: int = Form(None),
    weight_kg: float = Form(None),
    duration_seconds: int = Form(None),
    notes: str = Form(None),
):
    await workout_service.add_set(
        workout_exercise_id=exercise_id,
        set_number=set_number,
        reps=reps,
        weight_kg=weight_kg,
        duration_seconds=duration_seconds,
        notes=notes,
    )
    return RedirectResponse(url=f"/workouts/{workout_id}", status_code=303)


@router.post("/{workout_id}/exercises/{exercise_id}/sets/{set_id}/delete")
async def delete_set(workout_id: int, exercise_id: int, set_id: int):
    await workout_service.delete_set(set_id)
    return RedirectResponse(url=f"/workouts/{workout_id}", status_code=303)


@router.post("/{workout_id}/exercises/{exercise_id}/delete")
async def delete_exercise(workout_id: int, exercise_id: int):
    await workout_service.delete_exercise(exercise_id)
    return RedirectResponse(url=f"/workouts/{workout_id}", status_code=303)


@router.post("/{workout_id}/summarize")
async def summarize_workout(workout_id: int):
    try:
        await workout_service.summarize_workout(workout_id)
    except ValueError:
        pass
    return RedirectResponse(url=f"/workouts/{workout_id}", status_code=303)


@router.post("/{workout_id}/delete")
async def delete_workout(workout_id: int):
    await workout_service.delete_workout(workout_id)
    return RedirectResponse(url="/workouts", status_code=303)
