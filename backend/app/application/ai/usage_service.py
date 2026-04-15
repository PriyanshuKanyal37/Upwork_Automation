from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.job_generation_run import JobGenerationRun
from app.infrastructure.database.models.user import User


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


def _build_totals_payload(
    *,
    runs_total: Any,
    runs_success: Any,
    runs_failed: Any,
    input_tokens_total: Any,
    output_tokens_total: Any,
    estimated_cost_usd_total: Any,
    last_activity_at: datetime | None,
) -> dict[str, Any]:
    return {
        "runs_total": _to_int(runs_total),
        "runs_success": _to_int(runs_success),
        "runs_failed": _to_int(runs_failed),
        "input_tokens_total": _to_int(input_tokens_total),
        "output_tokens_total": _to_int(output_tokens_total),
        "estimated_cost_usd_total": round(_to_float(estimated_cost_usd_total), 6),
        "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
    }


async def get_usage_summary(
    *,
    session: AsyncSession,
    current_user_id: UUID,
    window_days: int | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_start: datetime | None = None
    if window_days is not None:
        window_start = now - timedelta(days=window_days)

    run_time_filters = []
    if window_start is not None:
        run_time_filters.append(JobGenerationRun.created_at >= window_start)

    runs_total_expr = func.count(JobGenerationRun.id).label("runs_total")
    runs_success_expr = func.coalesce(
        func.sum(case((JobGenerationRun.status == "success", 1), else_=0)),
        0,
    ).label("runs_success")
    runs_failed_expr = func.coalesce(
        func.sum(case((JobGenerationRun.status == "failed", 1), else_=0)),
        0,
    ).label("runs_failed")
    input_tokens_expr = func.coalesce(func.sum(JobGenerationRun.input_tokens), 0).label("input_tokens_total")
    output_tokens_expr = func.coalesce(func.sum(JobGenerationRun.output_tokens), 0).label("output_tokens_total")
    estimated_cost_expr = func.coalesce(func.sum(JobGenerationRun.estimated_cost_usd), 0).label(
        "estimated_cost_usd_total"
    )
    last_activity_expr = func.max(JobGenerationRun.created_at).label("last_activity_at")

    team_stmt = select(
        runs_total_expr,
        runs_success_expr,
        runs_failed_expr,
        input_tokens_expr,
        output_tokens_expr,
        estimated_cost_expr,
        last_activity_expr,
    )
    if run_time_filters:
        team_stmt = team_stmt.where(*run_time_filters)
    team_row = (await session.execute(team_stmt)).one()
    team_totals = _build_totals_payload(
        runs_total=team_row.runs_total,
        runs_success=team_row.runs_success,
        runs_failed=team_row.runs_failed,
        input_tokens_total=team_row.input_tokens_total,
        output_tokens_total=team_row.output_tokens_total,
        estimated_cost_usd_total=team_row.estimated_cost_usd_total,
        last_activity_at=team_row.last_activity_at,
    )

    join_conditions = [JobGenerationRun.user_id == User.id]
    if run_time_filters:
        join_conditions.extend(run_time_filters)

    per_user_stmt = (
        select(
            User.id.label("user_id"),
            User.display_name.label("display_name"),
            User.email.label("email"),
            runs_total_expr,
            runs_success_expr,
            runs_failed_expr,
            input_tokens_expr,
            output_tokens_expr,
            estimated_cost_expr,
            last_activity_expr,
        )
        .select_from(User)
        .outerjoin(JobGenerationRun, and_(*join_conditions))
        .group_by(User.id, User.display_name, User.email)
        .order_by(estimated_cost_expr.desc(), User.display_name.asc())
    )

    user_rows = (await session.execute(per_user_stmt)).all()
    team_users: list[dict[str, Any]] = []
    for row in user_rows:
        team_users.append(
            {
                "user_id": str(row.user_id),
                "display_name": row.display_name,
                "email": row.email,
                "totals": _build_totals_payload(
                    runs_total=row.runs_total,
                    runs_success=row.runs_success,
                    runs_failed=row.runs_failed,
                    input_tokens_total=row.input_tokens_total,
                    output_tokens_total=row.output_tokens_total,
                    estimated_cost_usd_total=row.estimated_cost_usd_total,
                    last_activity_at=row.last_activity_at,
                ),
            }
        )

    current_user_payload = next((item for item in team_users if item["user_id"] == str(current_user_id)), None)
    if current_user_payload is None:
        current_user = await session.get(User, current_user_id)
        current_user_payload = {
            "user_id": str(current_user_id),
            "display_name": current_user.display_name if current_user is not None else "",
            "email": current_user.email if current_user is not None else "",
            "totals": _build_totals_payload(
                runs_total=0,
                runs_success=0,
                runs_failed=0,
                input_tokens_total=0,
                output_tokens_total=0,
                estimated_cost_usd_total=0,
                last_activity_at=None,
            ),
        }

    return {
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "window_start_at": window_start.isoformat() if window_start else None,
        "window_end_at": now.isoformat(),
        "current_user": current_user_payload,
        "team_totals": team_totals,
        "team_users": team_users,
        "team_user_count": len(team_users),
        "active_user_count": sum(1 for item in team_users if item["totals"]["runs_total"] > 0),
    }
