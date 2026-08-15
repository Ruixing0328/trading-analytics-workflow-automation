from __future__ import annotations

import requests

from notion_trade_journal.exceptions import NotionAPIError
from notion_trade_journal.notion_client import NotionClient


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict | None = None,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}
        self.content = b"" if payload is None else b"{}"

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls = 0

    def request(self, **_: object) -> FakeResponse:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_request_retries_transient_connection_failure(monkeypatch) -> None:
    client = NotionClient("token", "2026-03-11")
    client.session = FakeSession(
        [
            requests.ConnectionError("Connection reset by peer"),
            FakeResponse(200, {"results": [{"id": "page-1"}]}),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.notion_client.sleep", lambda _: None)

    result = client.request("GET", "/search")

    assert result == {"results": [{"id": "page-1"}]}
    assert client.session.calls == 2


def test_request_retries_retryable_status_code(monkeypatch) -> None:
    client = NotionClient("token", "2026-03-11")
    client.session = FakeSession(
        [
            FakeResponse(503, {"message": "Service unavailable"}),
            FakeResponse(200, {"results": [{"id": "page-1"}]}),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.notion_client.sleep", lambda _: None)

    result = client.request("POST", "/data_sources/test/query", json={"page_size": 1})

    assert result == {"results": [{"id": "page-1"}]}
    assert client.session.calls == 2


def test_request_raises_after_retry_budget_is_exhausted(monkeypatch) -> None:
    client = NotionClient("token", "2026-03-11")
    client.session = FakeSession(
        [
            requests.ConnectionError("Connection reset by peer"),
            requests.ConnectionError("Connection reset by peer"),
            requests.ConnectionError("Connection reset by peer"),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.notion_client.sleep", lambda _: None)

    try:
        client.request("GET", "/search")
    except NotionAPIError as exc:
        assert "Request to Notion failed" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected NotionAPIError after retry exhaustion.")

    assert client.session.calls == 3
