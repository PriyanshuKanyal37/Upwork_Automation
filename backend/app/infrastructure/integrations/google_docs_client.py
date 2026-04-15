from __future__ import annotations

import asyncio
import json
import re

import httpx

from app.infrastructure.config.settings import get_settings
from app.infrastructure.errors.exceptions import AppException


class GoogleDocsClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def create_document(self, *, access_token: str, title: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            create_response = await client.post(
                f"{self._settings.google_docs_api_base_url}/documents",
                headers=headers,
                json={"title": title},
            )
        if create_response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_create_failed",
                message="Google Docs document creation failed",
                details={"status_code": create_response.status_code},
            )
        create_payload = create_response.json()
        document_id = str(create_payload.get("documentId") or "").strip()
        if not document_id:
            raise AppException(
                status_code=503,
                code="google_docs_create_failed",
                message="Google Docs API did not return a document id",
            )
        return {
            "document_id": document_id,
            "document_url": f"https://docs.google.com/document/d/{document_id}",
        }

    async def create_document_from_markdown(
        self,
        *,
        access_token: str,
        title: str,
        markdown: str,
    ) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {access_token}"}
        html = _markdown_to_docs_html(markdown)
        metadata = {"name": title, "mimeType": "application/vnd.google-apps.document"}
        files = {
            "metadata": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
            "media": ("document.html", html.encode("utf-8"), "text/html; charset=UTF-8"),
        }
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.google_drive_upload_api_base_url}/files",
                headers=headers,
                params={"uploadType": "multipart", "fields": "id"},
                files=files,
            )
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_create_from_html_failed",
                message="Google Docs document creation from HTML failed",
                details={"status_code": response.status_code},
            )
        document_id = str(response.json().get("id") or "").strip()
        if not document_id:
            raise AppException(
                status_code=503,
                code="google_docs_create_from_html_failed",
                message="Google Drive API did not return a document id",
            )
        return {
            "document_id": document_id,
            "document_url": f"https://docs.google.com/document/d/{document_id}",
        }

    async def insert_markdown(
        self,
        *,
        access_token: str,
        document_id: str,
        markdown: str,
        inline_image_url: str | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {access_token}"}
        rendered = _markdown_to_docs_text(markdown)
        requests: list[dict] = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": rendered["text"],
                }
            }
        ]

        for style in rendered["styles"]:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": style["start"], "endIndex": style["end"]},
                        "paragraphStyle": {"namedStyleType": style["named_style"]},
                        "fields": "namedStyleType",
                    }
                }
            )

        for bullet in rendered["bullets"]:
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": bullet["start"], "endIndex": bullet["end"]},
                        "bulletPreset": bullet["preset"],
                    }
                }
            )

        for style in rendered["text_styles"]:
            text_style: dict[str, object] = {}
            fields: list[str] = []
            if style.get("bold"):
                text_style["bold"] = True
                fields.append("bold")
            link_url = style.get("link")
            if isinstance(link_url, str) and link_url.strip():
                text_style["link"] = {"url": link_url.strip()}
                fields.append("link")
            if fields:
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": style["start"], "endIndex": style["end"]},
                            "textStyle": text_style,
                            "fields": ",".join(fields),
                        }
                    }
                )

        if inline_image_url:
            image_caption = "\n\n## Flow Diagram\n\n"
            image_caption_index = 1 + len(rendered["text"])
            image_index = image_caption_index + len(image_caption)
            requests.append(
                {
                    "insertText": {
                        "location": {"index": image_caption_index},
                        "text": image_caption,
                    }
                }
            )
            requests.append(
                {
                    "insertInlineImage": {
                        "location": {"index": image_index},
                        "uri": inline_image_url,
                    }
                }
            )

        batch_payload = {"requests": requests}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.google_docs_api_base_url}/documents/{document_id}:batchUpdate",
                headers=headers,
                json=batch_payload,
            )
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_write_failed",
                message="Google Docs content write failed",
                details={"status_code": response.status_code},
            )

    async def append_flow_diagram(
        self,
        *,
        access_token: str,
        document_id: str,
        inline_image_url: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            doc_response = await client.get(
                f"{self._settings.google_docs_api_base_url}/documents/{document_id}",
                headers=headers,
                params={"fields": "body(content(endIndex))"},
            )
        if doc_response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_read_failed",
                message="Google Docs content read failed",
                details={"status_code": doc_response.status_code},
            )
        payload = doc_response.json()
        content = payload.get("body", {}).get("content") or []
        end_index = max((int(item.get("endIndex", 1)) for item in content if item.get("endIndex")), default=1)
        insertion_index = max(1, end_index - 1)

        caption_text = "\n\nFlow Diagram\n\n"
        heading_start = insertion_index + 2
        heading_end = heading_start + len("Flow Diagram")
        image_index = insertion_index + len(caption_text)
        requests = [
            {
                "insertText": {
                    "location": {"index": insertion_index},
                    "text": caption_text,
                }
            },
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": heading_start, "endIndex": heading_end},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType",
                }
            },
            {
                "insertInlineImage": {
                    "location": {"index": image_index},
                    "uri": inline_image_url,
                }
            },
        ]
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.google_docs_api_base_url}/documents/{document_id}:batchUpdate",
                headers=headers,
                json={"requests": requests},
            )
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_image_append_failed",
                message="Google Docs flow diagram append failed",
                details={"status_code": response.status_code},
            )

    async def upload_public_image(
        self,
        *,
        access_token: str,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": mime_type,
        }
        params = {"uploadType": "media", "fields": "id"}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            upload_response = await client.post(
                f"{self._settings.google_drive_upload_api_base_url}/files",
                headers=headers,
                params=params,
                content=image_bytes,
            )
        if upload_response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_drive_upload_failed",
                message="Google Drive image upload failed",
                details={"status_code": upload_response.status_code},
            )
        file_id = str(upload_response.json().get("id") or "").strip()
        if not file_id:
            raise AppException(
                status_code=503,
                code="google_drive_upload_failed",
                message="Google Drive upload did not return file id",
            )

        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            await client.patch(
                f"{self._settings.google_drive_api_base_url}/files/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "id"},
                json={"name": filename},
            )
            permission_response = await client.post(
                f"{self._settings.google_drive_api_base_url}/files/{file_id}/permissions",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"role": "reader", "type": "anyone"},
            )
        if permission_response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_drive_permission_failed",
                message="Google Drive permission update failed",
                details={"status_code": permission_response.status_code, "file_id": file_id},
            )
        candidates = [
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w2000",
            f"https://drive.google.com/uc?export=view&id={file_id}",
            f"https://drive.google.com/uc?export=download&id={file_id}",
        ]
        for _ in range(4):
            for url in candidates:
                if await self._is_public_image_url_ready(url=url):
                    return url
            # Drive permission propagation is eventually consistent.
            await asyncio.sleep(0.75)
        return candidates[0]

    async def _is_public_image_url_ready(self, *, url: str) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.connector_live_health_timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, headers={"Accept": "image/*"})
        except Exception:
            return False
        if response.status_code >= 400:
            return False
        content_type = str(response.headers.get("content-type") or "").lower()
        return content_type.startswith("image/")

    async def probe_token(self, *, access_token: str) -> dict[str, str | int]:
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v1/tokeninfo",
                params={"access_token": access_token},
            )
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="google_docs_probe_failed",
                message="Google Docs credential probe failed",
                details={"status_code": response.status_code},
            )
        payload = response.json()
        return {
            "audience": str(payload.get("audience") or ""),
            "scope": str(payload.get("scope") or ""),
            "expires_in": int(payload.get("expires_in") or 0),
        }


