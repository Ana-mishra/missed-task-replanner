from fastapi import FastAPI

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

Base.metadata.create_all(bind=engine)
add_task_planning_columns()
app.include_router(tasks_router)
app.include_router(planning_router)
app.include_router(replanning_router)
app.include_router(recommendation_router)
app.include_router(analytics_router)
app.include_router(postponement_router)
