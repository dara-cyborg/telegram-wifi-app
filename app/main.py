from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import initialize_database
from app.routers.api import router
from app.services.scheduler import configure_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    initialize_database(settings.database_path)
    scheduler = AsyncIOScheduler()
    configure_scheduler(scheduler, settings.database_path)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Internet Payment Tracker", lifespan=lifespan)
app.include_router(router)
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