def _normalize_inline_markdown(text: str) -> str:
    collapsed = text.strip()
    if not collapsed:
        return ""
    return re.sub(r"\s+", " ", collapsed)


def _render_inline_markdown(content: str) -> tuple[str, list[dict[str, object]]]:
    plain_parts: list[str] = []
    style_runs: list[dict[str, object]] = []
    cursor = 0
    last = 0
    token_pattern = re.compile(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)|\*\*(.+?)\*\*|__(.+?)__|`([^`]+)`"
    )
    for match in token_pattern.finditer(content):
        prefix = content[last : match.start()]
        if prefix:
            plain_parts.append(prefix)
            cursor += len(prefix)

        if match.group(1) is not None and match.group(2) is not None:
            token = match.group(1)
            start = cursor
            plain_parts.append(token)
            cursor += len(token)
            style_runs.append({"start": start, "end": cursor, "link": match.group(2)})
        elif match.group(3) is not None or match.group(4) is not None:
            token = match.group(3) or match.group(4) or ""
            start = cursor
            plain_parts.append(token)
            cursor += len(token)
            style_runs.append({"start": start, "end": cursor, "bold": True})
        elif match.group(5) is not None:
            token = match.group(5)
            plain_parts.append(token)
            cursor += len(token)

        last = match.end()

    suffix = content[last:]
    if suffix:
        plain_parts.append(suffix)
        cursor += len(suffix)

    return "".join(plain_parts), style_runs


def _markdown_to_docs_text(markdown: str) -> dict[str, list[dict] | str]:
    text_parts: list[str] = []
    styles: list[dict[str, int | str]] = []
    bullets: list[dict[str, int | str]] = []
    text_styles: list[dict[str, int | str | bool]] = []
    cursor = 1

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            text_parts.append("\n")
            cursor += 1
            continue

        named_style: str | None = None
        is_bullet = False
        bullet_preset = "BULLET_DISC_CIRCLE_SQUARE"
        content = line

        if line.startswith("### "):
            named_style = "HEADING_3"
            content = line[4:].strip()
        elif line.startswith("## "):
            named_style = "HEADING_2"
            content = line[3:].strip()
        elif line.startswith("# "):
            named_style = "HEADING_1"
            content = line[2:].strip()
        elif re.match(r"^\d+\.\s+", line):
            is_bullet = True
            bullet_preset = "NUMBERED_DECIMAL_ALPHA_ROMAN"
            content = re.sub(r"^\d+\.\s+", "", line).strip()
        elif re.match(r"^[-*]\s+", line):
            is_bullet = True
            content = re.sub(r"^[-*]\s+", "", line).strip()

        content = _normalize_inline_markdown(content)
        content, inline_runs = _render_inline_markdown(content)
        text_parts.append(content + "\n")
        start = cursor
        end = start + len(content)
        cursor = end + 1

        if named_style and content:
            styles.append({"start": start, "end": end, "named_style": named_style})
        if is_bullet and content:
            bullets.append({"start": start, "end": end + 1, "preset": bullet_preset})
        for run in inline_runs:
            run_start = start + int(run["start"])
            run_end = start + int(run["end"])
            if run_end <= run_start:
                continue
            styled: dict[str, int | str | bool] = {"start": run_start, "end": run_end}
            if run.get("bold"):
                styled["bold"] = True
            if isinstance(run.get("link"), str):
                styled["link"] = str(run["link"])
            text_styles.append(styled)

    merged_text = "".join(text_parts) or "\n"
    return {
        "text": merged_text,
        "styles": styles,
        "bullets": bullets,
        "text_styles": text_styles,
    }


def _markdown_to_docs_html(markdown: str) -> str:
    try:
        from markdown_it import MarkdownIt
    except Exception as exc:
        raise AppException(
            status_code=503,
            code="markdown_renderer_unavailable",
            message="Markdown HTML renderer dependency is missing",
        ) from exc

    text = markdown.strip()
    if not text:
        text = "\n"
    md = MarkdownIt("commonmark", {"linkify": True}).enable("table").enable("strikethrough")
    body = md.render(text)
    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'></head>"
        f"<body>{body}</body></html>"
    )
