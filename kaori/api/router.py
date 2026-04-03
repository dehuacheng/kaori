from fastapi import APIRouter, Depends

from kaori.api import meals, weight, profile, test_mode, exercise_types, workout, timer_presets, summary, finance
from kaori.api.auth import verify_token
from kaori.config import TEST_MODE

# Health check is outside the authenticated router
health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health")
async def health_check():
    return {"status": "ok", "test_mode": TEST_MODE}


# All other API routes require bearer token
api_router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])
api_router.include_router(meals.router)
api_router.include_router(weight.router)
api_router.include_router(profile.router)
api_router.include_router(test_mode.router)
api_router.include_router(exercise_types.router)
api_router.include_router(workout.router)
api_router.include_router(timer_presets.router)
api_router.include_router(summary.router)
api_router.include_router(finance.router)
