from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.application.ai.contracts import ProviderGenerateRequest, ProviderName
from app.application.ai.costing import estimate_call_cost_usd
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.config.settings import get_settings


def _parse_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _sum_cost_report_cents(cost_report: dict[str, Any]) -> Decimal | None:
    data = cost_report.get("data")
    if not isinstance(data, list):
        return None

    total_cents = Decimal("0")
    found = False
    for bucket in data:
        if not isinstance(bucket, dict):
            continue
        results = bucket.get("results")
        if not isinstance(results, list):
            continue
        for row in results:
            if not isinstance(row, dict):
                continue
            # Anthropic Cost API reports decimal strings in lowest units (cents).
            amount = _parse_decimal(row.get("amount"))
            if amount is not None:
                total_cents += amount
                found = True
    return total_cents if found else None


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


async def _check_messages_api(*, model_name: str) -> dict[str, Any]:
    provider = AnthropicProviderAdapter()
    request = ProviderGenerateRequest(
        model_name=model_name,
        prompt="Reply with exactly: OK",
        system_prompt="You are a healthcheck assistant.",
        temperature=0.0,
        max_output_tokens=32,
    )
    result = await provider.generate(request)
    est_cost = estimate_call_cost_usd(
        provider=ProviderName.ANTHROPIC,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    return {
        "ok": True,
        "model": result.model_name,
        "output_text": (result.output_text or "").strip(),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "estimated_cost_usd": float(est_cost),
    }


async def _fetch_admin_cost_report(
    *,
    admin_api_key: str,
    days: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.anthropic_base_url.rstrip("/")
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    params = {
        "starting_at": _iso_utc(start),
        "ending_at": _iso_utc(now),
        "group_by[]": "description",
    }
    headers = {
        "x-api-key": admin_api_key,
        "anthropic-version": settings.anthropic_api_version,
    }
    url = f"{base_url}/v1/organizations/cost_report"
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = await client.get(url, headers=headers, params=params)
    if response.status_code >= 400:
        return {
            "ok": False,
            "status_code": response.status_code,
            "error_text": response.text,
        }
    parsed = response.json()
    total_cents = _sum_cost_report_cents(parsed)
    result: dict[str, Any] = {
        "ok": True,
        "window_days": days,
        "raw": parsed,
    }
    if total_cents is not None:
        result["total_cost_usd_window"] = float(total_cents / Decimal("100"))
    return result


async def _run(args: argparse.Namespace) -> int:
    print("=== Anthropic Messages API Healthcheck ===")
    try:
        health = await _check_messages_api(model_name=args.model_name)
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic script
        print("messages_api: FAILED")
        print(f"error: {exc}")
        return 2

    print("messages_api: OK")
    print(f"model: {health['model']}")
    print(f"output_text: {health['output_text']}")
    print(f"input_tokens: {health['input_tokens']}")
    print(f"output_tokens: {health['output_tokens']}")
    print(f"latency_ms: {health['latency_ms']}")
    print(f"estimated_cost_usd: {health['estimated_cost_usd']}")

    print("\n=== Anthropic Usage/Cost Check ===")
    admin_key = os.getenv("ANTHROPIC_ADMIN_API_KEY")
    if not admin_key:
        print("admin_api: SKIPPED (set ANTHROPIC_ADMIN_API_KEY to enable cost report)")
        print("note: standard ANTHROPIC_API_KEY cannot fetch organization cost report.")
        return 0

    admin_result = await _fetch_admin_cost_report(
        admin_api_key=admin_key,
        days=args.days,
        timeout_seconds=args.timeout_seconds,
    )
    if not admin_result.get("ok"):
        print("admin_api: FAILED")
        print(f"status_code: {admin_result.get('status_code')}")
        print(f"error_text: {admin_result.get('error_text')}")
        return 3

    print("admin_api: OK")
    print(f"window_days: {admin_result.get('window_days')}")
    total_cost_usd = admin_result.get("total_cost_usd_window")
    if total_cost_usd is not None:
        print(f"total_cost_usd_window: {total_cost_usd}")
        if args.budget_usd is not None:
            remaining = float(Decimal(str(args.budget_usd)) - Decimal(str(total_cost_usd)))
            print(f"budget_usd: {args.budget_usd}")
            print(f"remaining_usd_estimate: {remaining}")
    else:
        print("total_cost_usd_window: unavailable (response shape may differ)")

    if args.dump_json:
        output_path = args.dump_json
        with open(output_path, "w", encoding="utf-8") as fp:
            json.dump(admin_result.get("raw", {}), fp, indent=2, ensure_ascii=True)
            fp.write("\n")
        print(f"cost_report_dump: {output_path}")

    print(
        "note: Anthropic API does not expose a direct 'remaining credits' field; "
        "remaining is estimated only if you provide --budget-usd."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Temporary Anthropic API diagnostics.")
    parser.add_argument("--model-name", type=str, default="claude-sonnet-4-6")
    parser.add_argument("--days", type=int, default=30, help="Cost report lookback window in days.")
    parser.add_argument("--budget-usd", type=float, default=None, help="Optional budget to estimate remaining.")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--dump-json", type=str, default=None, help="Optional path to save raw cost report JSON.")
    args = parser.parse_args()

    exit_code = asyncio.run(_run(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

