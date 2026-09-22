from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool


Theme = Literal["light", "dark", "system"]


class SettingsResponse(BaseModel):
    theme: Theme
    planning_reminders: bool
    missed_task_reminders: bool
    reflection_reminders: bool

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdateRequest(BaseModel):
    theme: Theme | None = None
    planning_reminders: StrictBool | None = None
    missed_task_reminders: StrictBool | None = None
    reflection_reminders: StrictBool | None = None
