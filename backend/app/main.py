from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.plant import router as plant_router
from app.api.planning import router as planning_router
from app.api.postponement import router as postponement_router
from app.api.replanning import router as replanning_router
from app.api.recommendation import router as recommendation_router
from app.api.tasks import router as tasks_router
from app.api.task_history import router as task_history_router
from app.api.history import router as history_router
from app.api.auth import router as auth_router
from app.api.notifications import router as notifications_router
from app.api.settings import router as settings_router
from app.config import FRONTEND_ORIGIN
from app.database import (
    Base,
    add_task_ownership_column,
    add_task_planning_columns,
    add_user_name_confirmation_column,
    engine,
    upgrade_task_history_table,
    upgrade_task_history_task_fk,
)
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.daily_reflection import DailyReflection
from app.models.push_subscription import PushSubscription
from app.models.reminder_delivery import ReminderDelivery

app = FastAPI(title="Missed Task Replanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

Base.metadata.create_all(bind=engine)
add_task_planning_columns()
add_user_name_confirmation_column()
add_task_ownership_column()
upgrade_task_history_table()
upgrade_task_history_task_fk()
app.include_router(tasks_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(task_history_router)
app.include_router(history_router)
app.include_router(planning_router)
app.include_router(replanning_router)
app.include_router(recommendation_router)
app.include_router(analytics_router)
app.include_router(plant_router)
app.include_router(postponement_router)
