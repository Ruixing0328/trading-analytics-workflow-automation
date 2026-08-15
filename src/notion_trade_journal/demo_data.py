"""Deterministic, public-safe data for the portfolio dashboard."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .constants import DEFAULT_TIMEZONE

EASTERN = ZoneInfo(DEFAULT_TIMEZONE)
WINDOWS = ("Pre-10:00", "10:00-10:30", "10:30-11:00")
GRADES = ("A+", "A", "B", "C")
EMOTIONS = ("Calm", "Slightly Emotional", "Frustrated", "FOMO", "Tired")

# Twenty-four synthetic sessions with two records per session. The paired
# sequences intentionally finish near flat and include both positive and
# negative periods; they are demonstration inputs, not investment results.
PRIMARY_PNL = (
    80.0, -65.0, 55.0, -70.0, 0.0, 45.0, -60.0, 75.0,
    -85.0, 50.0, -40.0, 0.0, 65.0, -55.0, 40.0, -75.0,
    70.0, -50.0, 0.0, 60.0, -45.0, 35.0, -65.0, 50.0,
)
SECONDARY_PNL = (
    -70.0, 60.0, -50.0, 65.0, 35.0, -45.0, 55.0, -60.0,
    75.0, -40.0, 0.0, -55.0, 45.0, -65.0, 50.0, -35.0,
    60.0, -70.0, 40.0, 0.0, -50.0, 65.0, -45.0, 55.0,
)


def iso_with_tz(day: date, hour: int, minute: int) -> str:
    """Build an ISO timestamp in the configured trading timezone."""

    return datetime.combine(day, time(hour, minute), tzinfo=EASTERN).isoformat()


def result_for(pnl: float) -> str:
    """Map a synthetic P&L value to the journal's result vocabulary."""

    if pnl > 0:
        return "Win"
    if pnl < 0:
        return "Loss"
    return "Breakeven"


def demo_session_dates() -> list[date]:
    """Return three synthetic review sessions per week for eight weeks."""

    sessions: list[date] = []
    current = date(2026, 1, 5)
    while len(sessions) < 24:
        if current.weekday() in {0, 2, 4}:
            sessions.append(current)
        current += timedelta(days=1)
    return sessions


def build_demo_trade_rows() -> list[dict]:
    """Create 48 public-safe rows that exercise the real dashboard schema."""

    rows: list[dict] = []
    for session_index, day in enumerate(demo_session_dates()):
        for position, pnl in enumerate((PRIMARY_PNL[session_index], SECONDARY_PNL[session_index])):
            row_index = session_index * 2 + position
            instrument = "MNQ" if row_index % 3 else "MES"
            direction = "Long" if row_index % 2 == 0 else "Short"
            window = WINDOWS[row_index % len(WINDOWS)]
            entry_hour = 9 if window == "Pre-10:00" else 10
            entry_minute = 38 + (row_index % 10) if entry_hour == 9 else 5 + ((row_index * 7) % 50)
            result = result_for(pnl)
            risk_unit = 70.0 + ((row_index % 4) * 5.0)

            rows.append(
                {
                    "notion_page_id": f"demo-trade-{row_index + 1:03d}",
                    "notion_page_url": None,
                    "trade_name": f"Demo record {row_index + 1:03d}",
                    "trade_date": day.isoformat(),
                    "entry_time": iso_with_tz(day, entry_hour, entry_minute),
                    "instrument": instrument,
                    "direction": direction,
                    "account_type": "Papertrade" if row_index % 2 == 0 else "Backtest",
                    "account_label": None,
                    "setup_grade": GRADES[row_index % len(GRADES)],
                    "trade_window": window,
                    "result": result,
                    "pnl": pnl,
                    "realized_r": 0.0 if pnl == 0 else round(pnl / risk_unit, 2),
                    "planned_r": 1.5 + ((row_index % 3) * 0.5),
                    "hold_minutes": 7 + (row_index % 19),
                    "moved_to_be": row_index % 4 == 0,
                    "partials_taken": row_index % 5 == 0,
                    "size_appropriate": row_index % 9 != 0,
                    "stop_placement_valid": row_index % 8 != 0,
                    "target_placement_valid": row_index % 7 != 0,
                    "be_timing": "Proper" if row_index % 5 else "Too Early",
                    "exit_quality": ("Good", "Okay", "Poor")[row_index % 3],
                    "confidence": 3 + (row_index % 3),
                    "clarity": 3 + ((row_index + 1) % 3),
                    "patience": 3 + ((row_index + 2) % 3),
                    "emotional_state": EMOTIONS[row_index % len(EMOTIONS)],
                    "bias_4h": "Bullish" if direction == "Long" else "Bearish",
                    "bias_1h": "Bullish" if row_index % 4 else "Neutral",
                    "htf_bias_aligned": row_index % 4 != 0,
                    "htf_fvg_timeframe": ("5M", "15M", "1H", "4H")[row_index % 4],
                    "target_draw": "Other",
                    "ltf_trigger_timeframe": ("30S", "1M", "2M", "3M")[row_index % 4],
                    "inverse_fvg_formed": row_index % 3 != 0,
                    "inverse_fvg_clean": row_index % 4 != 0,
                    "market_structure_flip_present": row_index % 5 != 0,
                    "forced_trade": row_index % 11 == 0,
                    "overtraded": row_index % 13 == 0,
                    "doubled_down": row_index % 17 == 0,
                    "chased": row_index % 7 == 0,
                    "hesitated": row_index % 6 == 0,
                    "suboptimal_conditions": row_index % 8 == 0,
                    "screenshot_url": None,
                }
            )

    return rows
