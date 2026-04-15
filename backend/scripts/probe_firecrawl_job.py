from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from app.application.job.service import (
    _clean_firecrawl_job_markdown,
    _is_restricted_or_non_job_markdown,
    canonicalize_job_url,
)
from app.infrastructure.config.settings import get_settings
from app.infrastructure.integrations.firecrawl_client import (
    FirecrawlExtractionError,
    FirecrawlExtractResult,
    extract_markdown_bundle_from_url,
)


def _preview(text: str, limit: int = 700) -> str:
    normalized = text.strip().replace("\r\n", "\n")
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}\n\n...<truncated {len(normalized) - limit} chars>"


def _metadata_focus(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    keys = [
        "title",
        "og:title",
        "twitter:title",
        "description",
        "og:description",
        "og:image",
        "sourceURL",
        "url",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if key in metadata:
            out[key] = metadata[key]
    return out


def _resolve_api_key(explicit_api_key: str | None) -> str | None:
    if explicit_api_key and explicit_api_key.strip():
        return explicit_api_key.strip()
    settings = get_settings()
    return (settings.firecrawl_api_key or "").strip() or None


async def _run_probe(url: str, api_key: str | None, save_dir: Path | None) -> int:
    canonical = canonicalize_job_url(url)
    print(f"Input URL:      {url}")
    print(f"Canonical URL:  {canonical}")

    try:
        result: FirecrawlExtractResult = await extract_markdown_bundle_from_url(
            url=canonical,
            api_key=api_key,
        )
    except FirecrawlExtractionError as exc:
        print("\nFirecrawl status: FAILED")
        print(f"Code:            {exc.code}")
        print(f"Retryable:       {exc.retryable}")
        print(f"Message:         {exc.message}")
        return 1

    raw_markdown = (result.markdown or "").strip()
    cleaned_markdown = _clean_firecrawl_job_markdown(raw_markdown, metadata=result.metadata)
    restricted_like = _is_restricted_or_non_job_markdown(cleaned_markdown)

    print("\nFirecrawl status: OK")
    print(f"Raw length:       {len(raw_markdown)}")
    print(f"Cleaned length:   {len(cleaned_markdown)}")
    print(f"Restricted-like:  {restricted_like}")

    focused = _metadata_focus(result.metadata)
    print("\nMetadata (focused):")
    if focused:
        for key, value in focused.items():
            text = str(value).replace("\n", " ").strip()
            print(f"- {key}: {text[:220]}")
    else:
        print("- <none>")

    print("\nRaw markdown preview:")
    print(_preview(raw_markdown))

    print("\nCleaned markdown preview:")
    print(_preview(cleaned_markdown))

    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        raw_path = save_dir / "firecrawl_raw.md"
        cleaned_path = save_dir / "firecrawl_cleaned.md"
        raw_path.write_text(raw_markdown, encoding="utf-8")
        cleaned_path.write_text(cleaned_markdown, encoding="utf-8")
        print(f"\nSaved raw markdown to:     {raw_path}")
        print(f"Saved cleaned markdown to: {cleaned_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Firecrawl extraction and backend cleaning for an Upwork job URL."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=(
            "https://www.upwork.com/jobs/~022041005560876380510"
            "?referrer_url_path=%2Fnx%2Fsearch%2Fjobs%2Fdetails%2F~022041005560876380510"
        ),
        help="Upwork job URL to probe.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "Optional Firecrawl API key. If omitted, FIRECRAWL_API_KEY from backend settings is used."
        ),
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        help="Optional directory to save raw/cleaned markdown files.",
    )

    args = parser.parse_args()
    save_dir = Path(args.save_dir) if args.save_dir else None
    api_key = _resolve_api_key(args.api_key)
    return asyncio.run(_run_probe(url=args.url, api_key=api_key, save_dir=save_dir))


if __name__ == "__main__":
    raise SystemExit(main())
