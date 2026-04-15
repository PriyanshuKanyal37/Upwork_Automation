from __future__ import annotations

import httpx

from app.infrastructure.config.settings import get_settings
from app.infrastructure.errors.exceptions import AppException


class AirtableClient:
    """Scaffold client for future Airtable publish activation."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def assert_publish_enabled(self) -> None:
        if not self._settings.airtable_publish_enabled:
            raise AppException(
                status_code=503,
                code="airtable_publish_not_enabled",
                message="Airtable publish is disabled",
            )
        if not self._settings.airtable_personal_access_token:
            raise AppException(
                status_code=503,
                code="airtable_token_missing",
                message="Airtable publish token is not configured",
            )

    async def probe(self) -> dict[str, str]:
        self.assert_publish_enabled()
        headers = {"Authorization": f"Bearer {self._settings.airtable_personal_access_token}"}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.get(f"{self._settings.airtable_api_base_url}/meta/whoami", headers=headers)
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="airtable_probe_failed",
                message="Airtable probe failed",
                details={"status_code": response.status_code},
            )
        payload = response.json()
        return {"id": str(payload.get("id") or ""), "name": str(payload.get("name") or "")}

    async def upsert_record(
        self,
        *,
        base_id: str,
        table_name: str,
        fields: dict[str, str],
    ) -> dict[str, str]:
        self.assert_publish_enabled()
        headers = {"Authorization": f"Bearer {self._settings.airtable_personal_access_token}"}
        async with httpx.AsyncClient(timeout=self._settings.connector_live_health_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.airtable_api_base_url}/{base_id}/{table_name}",
                headers=headers,
                json={"records": [{"fields": fields}]},
            )
        if response.status_code >= 400:
            raise AppException(
                status_code=503,
                code="airtable_publish_failed",
                message="Airtable publish failed",
                details={"status_code": response.status_code},
            )
        payload = response.json()
        records = payload.get("records") or []
        if not records:
            raise AppException(
                status_code=503,
                code="airtable_publish_failed",
                message="Airtable publish returned no records",
            )
        record_id = str(records[0].get("id") or "").strip()
        return {
            "record_id": record_id,
            "record_url": f"https://airtable.com/{record_id}" if record_id else "",
        }

