from __future__ import annotations

from notion_trade_journal.config import Settings
from notion_trade_journal.mapping import build_notion_page_properties
from notion_trade_journal.models import TradeEntry
from notion_trade_journal.service import TradeJournalService

TRADE_DATA_SOURCE_ID = "data-source-123"
DAILY_RESULTS_DATA_SOURCE_ID = "daily-results-123"


class StubNotionClient:
    def __init__(self, *, duplicate_results: list[dict] | None = None) -> None:
        self.duplicate_results = duplicate_results or []
        self.updated_pages: list[tuple[str, dict]] = []
        self.created_pages: list[tuple[str, dict]] = []
        self.created_daily_pages: list[tuple[str, dict, list[dict]]] = []
        self.replaced_page_children: list[tuple[str, list[dict]]] = []
        self.upload_calls = 0
        self.query_calls = 0
        self.duplicate_query_calls = 0
        self.duplicate_filter_payloads: list[dict | None] = []
        self.trade_pages: dict[str, dict] = {}
        self.daily_results_pages: dict[str, dict] = {}

    def query_data_source(self, data_source_id: str, *, filter_payload: dict | None = None, sorts=None, page_size: int = 100) -> dict:
        self.query_calls += 1
        if data_source_id == DAILY_RESULTS_DATA_SOURCE_ID:
            date_equals = ((filter_payload or {}).get("date") or {}).get("equals")
            if date_equals:
                page = self.daily_results_pages.get(date_equals)
                return {"results": [page] if page else []}
            return {"results": list(self.daily_results_pages.values())}
        self.duplicate_query_calls += 1
        self.duplicate_filter_payloads.append(filter_payload)
        return {"results": list(self.duplicate_results)}

    def iterate_data_source_pages(self, data_source_id: str, *, filter_payload: dict | None = None, sorts=None, page_size: int = 100) -> list[dict]:
        assert data_source_id == TRADE_DATA_SOURCE_ID
        date_equals = ((filter_payload or {}).get("date") or {}).get("equals")
        if not date_equals:
            return list(self.trade_pages.values())
        matching = [page for page in self.trade_pages.values() if page["properties"]["Date"]["date"]["start"] == date_equals]
        return sorted(
            matching,
            key=lambda page: page["properties"].get("Entry Time", {}).get("date", {}).get("start") or "",
            reverse=True,
        )

    def update_page(self, page_id: str, properties: dict) -> dict:
        self.updated_pages.append((page_id, properties))
        for trade_date, page in list(self.daily_results_pages.items()):
            if page.get("id") == page_id:
                self.daily_results_pages[trade_date] = {**page, "properties": properties}
                break
        return {"id": page_id, "url": f"https://example.invalid/notion/{page_id}", "properties": properties}

    def create_page(self, data_source_id: str, properties: dict, *, children: list[dict] | None = None) -> dict:
        page_id = "created-page" if data_source_id == TRADE_DATA_SOURCE_ID else "daily-created-page"
        page = {"id": page_id, "url": f"https://example.invalid/notion/{page_id}", "properties": properties}
        if data_source_id == TRADE_DATA_SOURCE_ID:
            self.created_pages.append((data_source_id, properties))
            self.trade_pages[page_id] = page
        if data_source_id == DAILY_RESULTS_DATA_SOURCE_ID:
            self.created_daily_pages.append((data_source_id, properties, list(children or [])))
            self.daily_results_pages[properties["Date"]["date"]["start"]] = page
        return page

    def upload_local_file(self, file_path) -> dict:
        self.upload_calls += 1
        return {"id": "file-upload", "filename": "chart.png"}

    def import_external_file(self, external_url: str) -> dict:
        self.upload_calls += 1
        return {"id": "file-upload", "filename": "chart.png"}

    def retrieve_page(self, page_id: str) -> dict:
        if page_id in self.trade_pages:
            return self.trade_pages[page_id]
        if page_id in {page.get("id") for page in self.daily_results_pages.values()}:
            for page in self.daily_results_pages.values():
                if page.get("id") == page_id:
                    return page
        page = {
            "id": page_id,
            "url": f"https://example.invalid/notion/{page_id}",
            "properties": build_notion_page_properties(sample_trade()),
        }
        self.trade_pages[page_id] = page
        return page

    def replace_page_children(self, page_id: str, children: list[dict]) -> None:
        self.replaced_page_children.append((page_id, list(children)))


class StubSupabaseClient:
    def __init__(self) -> None:
        self.trades_table = "trade_journal_trades"
        self.upserted_records: list[dict] = []

    def upsert_trades(self, records: list[dict], *, on_conflict: str = "notion_page_id") -> int:
        assert on_conflict == "notion_page_id"
        self.upserted_records.extend(records)
        return len(records)


def sample_trade() -> TradeEntry:
    return TradeEntry.model_validate(
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Win",
            "pnl": 47.0,
            "screenshot_path": "/tmp/chart.png",
        }
    )


def build_service(client: StubNotionClient) -> TradeJournalService:
    settings = Settings(
        notion_token="secret-test",
        trade_journal_data_source_id=TRADE_DATA_SOURCE_ID,
        daily_results_data_source_id=DAILY_RESULTS_DATA_SOURCE_ID,
    )
    return TradeJournalService(settings, client=client)


