"""Filtering and decision-support metrics for the public dashboard."""

from __future__ import annotations

from calendar import month_name
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Iterable

WEEKDAY_ORDER = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FILTER_FIELDS = ("instrument", "account_type", "setup_grade", "result")
SCORECARD_LIMITS = {"weekly": 8, "monthly": 6}
FLAG_FIELDS = (
    ("forced_trade", "Forced trade"),
    ("overtraded", "Overtraded"),
    ("doubled_down", "Doubled down"),
    ("chased", "Chased"),
    ("hesitated", "Hesitated"),
    ("suboptimal_conditions", "Suboptimal conditions"),
)
BOOLEAN_FIELDS = {
    "forced_trade", "overtraded", "doubled_down", "chased", "hesitated",
    "suboptimal_conditions", "moved_to_be", "partials_taken",
    "size_appropriate", "stop_placement_valid", "target_placement_valid",
}


@dataclass(frozen=True)
class DashboardFilters:
    """Active dashboard filters coming from the UI query string."""

    start_date: str | None = None
    end_date: str | None = None
    instrument: str | None = None
    account_type: str | None = None
    setup_grade: str | None = None
    result: str | None = None


def parse_iso_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    return date.fromisoformat(str(value)[:10])


def parse_iso_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


def to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def to_bool(value: Any) -> bool | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return value
    if value in {0, 0.0, "0", "false", "False", "no", "No"}:
        return False
    if value in {1, 1.0, "1", "true", "True", "yes", "Yes"}:
        return True
    return None


def normalize_trade_row(row: dict[str, Any]) -> dict[str, Any]:
    """Attach typed helpers without mutating the source row."""

    normalized = dict(row)
    normalized["trade_date_obj"] = parse_iso_date(row.get("trade_date"))
    normalized["entry_time_obj"] = parse_iso_datetime(row.get("entry_time"))
    normalized["pnl_value"] = to_float(row.get("pnl")) or 0.0
    normalized["realized_r_value"] = to_float(row.get("realized_r"))
    normalized["hold_minutes_value"] = to_int(row.get("hold_minutes"))
    for field in BOOLEAN_FIELDS:
        normalized[field] = to_bool(row.get(field))
    return normalized


