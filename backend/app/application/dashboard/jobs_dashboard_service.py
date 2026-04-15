from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_generation_run import JobGenerationRun
from app.infrastructure.database.models.user import User

WINDOW_DAY = "day"
WINDOW_WEEK = "week"
WINDOW_MONTH = "month"

WINDOW_DAYS_MAP: dict[str, int] = {
    WINDOW_DAY: 1,
    WINDOW_WEEK: 7,
    WINDOW_MONTH: 30,
}


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _round_cost(value: Any) -> float:
    return round(_to_float(value), 6)


def _window_days(window: str) -> int:
    return WINDOW_DAYS_MAP[window]


async def get_jobs_dashboard_summary(
    *,
    session: AsyncSession,
    current_user_id: UUID,
    window: str,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_days = _window_days(window)
    window_start = now - timedelta(days=window_days)

    # submitted_at is the source-of-truth; fall back to created_at for old rows.
    # Legacy compatibility: treat outcome='sent' as submitted when flag was not synced.
    submit_time_expr = func.coalesce(Job.submitted_at, Job.created_at)
    submitted_expr = or_(Job.is_submitted_to_upwork.is_(True), Job.outcome == "sent")
    submitted_in_window_expr = and_(submitted_expr, submit_time_expr >= window_start)

    jobs_stats_subquery = (
        select(
            Job.user_id.label("user_id"),
            func.coalesce(func.sum(case((submitted_expr, 1), else_=0)), 0).label("total_jobs_sent_all_time"),
            func.coalesce(func.sum(case((submitted_in_window_expr, 1), else_=0)), 0).label("jobs_sent_in_window"),
        )
        .group_by(Job.user_id)
        .subquery()
    )

    cost_stats_subquery = (
        select(
            JobGenerationRun.user_id.label("user_id"),
            func.coalesce(func.sum(JobGenerationRun.estimated_cost_usd), 0).label("total_ai_cost_usd_all_time"),
        )
        .group_by(JobGenerationRun.user_id)
        .subquery()
    )

    summary_stmt = (
        select(
            User.id.label("user_id"),
            User.display_name.label("display_name"),
            User.email.label("email"),
            func.coalesce(jobs_stats_subquery.c.total_jobs_sent_all_time, 0).label("total_jobs_sent_all_time"),
            func.coalesce(jobs_stats_subquery.c.jobs_sent_in_window, 0).label("jobs_sent_in_window"),
            func.coalesce(cost_stats_subquery.c.total_ai_cost_usd_all_time, 0).label("total_ai_cost_usd_all_time"),
        )
        .select_from(User)
        .outerjoin(jobs_stats_subquery, jobs_stats_subquery.c.user_id == User.id)
        .outerjoin(cost_stats_subquery, cost_stats_subquery.c.user_id == User.id)
    )
    rows = (await session.execute(summary_stmt)).all()

    leaderboard: list[dict[str, Any]] = []
    for row in rows:
        sent_in_window = _to_int(row.jobs_sent_in_window)
        avg_speed = sent_in_window / window_days
        leaderboard.append(
            {
                "user_id": str(row.user_id),
                "display_name": row.display_name,
                "email": row.email,
                "proposals_sent_in_window": sent_in_window,
                "avg_send_speed_per_day": avg_speed,
                "total_jobs_sent_all_time": _to_int(row.total_jobs_sent_all_time),
                "total_ai_cost_usd_all_time": _round_cost(row.total_ai_cost_usd_all_time),
            }
        )

    leaderboard.sort(
        key=lambda item: (
            -item["proposals_sent_in_window"],
            -item["avg_send_speed_per_day"],
            item["display_name"].lower(),
        )
    )
    for idx, item in enumerate(leaderboard, start=1):
        item["rank"] = idx

    current_user_payload = next((item for item in leaderboard if item["user_id"] == str(current_user_id)), None)
    if current_user_payload is None:
        current_user = await session.get(User, current_user_id)
        current_user_payload = {
            "rank": None,
            "user_id": str(current_user_id),
            "display_name": current_user.display_name if current_user is not None else "",
            "email": current_user.email if current_user is not None else "",
            "proposals_sent_in_window": 0,
            "avg_send_speed_per_day": 0.0,
            "total_jobs_sent_all_time": 0,
            "total_ai_cost_usd_all_time": 0.0,
        }

    return {
        "generated_at": now.isoformat(),
        "window_key": window,
        "window_days": window_days,
        "window_start_at": window_start.isoformat(),
        "window_end_at": now.isoformat(),
        "current_user": current_user_payload,
        "leaderboard": leaderboard,
        "leaderboard_user_count": len(leaderboard),
    }