def test_create_trade_entry_skips_duplicate_before_upload() -> None:
    client = StubNotionClient(
        duplicate_results=[{"id": "existing-page", "url": "https://example.invalid/notion/existing-page"}]
    )
    service = build_service(client)

    response = service.create_trade_entry(
        sample_trade(),
        validate_schema=False,
        duplicate_mode="skip",
    )

    assert response["action"] == "skipped"
    assert response["duplicate"] is True
    assert client.upload_calls == 0
    assert client.created_pages == []
    assert client.updated_pages == []


def test_create_trade_entry_upserts_duplicate() -> None:
    client = StubNotionClient(
        duplicate_results=[{"id": "existing-page", "url": "https://example.invalid/notion/existing-page"}]
    )
    service = build_service(client)

    response = service.create_trade_entry(
        sample_trade(),
        validate_schema=False,
        duplicate_mode="upsert",
    )

    assert response["action"] == "updated"
    assert response["duplicate"] is True
    assert client.upload_calls == 1
    assert len(client.updated_pages) == 1
    assert client.created_pages == []


def test_create_trade_entry_skips_duplicate_lookup_without_entry_time() -> None:
    client = StubNotionClient(
        duplicate_results=[{"id": "existing-page", "url": "https://example.invalid/notion/existing-page"}]
    )
    service = build_service(client)
    trade = TradeEntry.model_validate(
        {
            "date": "2025-07-15",
            "instrument": "MNQ",
            "direction": "Short",
            "result": "Loss",
            "pnl": -10.0,
        }
    )

    response = service.create_trade_entry(
        trade,
        validate_schema=False,
        duplicate_mode="skip",
    )

    assert response["action"] == "created"
    assert client.duplicate_query_calls == 0
    assert len(client.created_pages) == 1


def test_duplicate_lookup_includes_account_fields_when_present() -> None:
    client = StubNotionClient()
    service = build_service(client)
    trade = TradeEntry.model_validate(
        {
            "date": "2026-04-16",
            "instrument": "MNQ",
            "direction": "Short",
            "account_type": "Papertrade",
            "account_label": "Synthetic Account A",
            "entry_time": "2026-04-16T10:20:00-04:00",
            "result": "Loss",
            "pnl": -282,
        }
    )

    service.find_duplicate_trade_entry(TRADE_DATA_SOURCE_ID, trade)

    filter_terms = client.duplicate_filter_payloads[0]["and"]
    assert {"property": "Account Type", "select": {"equals": "Papertrade"}} in filter_terms
    assert {"property": "Account Label", "rich_text": {"equals": "Synthetic Account A"}} in filter_terms


def test_create_trade_entry_syncs_saved_page_to_supabase() -> None:
    client = StubNotionClient()
    supabase_client = StubSupabaseClient()
    settings = Settings(
        notion_token="secret-test",
        trade_journal_data_source_id=TRADE_DATA_SOURCE_ID,
        daily_results_data_source_id=DAILY_RESULTS_DATA_SOURCE_ID,
    )
    service = TradeJournalService(settings, client=client, supabase_client=supabase_client)

    response = service.create_trade_entry(
        sample_trade(),
        validate_schema=False,
        duplicate_mode="upsert",
    )

    assert response["action"] == "created"
    assert response["sync"]["supabase"] == {"rows_upserted": 1, "table": "trade_journal_trades"}
    assert response["sync"]["daily_results"]["action"] == "created"
    assert len(supabase_client.upserted_records) == 1
    assert supabase_client.upserted_records[0]["trade_name"] == "2026-04-03 MNQ Short 09:42"
    assert supabase_client.upserted_records[0]["trade_date"] == "2026-04-03"


def test_update_trade_screenshot_syncs_saved_page_to_supabase() -> None:
    client = StubNotionClient()
    supabase_client = StubSupabaseClient()
    settings = Settings(
        notion_token="secret-test",
        trade_journal_data_source_id=TRADE_DATA_SOURCE_ID,
        daily_results_data_source_id=DAILY_RESULTS_DATA_SOURCE_ID,
    )
    service = TradeJournalService(settings, client=client, supabase_client=supabase_client)

    response = service.update_trade_screenshot(
        "existing-page",
        screenshot_path="/tmp/chart.png",
    )

    assert response["action"] == "updated"
    assert response["sync"]["supabase"] == {"rows_upserted": 1, "table": "trade_journal_trades"}
    assert client.upload_calls == 1
    assert client.updated_pages[0][0] == "existing-page"
    assert client.updated_pages[0][1]["Screenshot"]["files"][0]["file_upload"]["id"] == "file-upload"
    assert len(supabase_client.upserted_records) == 1
    assert supabase_client.upserted_records[0]["notion_page_id"] == "existing-page"


def test_create_trade_entry_creates_daily_results_page() -> None:
    client = StubNotionClient()
    service = build_service(client)

    response = service.create_trade_entry(
        sample_trade(),
        validate_schema=False,
        duplicate_mode="upsert",
    )

    assert response["sync"]["daily_results"]["action"] == "created"
    assert len(client.created_daily_pages) == 1
    _, properties, children = client.created_daily_pages[0]
    assert properties["Day"]["title"][0]["text"]["content"] == "2026-04-03"
    assert properties["Trade Count"]["number"] == 1.0
    assert properties["Daily Result"]["select"]["name"] == "Win"
    assert children[-1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "2026-04-03 MNQ Short 09:42"
