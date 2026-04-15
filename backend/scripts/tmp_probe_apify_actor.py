from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ACTOR_ID = "UL2325zphnyxDYpsp"
DEFAULT_URL = "https://www.upwork.com/jobs/~022041005560876380510?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"


def _call_actor(token: str, payload: dict[str, Any], timeout: int = 420) -> tuple[int, str]:
    endpoint = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
        f"?token={token}&format=json&clean=true"
    )
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), text
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}\n\n...<truncated {len(text) - max_len} chars>"


def _extract_summary(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"parse_error": True}

    if isinstance(parsed, list) and parsed:
        first = parsed[0]
        if isinstance(first, dict):
            return {
                "success": first.get("success"),
                "total_jobs_scraped": first.get("total_jobs_scraped"),
                "error": first.get("error"),
                "queries_processed": first.get("queries_processed"),
            }
    return {"shape": type(parsed).__name__}


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporary Apify actor probe for Upwork URL scraping.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Upwork job URL to test.")
    parser.add_argument(
        "--token",
        default=None,
        help="Apify API token. If omitted, APIFY_TOKEN env var is used.",
    )
    parser.add_argument(
        "--report",
        default="docs/apify_probe_output.md",
        help="Path to write markdown report.",
    )
    args = parser.parse_args()

    token = (args.token or os.getenv("APIFY_TOKEN") or "").strip()
    if not token:
        print("Missing Apify token. Provide --token or APIFY_TOKEN env var.")
        return 1

    cases: list[tuple[str, dict[str, Any]]] = [
        (
            "queries_with_job_url",
            {"queries": [args.url]},
        ),
        (
            "queries_with_job_url_no_apify_proxy",
            {"queries": [args.url], "proxyConfiguration": {"useApifyProxy": False}},
        ),
        (
            "queries_with_search_url",
            {"queries": ["https://www.upwork.com/freelance-jobs/automation/"]},
        ),
    ]

    report_lines: list[str] = [
        "# Temporary Apify Actor Probe",
        "",
        f"- Actor ID: `{ACTOR_ID}`",
        f"- Tested URL: `{args.url}`",
        "",
        "## Results",
        "",
    ]

    overall_ok = False

    for name, payload in cases:
        status, raw = _call_actor(token=token, payload=payload)
        summary = _extract_summary(raw)
        jobs_scraped = summary.get("total_jobs_scraped")
        is_success = bool(summary.get("success")) and isinstance(jobs_scraped, int) and jobs_scraped > 0
        overall_ok = overall_ok or is_success

        report_lines.extend(
            [
                f"### {name}",
                "",
                f"- HTTP status: `{status}`",
                f"- Parsed summary: `{json.dumps(summary, ensure_ascii=False)}`",
                "- Payload:",
                "```json",
                json.dumps(payload, ensure_ascii=False, indent=2),
                "```",
                "- Raw response preview:",
                "```json",
                _truncate(raw, max_len=2200),
                "```",
                "",
            ]
        )

    report_lines.extend(
        [
            "## Verdict",
            "",
            (
                "- Actor returned at least one scraped job item for tested cases."
                if overall_ok
                else "- Actor did not return usable scraped job data for tested cases."
            ),
            "",
            "Note: This is a temporary diagnostic script/report.",
        ]
    )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Report written to: {report_path}")
    print("Verdict:", "WORKING" if overall_ok else "NOT_WORKING_FOR_TESTED_CASES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
