from fastapi import FastAPI

from app.api.tasks import router as tasks_router
from app.database import Base, engine
from app.models.task import Task

app = FastAPI(title="Missed Task Replanner API")

Base.metadata.create_all(bind=engine)
app.include_router(tasks_router)
