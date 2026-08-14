from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.planning import router as planning_router
from app.api.postponement import router as postponement_router
from app.api.replanning import router as replanning_router
from app.api.recommendation import router as recommendation_router
from app.api.tasks import router as tasks_router
from app.database import Base, add_task_planning_columns, engine
from app.models.task import Task
from app.models.task_history import TaskHistory

app = FastAPI(title="Missed Task Replanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

Base.metadata.create_all(bind=engine)
add_task_planning_columns()
app.include_router(tasks_router)
app.include_router(planning_router)
app.include_router(replanning_router)
app.include_router(recommendation_router)
app.include_router(analytics_router)
app.include_router(postponement_router)
