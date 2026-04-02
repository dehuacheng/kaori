import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from kaori.config import BASE_DIR, PHOTOS_DIR, TEST_MODE, DB_PATH, setup_logging
from kaori.database import init_db
from kaori.api.router import api_router, health_router
from kaori.web.router import web_router

setup_logging()
logger = logging.getLogger("kaori")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Kaori starting up (test_mode=%s, db=%s, photos=%s)", TEST_MODE, DB_PATH, PHOTOS_DIR)
    if TEST_MODE:
        logger.warning("*** RUNNING IN TEST MODE — using %s ***", DB_PATH)
    await init_db()
    yield


app = FastAPI(title="Kaori", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "kaori" / "static")), name="static")
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

# Health check (unauthenticated)
app.include_router(health_router)

# API routes (JSON, authenticated)
app.include_router(api_router)

# Web routes (HTML — barebone testing frontend)
app.include_router(web_router)
