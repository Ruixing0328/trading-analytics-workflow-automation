from __future__ import annotations

from pathlib import Path

import pytest

from notion_trade_journal.exceptions import TradeJournalValidationError
from notion_trade_journal.models import TradeEntry, TradeWindow, load_trade_entry


def test_trade_name_and_derived_fields_are_generated() -> None:
    trade = TradeEntry.model_validate(
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "exit_time": "2026-04-03T09:58:00-04:00",
            "result": "Win",
            "pnl": 47.0,
            "bias_4h": "Bearish",
            "bias_1h": "Bearish",
        }
    )

    assert trade.trade_name == "2026-04-03 MNQ Short 09:42"
    assert trade.hold_minutes == 16
    assert trade.trade_window == TradeWindow.PRE_1000
    assert trade.htf_bias_aligned is True


def test_missing_entry_time_keeps_time_derivatives_blank() -> None:
    trade = TradeEntry.model_validate(
        {
            "date": "2025-07-15",
            "instrument": "MNQ",
            "direction": "Short",
            "result": "Loss",
            "pnl": -10.0,
            "exit_time": "2025-07-15T10:05:00-04:00",
        }
    )

    assert trade.trade_name == "2025-07-15 MNQ Short"
    assert trade.entry_time is None
    assert trade.trade_window is None
    assert trade.hold_minutes is None


def test_timezone_aware_datetimes_are_required() -> None:
    with pytest.raises(TradeJournalValidationError):
        load_trade_entry(
            {
                "date": "2026-04-03",
                "instrument": "MNQ",
                "direction": "Short",
                "entry_time": "2026-04-03T09:42:00",
                "result": "Win",
                "pnl": 47.0,
            }
        )


def test_relative_screenshot_paths_are_resolved() -> None:
    base_path = Path("/tmp/trades")
    trade = load_trade_entry(
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Win",
            "pnl": 47.0,
            "screenshot_path": "./sample_trade.png",
        },
        base_path=base_path,
    )

    assert trade.screenshot_path == str((base_path / "sample_trade.png").resolve())


def test_archival_entries_can_omit_result_and_pnl() -> None:
    trade = load_trade_entry(
        {
            "date": "2025-07-15",
            "instrument": "MNQ",
            "direction": "Short",
        }
    )

    assert trade.result is None
    assert trade.pnl is None


def test_normalizes_common_boolean_numeric_and_enum_variants() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-03",
            "instrument": "mnq",
            "direction": "short",
            "account_type": "backtesting",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "break-even",
            "pnl": "0",
            "moved_to_be": "yes",
            "partials_taken": "0",
            "confidence": "4",
        }
    )

    assert trade.instrument == "MNQ"
    assert trade.direction == "Short"
    assert trade.account_type == "Backtest"
    assert trade.result == "Breakeven"
    assert trade.pnl == 0.0
    assert trade.moved_to_be is True
    assert trade.partials_taken is False
    assert trade.confidence == 4


def test_normalizes_live_journal_aliases_and_fractional_hold_minutes() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-10",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-10T09:42:21-04:00",
            "trade_window": "NY Open",
            "result": "Breakeven",
            "pnl": "2.5",
            "hold_minutes": "6.67",
            "target_draw": "LRL / Data Wick Highs / 4H Highs",
            "be_timing": "Early",
        }
    )

    assert trade.trade_window == "Pre-10:00"
    assert trade.hold_minutes == 6.67
    assert trade.target_draw == "Other"
    assert trade.be_timing == "Too Early"
    assert trade.result == "Breakeven"
    assert trade.pnl == 2.5


def test_normalizes_additional_live_journal_aliases() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-10",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-10T11:00:02-04:00",
            "trade_window": "Late Morning",
            "result": "Breakeven",
            "pnl": 3.0,
            "htf_fvg_timeframe": "5M",
            "target_draw": "4H Highs",
            "be_timing": "Proper",
        }
    )

    assert trade.trade_window == "10:30-11:00"
    assert trade.htf_fvg_timeframe == "5M"
    assert trade.target_draw == "Opposing 4H High"
    assert trade.be_timing == "Proper"


def test_late_morning_alias_uses_entry_time_bucket() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-14",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-14T10:11:00-04:00",
            "trade_window": "Late Morning",
            "target_draw": "-2 Standard Deviation",
            "result": "Win",
            "pnl": 91.5,
        }
    )

    assert trade.trade_window == "10:00-10:30"
    assert trade.target_draw == "-2 Standard Deviation"


