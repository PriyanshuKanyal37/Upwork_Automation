from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dashboard.jobs_dashboard_service import get_jobs_dashboard_summary
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.interfaces.api.dependencies.auth import get_current_user

DashboardWindow = Literal["day", "week", "month"]

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class JobsDashboardUserStatsResponse(BaseModel):
    rank: int | None
    user_id: str
    display_name: str
    email: str
    proposals_sent_in_window: int
    avg_send_speed_per_day: float
    total_jobs_sent_all_time: int
    total_ai_cost_usd_all_time: float


class JobsDashboardResponse(BaseModel):
    generated_at: str
    window_key: DashboardWindow
    window_days: int
    window_start_at: str
    window_end_at: str
    current_user: JobsDashboardUserStatsResponse
    leaderboard: list[JobsDashboardUserStatsResponse]
    leaderboard_user_count: int


@router.get("/jobs", response_model=JobsDashboardResponse)
async def jobs_dashboard(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    window: Annotated[DashboardWindow, Query()] = "week",
) -> dict[str, Any]:
    return await get_jobs_dashboard_summary(
        session=session,
        current_user_id=current_user.id,
        window=window,
    )