def available_filter_values(trades: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    source = list(trades)
    return {
        field: sorted({str(row[field]) for row in source if row.get(field) not in {None, ""}})
        for field in FILTER_FIELDS
    }


def apply_filters(trades: list[dict[str, Any]], filters: DashboardFilters) -> list[dict[str, Any]]:
    start = parse_iso_date(filters.start_date)
    end = parse_iso_date(filters.end_date)
    filtered: list[dict[str, Any]] = []
    for trade in trades:
        trade_date = trade.get("trade_date_obj")
        if start and trade_date and trade_date < start:
            continue
        if end and trade_date and trade_date > end:
            continue
        if filters.instrument and trade.get("instrument") != filters.instrument:
            continue
        if filters.account_type and trade.get("account_type") != filters.account_type:
            continue
        if filters.setup_grade and trade.get("setup_grade") != filters.setup_grade:
            continue
        if filters.result and trade.get("result") != filters.result:
            continue
        filtered.append(trade)
    return filtered


def sort_trades_desc(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        trades,
        key=lambda row: (row.get("trade_date_obj") or date.min, row.get("entry_time") or ""),
        reverse=True,
    )


def compute_win_rate(wins: int, losses: int) -> float | None:
    """Use decisive outcomes only so breakeven records remain neutral."""

    decisive = wins + losses
    return None if decisive == 0 else (wins / decisive) * 100


def group_metrics(
    trades: Iterable[dict[str, Any]],
    *,
    field: str,
    fallback_label: str = "Unspecified",
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for trade in trades:
        label = str(trade.get(field) or fallback_label)
        bucket = grouped.setdefault(
            label,
            {"label": label, "count": 0, "wins": 0, "losses": 0, "breakevens": 0, "pnl": 0.0},
        )
        bucket["count"] += 1
        bucket["pnl"] += trade["pnl_value"]
        result = trade.get("result")
        if result == "Win":
            bucket["wins"] += 1
        elif result == "Loss":
            bucket["losses"] += 1
        elif result == "Breakeven":
            bucket["breakevens"] += 1
    output: list[dict[str, Any]] = []
    for bucket in grouped.values():
        bucket["avg_pnl"] = bucket["pnl"] / bucket["count"]
        bucket["win_rate"] = compute_win_rate(bucket["wins"], bucket["losses"])
        output.append(bucket)
    return sorted(output, key=lambda row: (row["pnl"], row["count"]), reverse=True)


def build_equity_curve(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for trade in trades:
        trade_date = trade.get("trade_date_obj")
        if trade_date is None:
            continue
        key = trade_date.isoformat()
        bucket = grouped.setdefault(key, {"date": key, "daily_pnl": 0.0, "count": 0})
        bucket["daily_pnl"] += trade["pnl_value"]
        bucket["count"] += 1
    cumulative = 0.0
    curve: list[dict[str, Any]] = []
    for key in sorted(grouped):
        cumulative += grouped[key]["daily_pnl"]
        curve.append({**grouped[key], "cumulative_pnl": cumulative})
    return curve


def build_weekday_performance(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = {day: {"label": day, "count": 0, "pnl": 0.0} for day in WEEKDAY_ORDER}
    for trade in trades:
        trade_date = trade.get("trade_date_obj")
        if trade_date is None:
            continue
        bucket = grouped[WEEKDAY_ORDER[trade_date.weekday()]]
        bucket["count"] += 1
        bucket["pnl"] += trade["pnl_value"]
    return [
        {**grouped[day], "avg_pnl": grouped[day]["pnl"] / grouped[day]["count"]}
        for day in WEEKDAY_ORDER
        if grouped[day]["count"]
    ]


def build_flag_performance(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample_size = len(trades) or 1
    for field, label in FLAG_FIELDS:
        flagged = [trade for trade in trades if trade.get(field) is True]
        if not flagged:
            continue
        pnl = sum(trade["pnl_value"] for trade in flagged)
        wins = sum(trade.get("result") == "Win" for trade in flagged)
        losses = sum(trade.get("result") == "Loss" for trade in flagged)
        rows.append(
            {
                "label": label,
                "count": len(flagged),
                "share_of_sample": (len(flagged) / sample_size) * 100,
                "pnl": pnl,
                "avg_pnl": pnl / len(flagged),
                "win_rate": compute_win_rate(wins, losses),
            }
        )
    return sorted(rows, key=lambda row: row["pnl"])


def summarize_sample(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "total_trades": 0, "total_pnl": 0.0, "avg_trade": 0.0, "win_rate": None,
            "profit_factor": None, "average_r": None, "average_hold_minutes": None,
            "best_trade": None, "worst_trade": None, "gross_profit": 0.0,
            "gross_loss": 0.0, "known_trade_count": 0,
            "aggregate_only_trade_count": 0, "aggregate_only_day_count": 0,
            "aggregate_only_pnl": 0.0,
        }
    pnls = [trade["pnl_value"] for trade in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    realized_rs = [trade["realized_r_value"] for trade in trades if trade["realized_r_value"] is not None]
    hold_minutes = [trade["hold_minutes_value"] for trade in trades if trade["hold_minutes_value"] is not None]
    wins_count = sum(trade.get("result") == "Win" for trade in trades)
    losses_count = sum(trade.get("result") == "Loss" for trade in trades)
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    return {
        "total_trades": len(trades),
        "total_pnl": sum(pnls),
        "avg_trade": sum(pnls) / len(trades),
        "win_rate": compute_win_rate(wins_count, losses_count),
        "profit_factor": (gross_profit / abs(gross_loss)) if gross_loss else None,
        "average_r": mean(realized_rs) if realized_rs else None,
        "average_hold_minutes": mean(hold_minutes) if hold_minutes else None,
        "best_trade": max(pnls),
        "worst_trade": min(pnls),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "known_trade_count": len(trades),
        "aggregate_only_trade_count": 0,
        "aggregate_only_day_count": 0,
        "aggregate_only_pnl": 0.0,
    }


def build_streaks(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "current": {"type": None, "count": 0, "label": "No trades yet"},
            "max_win_streak": 0,
            "max_loss_streak": 0,
        }
    ordered = list(reversed(sort_trades_desc(trades)))
    running_type: str | None = None
    running_count = 0
    max_win = 0
    max_loss = 0
    for trade in ordered:
        result = trade.get("result")
        if result == running_type:
            running_count += 1
        else:
            running_type = result
            running_count = 1
        if result == "Win":
            max_win = max(max_win, running_count)
        elif result == "Loss":
            max_loss = max(max_loss, running_count)
    word = "trade" if running_count == 1 else "streak"
    return {
        "current": {
            "type": running_type,
            "count": running_count,
            "label": f"{running_count} {str(running_type).lower()} {word}",
        },
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
    }


def month_end_for(month_start: date) -> date:
    if month_start.month == 12:
        return month_start.replace(day=31)
    return month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)


def format_month_day(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"


def build_period_scorecards(trades: list[dict[str, Any]], *, period: str) -> list[dict[str, Any]]:
    if period not in SCORECARD_LIMITS:
        raise ValueError(f"Unsupported scorecard period: {period}")
    grouped: dict[date, list[dict[str, Any]]] = {}
    for trade in trades:
        trade_date = trade.get("trade_date_obj")
        if trade_date is None:
            continue
        period_start = (
            trade_date - timedelta(days=trade_date.weekday())
            if period == "weekly"
            else trade_date.replace(day=1)
        )
        grouped.setdefault(period_start, []).append(trade)
    output: list[dict[str, Any]] = []
    for period_start in sorted(grouped, reverse=True)[: SCORECARD_LIMITS[period]]:
        period_trades = grouped[period_start]
        period_end = period_start + timedelta(days=6) if period == "weekly" else month_end_for(period_start)
        summary = summarize_sample(period_trades)
        daily: dict[date, float] = {}
        for trade in period_trades:
            trade_date = trade["trade_date_obj"]
            daily[trade_date] = daily.get(trade_date, 0.0) + trade["pnl_value"]
        best_day = max(daily.items(), key=lambda item: item[1], default=None)
        top_instrument = group_metrics(period_trades, field="instrument")[:1]
        top_setup = group_metrics(period_trades, field="setup_grade")[:1]
        title = (
            f"Week of {format_month_day(period_start)}"
            if period == "weekly"
            else f"{month_name[period_start.month]} {period_start.year}"
        )
        output.append(
            {
                "period": period,
                "period_key": period_start.isoformat(),
                "title": title,
                "subtitle": f"{format_month_day(period_start)} - {format_month_day(period_end)}",
                "start_date": period_start.isoformat(),
                "end_date": period_end.isoformat(),
                "total_trades": len(period_trades),
                "trading_days": len(daily),
                "wins": sum(row.get("result") == "Win" for row in period_trades),
                "losses": sum(row.get("result") == "Loss" for row in period_trades),
                "breakevens": sum(row.get("result") == "Breakeven" for row in period_trades),
                "green_days": sum(value > 0 for value in daily.values()),
                "red_days": sum(value < 0 for value in daily.values()),
                "flat_days": sum(value == 0 for value in daily.values()),
                **{key: summary[key] for key in (
                    "total_pnl", "avg_trade", "win_rate", "profit_factor",
                    "average_r", "best_trade", "worst_trade",
                )},
                "best_day_label": format_month_day(best_day[0]) if best_day else None,
                "best_day_pnl": best_day[1] if best_day else None,
                "top_instrument": top_instrument[0]["label"] if top_instrument else None,
                "top_instrument_pnl": top_instrument[0]["pnl"] if top_instrument else None,
                "top_setup_grade": top_setup[0]["label"] if top_setup else None,
                "top_setup_grade_pnl": top_setup[0]["pnl"] if top_setup else None,
                "aggregate_only_trade_count": 0,
                "aggregate_only_day_count": 0,
                "aggregate_only_pnl": 0.0,
                "aggregate_only_dates": [],
            }
        )
    return output


def build_highlights(
    by_instrument: list[dict[str, Any]],
    by_trade_window: list[dict[str, Any]],
    flag_performance: list[dict[str, Any]],
) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    if by_instrument:
        best = by_instrument[0]
        rate = "—" if best["win_rate"] is None else f"{best['win_rate']:.1f}%"
        highlights.append({
            "title": "Best instrument", "value": best["label"],
            "detail": f"{best['count']} records, {rate} win rate, USD {best['pnl']:.2f}",
        })
    if by_trade_window:
        best = by_trade_window[0]
        highlights.append({
            "title": "Strongest window", "value": best["label"],
            "detail": f"{best['count']} records, USD {best['avg_pnl']:.2f} average",
        })
    if flag_performance:
        leak = min(flag_performance, key=lambda row: row["pnl"])
        highlights.append({
            "title": "Process flag", "value": leak["label"],
            "detail": f"{leak['count']} records flagged, USD {leak['pnl']:.2f} total",
        })
    return highlights[:3]


def build_recent_trades(trades: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    fields = (
        "trade_name", "trade_date", "instrument", "direction", "result",
        "setup_grade", "trade_window", "emotional_state",
    )
    output: list[dict[str, Any]] = []
    for trade in sort_trades_desc(trades)[:limit]:
        row = {field: trade.get(field) for field in fields}
        row["pnl"] = trade["pnl_value"]
        output.append(row)
    return output


def build_dashboard_payload(raw_rows: list[dict[str, Any]], filters: DashboardFilters) -> dict[str, Any]:
    """Build the complete JSON payload consumed by the frontend."""

    normalized = [normalize_trade_row(row) for row in raw_rows]
    filtered = apply_filters(normalized, filters)
    by_instrument = group_metrics(filtered, field="instrument")
    by_trade_window = group_metrics(filtered, field="trade_window")
    by_setup_grade = group_metrics(filtered, field="setup_grade")
    by_emotional_state = group_metrics(filtered, field="emotional_state")
    flag_performance = build_flag_performance(filtered)
    empty_adjustments = {"day_count": 0, "trade_count": 0, "total_pnl": 0.0, "dates": []}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filters": {
            "active": {
                "start_date": filters.start_date,
                "end_date": filters.end_date,
                "instrument": filters.instrument,
                "account_type": filters.account_type,
                "setup_grade": filters.setup_grade,
                "result": filters.result,
            },
            "available": available_filter_values(normalized),
            "result_count": len(filtered),
            "source_count": len(normalized),
            "known_result_count": len(filtered),
            "known_source_count": len(normalized),
        },
        "summary": {**summarize_sample(filtered), **build_streaks(filtered)},
        "highlights": build_highlights(by_instrument, by_trade_window, flag_performance),
        "scorecards": {
            "weekly": build_period_scorecards(filtered, period="weekly"),
            "monthly": build_period_scorecards(filtered, period="monthly"),
        },
        "charts": {
            "equity_curve": build_equity_curve(filtered),
            "by_instrument": by_instrument,
            "by_trade_window": by_trade_window,
            "by_setup_grade": by_setup_grade,
            "by_emotional_state": by_emotional_state,
            "weekday_performance": build_weekday_performance(filtered),
            "discipline_flags": flag_performance,
        },
        "recent_trades": build_recent_trades(filtered),
        "aggregate_adjustments": {"filtered": empty_adjustments, "source": empty_adjustments},
    }
