from fastapi import APIRouter

from kaori.web import dashboard, meals, profile, workout

web_router = APIRouter()
web_router.include_router(dashboard.router)
web_router.include_router(meals.router)
web_router.include_router(profile.router)
web_router.include_router(workout.router)
