from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.usage_service import get_usage_summary
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageTotalsResponse(BaseModel):
    runs_total: int
    runs_success: int
    runs_failed: int
    input_tokens_total: int
    output_tokens_total: int
    estimated_cost_usd_total: float
    last_activity_at: str | None


class UsageUserResponse(BaseModel):
    user_id: str
    display_name: str
    email: str
    totals: UsageTotalsResponse


class UsageSummaryResponse(BaseModel):
    generated_at: str
    window_days: int | None
    window_start_at: str | None
    window_end_at: str
    current_user: UsageUserResponse
    team_totals: UsageTotalsResponse
    team_users: list[UsageUserResponse]
    team_user_count: int
    active_user_count: int


@router.get("/summary", response_model=UsageSummaryResponse)
async def usage_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    window_days: Annotated[int | None, Query(ge=1, le=365)] = None,
) -> dict[str, Any]:
    return await get_usage_summary(
        session=session,
        current_user_id=current_user.id,
        window_days=window_days,
    )