def test_ny_open_alias_uses_entry_time_bucket() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-17",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-17T10:01:13-04:00",
            "trade_window": "NY Open",
            "result": "Loss",
            "pnl": -100.5,
        }
    )

    assert trade.trade_window == "10:00-10:30"


def test_normalizes_no_clear_dol_target_draw() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-16",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-16T10:20:00-04:00",
            "target_draw": "1:1 / no clear DOL below",
            "result": "Loss",
            "pnl": -282,
        }
    )

    assert trade.target_draw == "1:1 / No Clear DOL Below"


def test_normalizes_april_17_trade_options() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-17",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-17T09:50:06-04:00",
            "ltf_trigger_timeframe": "30S",
            "target_draw": "5M gap / higher-timeframe continuation",
            "rule_break_severity": "Moderate",
            "be_timing": "Improper",
            "emotional_state": "calm",
            "result": "Breakeven",
            "pnl": 2.5,
        }
    )

    assert trade.ltf_trigger_timeframe == "30S"
    assert trade.target_draw == "5M Gap / Higher-Timeframe Continuation"
    assert trade.rule_break_severity == "Moderate"
    assert trade.be_timing == "Improper"
    assert trade.emotional_state == "Calm"


def test_normalizes_april_20_trade_options() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-20",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-20T09:52:02-04:00",
            "target_draw": "4H highs and NWOG",
            "emotional_state": "Greedy",
            "result": "Loss",
            "pnl": -166,
        }
    )

    assert trade.target_draw == "4H Highs and NWOG"
    assert trade.emotional_state == "Greedy"


def test_normalizes_all_time_highs_target_draw() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-21",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-21T10:27:14-04:00",
            "target_draw": "All Time Highs / 4H Highs",
            "result": "Breakeven",
            "pnl": 0.5,
        }
    )

    assert trade.target_draw == "All Time Highs / 4H Highs"


def test_normalizes_april_22_trade_options() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-22",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-22T09:49:28-04:00",
            "target_draw": "LRL below",
            "be_timing": "Missed",
            "setup_grade": "C",
            "result": "Loss",
            "pnl": -211.5,
        }
    )

    assert trade.target_draw == "LRL Below"
    assert trade.be_timing == "Missed"
    assert trade.setup_grade == "C"


def test_normalizes_low_rule_break_severity_alias() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-24",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-24T10:10:05-04:00",
            "rule_break_severity": "Low",
            "result": "Loss",
            "pnl": -129.5,
        }
    )

    assert trade.rule_break_severity == "Minor"


def test_normalizes_lrl_above_target_draw_aliases() -> None:
    first_trade = load_trade_entry(
        {
            "date": "2026-04-27",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-27T09:40:18-04:00",
            "target_draw": "LRL Above, 1H highs",
            "result": "Loss",
            "pnl": -70.5,
        }
    )
    second_trade = load_trade_entry(
        {
            "date": "2026-04-27",
            "instrument": "MNQ",
            "direction": "Long",
            "entry_time": "2026-04-27T09:55:09-04:00",
            "target_draw": "Generated LRL Above / 1H highs",
            "result": "Loss",
            "pnl": -262.0,
        }
    )

    assert first_trade.target_draw == "LRL Above / 1H Highs"
    assert second_trade.target_draw == "LRL Above / 1H Highs"


def test_normalizes_papertrade_aliases() -> None:
    trade = load_trade_entry(
        {
            "date": "2025-07-15",
            "instrument": "MNQ",
            "direction": "Short",
            "account_type": "paper trade",
        }
    )

    assert trade.account_type == "Papertrade"


def test_result_and_pnl_sign_must_match() -> None:
    invalid_payloads = [
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Win",
            "pnl": -45,
        },
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Loss",
            "pnl": 12,
        },
    ]

    for payload in invalid_payloads:
        with pytest.raises(TradeJournalValidationError):
            load_trade_entry(payload)


def test_trade_window_uses_eastern_time() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-03",
            "instrument": "MES",
            "direction": "Long",
            "entry_time": "2026-04-03T13:15:00+00:00",
            "result": "Win",
            "pnl": 10,
        }
    )

    assert trade.trade_window == TradeWindow.PRE_1000


def test_empty_optional_strings_become_none() -> None:
    trade = load_trade_entry(
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Loss",
            "pnl": -50,
            "account_label": "   ",
            "entry_rationale": "",
        }
    )

    assert trade.account_label is None
    assert trade.entry_rationale is None
