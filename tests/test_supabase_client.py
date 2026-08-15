from __future__ import annotations

import requests

from notion_trade_journal.exceptions import SupabaseAPIError
from notion_trade_journal.supabase_client import SupabaseClient


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: object | None = None,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = b"" if payload is None else b"{}"

    def json(self) -> object:
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


def build_client() -> SupabaseClient:
    return SupabaseClient("https://example.supabase.co", "secret", trades_table="trade_journal_trades")


def test_request_retries_transient_connection_failure(monkeypatch) -> None:
    client = build_client()
    client.session = FakeSession(
        [
            requests.ConnectionError("Connection reset by peer"),
            FakeResponse(200, [{"notion_page_id": "page-1"}]),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.supabase_client.sleep", lambda _: None)

    result = client.request("GET", "trade_journal_trades")

    assert result == [{"notion_page_id": "page-1"}]
    assert client.session.calls == 2


def test_request_retries_retryable_status_code(monkeypatch) -> None:
    client = build_client()
    client.session = FakeSession(
        [
            FakeResponse(503, {"message": "Service unavailable"}),
            FakeResponse(200, [{"notion_page_id": "page-1"}]),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.supabase_client.sleep", lambda _: None)

    result = client.request("GET", "trade_journal_trades")

    assert result == [{"notion_page_id": "page-1"}]
    assert client.session.calls == 2


def test_request_raises_after_retry_budget_is_exhausted(monkeypatch) -> None:
    client = build_client()
    client.session = FakeSession(
        [
            requests.ConnectionError("Connection reset by peer"),
            requests.ConnectionError("Connection reset by peer"),
            requests.ConnectionError("Connection reset by peer"),
        ]
    )
    monkeypatch.setattr("notion_trade_journal.supabase_client.sleep", lambda _: None)

    try:
        client.request("GET", "trade_journal_trades")
    except SupabaseAPIError as exc:
        assert "Request to Supabase failed" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected SupabaseAPIError after retry exhaustion.")

    assert client.session.calls == 3


def test_upsert_trades_normalizes_records_to_a_shared_keyset() -> None:
    client = build_client()
    session = FakeSession([FakeResponse(201, None)])
    captured: dict[str, object] = {}
    original_request = session.request

    def capture_request(**kwargs: object) -> FakeResponse:
        captured.update(kwargs)
        return original_request(**kwargs)

    session.request = capture_request  # type: ignore[method-assign]
    client.session = session

    inserted = client.upsert_trades(
        [
            {"notion_page_id": "page-1", "trade_name": "Trade 1", "pnl": 10.0},
            {"notion_page_id": "page-2", "trade_name": "Trade 2"},
        ]
    )

    assert inserted == 2
    assert captured["json"] == [
        {"notion_page_id": "page-1", "pnl": 10.0, "trade_name": "Trade 1"},
        {"notion_page_id": "page-2", "pnl": None, "trade_name": "Trade 2"},
    ]
