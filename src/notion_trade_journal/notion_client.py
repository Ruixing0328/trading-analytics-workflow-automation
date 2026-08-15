"""Thin Notion REST client used by the trade journal service."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from time import sleep
from typing import Any

import requests

from .constants import API_BASE_URL, MAX_SINGLE_PART_UPLOAD_BYTES
from .exceptions import NotionAPIError, TradeJournalConfigurationError

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_REQUEST_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.5


class NotionClient:
    """Small wrapper around the Notion REST API with project-specific helpers."""

    def __init__(self, token: str, notion_version: str, timeout_seconds: int = 30):
        if not token:
            raise TradeJournalConfigurationError("A Notion API token is required.")

        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": notion_version,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def retry_delay_seconds(self, attempt: int, *, response: requests.Response | None = None) -> float:
        """Return the sleep duration before retrying a transient Notion request."""

        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 0.0)
                except ValueError:
                    pass
        return min(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)), 2.0)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
        headers: dict | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Send a request to Notion and raise a rich exception on failure."""

        url = path if path.startswith("https://") else f"{API_BASE_URL}{path}"
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)
        if files:
            request_headers.pop("Content-Type", None)

        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    json=json,
                    data=data,
                    params=params,
                    files=files,
                    headers=request_headers,
                    timeout=timeout_seconds or self.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt >= MAX_REQUEST_ATTEMPTS:
                    raise NotionAPIError(f"Request to Notion failed: {exc}") from exc
                delay_seconds = self.retry_delay_seconds(attempt)
                logger.warning(
                    "Transient Notion request failure on %s %s (attempt %s/%s): %s. Retrying in %.1fs.",
                    method.upper(),
                    url,
                    attempt,
                    MAX_REQUEST_ATTEMPTS,
                    exc,
                    delay_seconds,
                )
                sleep(delay_seconds)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {"message": response.text}
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_REQUEST_ATTEMPTS:
                    delay_seconds = self.retry_delay_seconds(attempt, response=response)
                    logger.warning(
                        "Transient Notion API error on %s %s (attempt %s/%s): %s. Retrying in %.1fs.",
                        method.upper(),
                        url,
                        attempt,
                        MAX_REQUEST_ATTEMPTS,
                        body.get("message", f"HTTP {response.status_code}"),
                        delay_seconds,
                    )
                    sleep(delay_seconds)
                    continue
                raise NotionAPIError(
                    message=body.get("message", f"Notion API error ({response.status_code})"),
                    status_code=response.status_code,
                    code=body.get("code"),
                )

            if not response.content:
                return {}
            return response.json()

        raise NotionAPIError(f"Request to Notion failed after {MAX_REQUEST_ATTEMPTS} attempts.")

    def search_data_sources(self, query: str, page_size: int = 10) -> list[dict[str, Any]]:
        """Search for shared Notion data sources by title."""

        payload = {
            "query": query,
            "filter": {"value": "data_source", "property": "object"},
            "page_size": page_size,
        }
        response = self.request("POST", "/search", json=payload)
        return response.get("results", [])

    def find_data_source_by_title(self, title: str) -> dict[str, Any] | None:
        """Find a data source whose title matches the requested journal name."""

        normalized_target = title.strip().lower()
        candidates = self.search_data_sources(title)
        for candidate in candidates:
            candidate_title = extract_title(candidate.get("title", []))
            if candidate_title.strip().lower() == normalized_target:
                return candidate
        return candidates[0] if candidates else None

    def retrieve_data_source(self, data_source_id: str) -> dict[str, Any]:
        return self.request("GET", f"/data_sources/{data_source_id}")

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_payload: dict | None = None,
        sorts: list[dict] | None = None,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"page_size": page_size}
        if filter_payload:
            payload["filter"] = filter_payload
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        return self.request("POST", f"/data_sources/{data_source_id}/query", json=payload)

    def iterate_data_source_pages(
        self,
        data_source_id: str,
        *,
        filter_payload: dict | None = None,
        sorts: list[dict] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Return every page from a data source, following Notion pagination."""

        pages: list[dict[str, Any]] = []
        next_cursor: str | None = None
        while True:
            response = self.query_data_source(
                data_source_id,
                filter_payload=filter_payload,
                sorts=sorts,
                start_cursor=next_cursor,
                page_size=page_size,
            )
            pages.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
            if not next_cursor:
                break
        return pages

    def create_page(
        self,
        data_source_id: str,
        properties: dict[str, Any],
        *,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "parent": {"type": "data_source_id", "data_source_id": data_source_id},
            "properties": properties,
        }
        if children:
            payload["children"] = children
        return self.request("POST", "/pages", json=payload)

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update an existing page with a new set of properties."""

        return self.request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        """Fetch a single page so downstream syncs can use the full property payload."""

        return self.request("GET", f"/pages/{page_id}")

    def retrieve_block_children(
        self,
        block_id: str,
        *,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.request("GET", f"/blocks/{block_id}/children", params=params)

    def iterate_block_children(self, block_id: str, *, page_size: int = 100) -> list[dict[str, Any]]:
        """Return every top-level child block for the page or block."""

        children: list[dict[str, Any]] = []
        next_cursor: str | None = None
        while True:
            response = self.retrieve_block_children(
                block_id,
                start_cursor=next_cursor,
                page_size=page_size,
            )
            children.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
            if not next_cursor:
                break
        return children

    def append_block_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        """Append child blocks to a page or parent block."""

        return self.request("PATCH", f"/blocks/{block_id}/children", json={"children": children})

    def delete_block(self, block_id: str) -> dict[str, Any]:
        """Archive a block so generated Daily Results content can be replaced."""

        return self.request("DELETE", f"/blocks/{block_id}")

    def replace_page_children(self, page_id: str, children: list[dict[str, Any]]) -> None:
        """Replace the current top-level page blocks with the provided generated blocks."""

        for block in self.iterate_block_children(page_id):
            block_id = block.get("id")
            if block_id:
                self.delete_block(block_id)

        for index in range(0, len(children), 100):
            self.append_block_children(page_id, children[index : index + 100])

    def create_database(
        self,
        *,
        title: str,
        properties: dict[str, Any],
        parent_page_id: str | None = None,
        description: str | None = None,
        is_inline: bool = False,
    ) -> dict[str, Any]:
        """Create the Trade Journal database and its initial data source."""

        if parent_page_id:
            parent = {"type": "page_id", "page_id": parent_page_id}
        else:
            raise TradeJournalConfigurationError(
                "Provide a parent page ID when creating the database."
            )

        payload: dict[str, Any] = {
            "parent": parent,
            "title": [{"type": "text", "text": {"content": title}}],
            "is_inline": is_inline,
            "initial_data_source": {"properties": properties},
        }
        if description:
            payload["description"] = [{"type": "text", "text": {"content": description}}]
        return self.request("POST", "/databases", json=payload)

    def create_file_upload(
        self,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        mode: str = "single_part",
        external_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"mode": mode}
        if filename:
            payload["filename"] = filename
        if content_type:
            payload["content_type"] = content_type
        if external_url:
            payload["external_url"] = external_url
        return self.request("POST", "/file_uploads", json=payload)

    def retrieve_file_upload(self, file_upload_id: str) -> dict[str, Any]:
        return self.request("GET", f"/file_uploads/{file_upload_id}")

    def send_file_upload(self, file_upload_id: str, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, content_type)}
            return self.request("POST", f"/file_uploads/{file_upload_id}/send", files=files)

    def wait_for_uploaded_file(
        self,
        file_upload_id: str,
        *,
        timeout_seconds: int = 30,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, Any]:
        elapsed = 0.0
        while elapsed <= timeout_seconds:
            file_upload = self.retrieve_file_upload(file_upload_id)
            status = file_upload.get("status")
            if status == "uploaded":
                return file_upload
            if status in {"failed", "expired"}:
                raise NotionAPIError(f"File upload {file_upload_id} finished with status '{status}'.")
            sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
        raise NotionAPIError(f"Timed out waiting for file upload {file_upload_id} to complete.")

    def upload_local_file(self, file_path: str | Path) -> dict[str, Any]:
        """Upload a local file directly into Notion-managed storage."""

        path = Path(file_path)
        if not path.exists():
            raise NotionAPIError(f"Screenshot file not found: {path}")

        file_size = path.stat().st_size
        if file_size > MAX_SINGLE_PART_UPLOAD_BYTES:
            raise NotionAPIError(
                f"File exceeds the {MAX_SINGLE_PART_UPLOAD_BYTES // (1024 * 1024)} MB single-part upload limit: {path}"
            )

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        file_upload = self.create_file_upload(filename=path.name, content_type=content_type)
        file_upload_id = file_upload["id"]
        self.send_file_upload(file_upload_id, path)
        uploaded = self.wait_for_uploaded_file(file_upload_id)
        logger.info("Uploaded file %s as Notion file_upload %s", path.name, file_upload_id)
        return uploaded

    def import_external_file(self, external_url: str) -> dict[str, Any]:
        """Ask Notion to import a public file URL into the workspace."""

        filename = external_url.rstrip("/").split("/")[-1] or "screenshot"
        file_upload = self.create_file_upload(
            filename=filename,
            mode="external_url",
            external_url=external_url,
        )
        return self.wait_for_uploaded_file(file_upload["id"])


def extract_title(title_items: list[dict[str, Any]]) -> str:
    """Extract plain text from a Notion title array."""

    parts: list[str] = []
    for item in title_items:
        plain_text = item.get("plain_text")
        if plain_text:
            parts.append(plain_text)
            continue
        text = item.get("text", {})
        if text.get("content"):
            parts.append(text["content"])
    return "".join(parts)
