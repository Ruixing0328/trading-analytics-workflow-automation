"""Trade entry domain models and validation."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .constants import DEFAULT_TIMEZONE
from .exceptions import TradeJournalValidationError


class Instrument(str, Enum):
    MNQ = "MNQ"
    MES = "MES"


class Direction(str, Enum):
    LONG = "Long"
    SHORT = "Short"


class AccountType(str, Enum):
    FUNDED = "Funded"
    EVAL = "Eval"
    BACKTEST = "Backtest"
    PAPERTRADE = "Papertrade"


class TradeWindow(str, Enum):
    PRE_1000 = "Pre-10:00"
    FROM_1000_TO_1030 = "10:00-10:30"
    FROM_1030_TO_1100 = "10:30-11:00"


class Result(str, Enum):
    WIN = "Win"
    LOSS = "Loss"
    BREAKEVEN = "Breakeven"


class Bias(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class HtfFvgTimeframe(str, Enum):
    TF_5M = "5M"
    TF_15M = "15M"
    TF_1H = "1H"
    TF_4H = "4H"
    NONE = "None"


class TargetDraw(str, Enum):
    OPPOSING_1H_HIGH = "Opposing 1H High"
    OPPOSING_1H_LOW = "Opposing 1H Low"
    OPPOSING_4H_HIGH = "Opposing 4H High"
    OPPOSING_4H_LOW = "Opposing 4H Low"
    LRL_BELOW = "LRL Below"
    LRL_ABOVE_AND_1H_HIGHS = "LRL Above / 1H Highs"
    NEGATIVE_2_STANDARD_DEVIATION = "-2 Standard Deviation"
    ONE_TO_ONE_NO_CLEAR_DOL_BELOW = "1:1 / No Clear DOL Below"
    FIVE_M_GAP_HTF_CONTINUATION = "5M Gap / Higher-Timeframe Continuation"
    ALL_TIME_HIGHS_AND_4H_HIGHS = "All Time Highs / 4H Highs"
    FOUR_H_HIGHS_AND_NWOG = "4H Highs and NWOG"
    OTHER = "Other"


class LtfTriggerTimeframe(str, Enum):
    TF_30S = "30S"
    TF_1M = "1M"
    TF_2M = "2M"
    TF_3M = "3M"
    TF_5M = "5M"
    NONE = "None"


class SetupGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"


class RuleBreakSeverity(str, Enum):
    NONE = "None"
    MINOR = "Minor"
    MODERATE = "Moderate"
    MAJOR = "Major"
    HIGH = "High"


class BETiming(str, Enum):
    PROPER = "Proper"
    TOO_EARLY = "Too Early"
    TOO_LATE = "Too Late"
    IMPROPER = "Improper"
    MISSED = "Missed"
    NOT_USED = "Not Used"


class ExitQuality(str, Enum):
    GOOD = "Good"
    OKAY = "Okay"
    POOR = "Poor"


class EmotionalState(str, Enum):
    CALM = "Calm"
    SLIGHTLY_EMOTIONAL = "Slightly Emotional"
    FRUSTRATED = "Frustrated"
    FOMO = "FOMO"
    GREEDY = "Greedy"
    REVENGE = "Revenge"
    TIRED = "Tired"


BOOLEAN_FIELDS = frozenset(
    {
        "moved_to_be",
        "partials_taken",
        "htf_bias_aligned",
        "htf_fvg_respected",
        "itm_sweep_occurred",
        "sweep_inside_gap",
        "inverse_fvg_formed",
        "inverse_fvg_clean",
        "market_structure_flip_present",
        "a_plus_setup",
        "suboptimal_conditions",
        "forced_trade",
        "doubled_down",
        "overtraded",
        "size_appropriate",
        "stop_placement_valid",
        "target_placement_valid",
        "hesitated",
        "chased",
    }
)
FLOAT_FIELDS = frozenset(
    {
        "entry_price",
        "exit_price",
        "stop_price",
        "target_price",
        "contracts",
        "hold_minutes",
        "pnl",
        "realized_r",
        "planned_r",
    }
)
INTEGER_FIELDS = frozenset({"confidence", "clarity", "patience"})
EASTERN_TIMEZONE = ZoneInfo(DEFAULT_TIMEZONE)


def normalize_lookup_key(value: str) -> str:
    """Create a lenient lookup key for case-insensitive enum normalization."""

    return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())


def build_enum_alias_map(enum_cls: type[Enum], *extra_aliases: tuple[str, str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for member in enum_cls:
        aliases[normalize_lookup_key(str(member.value))] = str(member.value)
    for alias, canonical in extra_aliases:
        aliases[normalize_lookup_key(alias)] = canonical
    return aliases


ENUM_NORMALIZERS = {
    "instrument": build_enum_alias_map(Instrument),
    "direction": build_enum_alias_map(Direction),
    "account_type": build_enum_alias_map(
        AccountType,
        ("backtesting", "Backtest"),
        ("paper trade", "Papertrade"),
        ("papertrading", "Papertrade"),
    ),
    "trade_window": build_enum_alias_map(TradeWindow),
    "result": build_enum_alias_map(
        Result,
        ("be", "Breakeven"),
        ("break-even", "Breakeven"),
        ("break even", "Breakeven"),
    ),
    "bias_4h": build_enum_alias_map(Bias),
    "bias_1h": build_enum_alias_map(Bias),
    "htf_fvg_timeframe": build_enum_alias_map(HtfFvgTimeframe),
    "target_draw": build_enum_alias_map(
        TargetDraw,
        ("4h highs", "Opposing 4H High"),
        ("4h high", "Opposing 4H High"),
        ("4h lows", "Opposing 4H Low"),
        ("4h low", "Opposing 4H Low"),
        ("1h highs", "Opposing 1H High"),
        ("1h high", "Opposing 1H High"),
        ("1h lows", "Opposing 1H Low"),
        ("1h low", "Opposing 1H Low"),
        ("lrl above, 1h highs", "LRL Above / 1H Highs"),
        ("generated lrl above / 1h highs", "LRL Above / 1H Highs"),
    ),
    "ltf_trigger_timeframe": build_enum_alias_map(LtfTriggerTimeframe),
    "setup_grade": build_enum_alias_map(SetupGrade),
    "rule_break_severity": build_enum_alias_map(
        RuleBreakSeverity,
        ("low", "Minor"),
    ),
    "be_timing": build_enum_alias_map(
        BETiming,
        ("early", "Too Early"),
        ("late", "Too Late"),
    ),
    "exit_quality": build_enum_alias_map(ExitQuality),
    "emotional_state": build_enum_alias_map(EmotionalState),
}


def normalize_boolean_value(field_name: str, value: Any) -> Any:
    """Normalize supported boolean variants into real booleans."""

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, float) and value in {0.0, 1.0}:
        return bool(int(value))
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    raise ValueError(
        f"{field_name} must be a boolean or one of: true/false, yes/no, 1/0."
    )


def parse_decimal(field_name: str, value: Any) -> Decimal:
    """Parse a numeric payload value while rejecting formatted text."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric, not a boolean.")
    if isinstance(value, (int, float)):
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            raise ValueError(f"{field_name} must be a finite number.")
        return parsed
    if isinstance(value, str):
        cleaned = value.strip()
        if "$" in cleaned or "," in cleaned:
            raise ValueError(f"{field_name} must not include dollar signs or commas.")
        try:
            parsed = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} must be numeric.") from exc
        if not parsed.is_finite():
            raise ValueError(f"{field_name} must be a finite number.")
        return parsed
    raise ValueError(f"{field_name} must be numeric.")


def normalize_numeric_value(field_name: str, value: Any, *, integer: bool) -> int | float | None:
    """Normalize numeric strings into Python numbers."""

    if value is None:
        return None

    parsed = parse_decimal(field_name, value)
    if integer:
        if parsed != parsed.to_integral_value():
            raise ValueError(f"{field_name} must be an integer.")
        return int(parsed)
    return float(parsed)


def normalize_enum_value(field_name: str, value: Any) -> Any:
    """Normalize enum inputs with case-insensitive matching and common aliases."""

    if value is None or not isinstance(value, str):
        return value
    aliases = ENUM_NORMALIZERS.get(field_name)
    if not aliases:
        return value
    normalized = aliases.get(normalize_lookup_key(value))
    if normalized is not None:
        return normalized
    if field_name == "target_draw":
        return "Other"
    return value


def normalize_trade_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize loose JSON/CSV input into the canonical trade payload format."""

    normalized: dict[str, Any] = {}
    for key, value in raw_payload.items():
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                normalized[key] = None
                continue
            value = stripped

        if key == "trade_window" and isinstance(value, str) and normalize_lookup_key(value) in {
            "late morning",
            "ny open",
            "new york open",
        }:
            normalized[key] = None
            continue
        if key in BOOLEAN_FIELDS:
            normalized[key] = normalize_boolean_value(key, value)
            continue
        if key in INTEGER_FIELDS:
            normalized[key] = normalize_numeric_value(key, value, integer=True)
            continue
        if key in FLOAT_FIELDS:
            normalized[key] = normalize_numeric_value(key, value, integer=False)
            continue
        if key in ENUM_NORMALIZERS:
            normalized[key] = normalize_enum_value(key, value)
            continue
        normalized[key] = value

    return normalized


class TradeEntry(BaseModel):
    """Validated trade entry that maps one-to-one into the Notion journal."""

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    trade_name: Optional[str] = None
    date: date
    instrument: Instrument
    direction: Direction
    account_type: Optional[AccountType] = None
    account_label: Optional[str] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    trade_window: Optional[TradeWindow] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    contracts: Optional[float] = None
    hold_minutes: Optional[float] = None
    result: Optional[Result] = None
    pnl: Optional[float] = None
    realized_r: Optional[float] = None
    planned_r: Optional[float] = None
    moved_to_be: Optional[bool] = None
    partials_taken: Optional[bool] = None
    bias_4h: Optional[Bias] = None
    bias_1h: Optional[Bias] = None
    htf_bias_aligned: Optional[bool] = None
    htf_fvg_timeframe: Optional[HtfFvgTimeframe] = None
    htf_fvg_respected: Optional[bool] = None
    itm_sweep_occurred: Optional[bool] = None
    sweep_inside_gap: Optional[bool] = None
    target_draw: Optional[TargetDraw] = None
    ltf_trigger_timeframe: Optional[LtfTriggerTimeframe] = None
    inverse_fvg_formed: Optional[bool] = None
    inverse_fvg_clean: Optional[bool] = None
    market_structure_flip_present: Optional[bool] = None
    a_plus_setup: Optional[bool] = None
    setup_grade: Optional[SetupGrade] = None
    suboptimal_conditions: Optional[bool] = None
    forced_trade: Optional[bool] = None
    doubled_down: Optional[bool] = None
    overtraded: Optional[bool] = None
    size_appropriate: Optional[bool] = None
    rule_break_severity: Optional[RuleBreakSeverity] = None
    stop_placement_valid: Optional[bool] = None
    target_placement_valid: Optional[bool] = None
    be_timing: Optional[BETiming] = None
    exit_quality: Optional[ExitQuality] = None
    confidence: Optional[int] = None
    clarity: Optional[int] = None
    patience: Optional[int] = None
    emotional_state: Optional[EmotionalState] = None
    hesitated: Optional[bool] = None
    chased: Optional[bool] = None
    entry_rationale: Optional[str] = None
    what_went_well: Optional[str] = None
    what_went_wrong: Optional[str] = None
    lesson: Optional[str] = None
    next_time_rule: Optional[str] = None
    coach_feedback: Optional[str] = None
    screenshot_path: Optional[str] = None
    screenshot_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_payload(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return normalize_trade_payload(value)
        return value

    @field_validator("entry_time", "exit_time")
    @classmethod
    def ensure_timezone_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Datetime values must include timezone information.")
        return value

    @field_validator("confidence", "clarity", "patience")
    @classmethod
    def validate_rating(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not 1 <= value <= 5:
            raise ValueError("Ratings must be between 1 and 5.")
        return value

    @model_validator(mode="after")
    def derive_missing_fields(self) -> "TradeEntry":
        if self.screenshot_path and self.screenshot_url:
            raise ValueError("Use either screenshot_path or screenshot_url, not both.")

        if self.exit_time and self.entry_time and self.exit_time < self.entry_time:
            raise ValueError("exit_time cannot be earlier than entry_time.")

        if self.result == Result.WIN and self.pnl is not None and self.pnl <= 0:
            raise ValueError("Win trades must have pnl greater than 0.")
        if self.result == Result.LOSS and self.pnl is not None and self.pnl >= 0:
            raise ValueError("Loss trades must have pnl less than 0.")
        if self.hold_minutes is None and self.exit_time and self.entry_time:
            duration_seconds = (self.exit_time - self.entry_time).total_seconds()
            self.hold_minutes = float(max(int(duration_seconds // 60), 0))

        if self.trade_window is None and self.entry_time is not None:
            self.trade_window = derive_trade_window(self.entry_time)

        if self.htf_bias_aligned is None and self.bias_4h and self.bias_1h:
            self.htf_bias_aligned = self.bias_4h == self.bias_1h

        if not self.trade_name:
            self.trade_name = generate_trade_name(
                trade_date=self.date,
                instrument=self.instrument,
                direction=self.direction,
                entry_time=self.entry_time,
            )

        return self


def derive_trade_window(entry_time: datetime) -> TradeWindow:
    """Infer the trading window bucket from the entry timestamp."""

    eastern_entry_time = entry_time.astimezone(EASTERN_TIMEZONE)
    minute_of_day = eastern_entry_time.hour * 60 + eastern_entry_time.minute
    ten_am = 10 * 60
    ten_thirty = 10 * 60 + 30
    eleven_am = 11 * 60

    if minute_of_day < ten_am:
        return TradeWindow.PRE_1000
    if minute_of_day < ten_thirty:
        return TradeWindow.FROM_1000_TO_1030
    if minute_of_day < eleven_am:
        return TradeWindow.FROM_1030_TO_1100
    return TradeWindow.FROM_1030_TO_1100


def generate_trade_name(
    trade_date: date,
    instrument: Union[Instrument, str],
    direction: Union[Direction, str],
    entry_time: Optional[datetime],
) -> str:
    """Generate a readable trade title from the core identifying fields."""

    instrument_value = instrument.value if isinstance(instrument, Instrument) else instrument
    direction_value = direction.value if isinstance(direction, Direction) else direction
    if entry_time is None:
        return f"{trade_date.isoformat()} {instrument_value} {direction_value}"
    timestamp_label = entry_time.astimezone(EASTERN_TIMEZONE).strftime("%H:%M")
    return f"{trade_date.isoformat()} {instrument_value} {direction_value} {timestamp_label}"


def load_trade_entry(payload: Dict[str, Any], base_path: Optional[Path] = None) -> TradeEntry:
    """Normalize and validate a raw trade payload."""

    normalized = dict(payload)
    screenshot_path = normalized.get("screenshot_path")
    if screenshot_path and base_path:
        resolved_path = Path(screenshot_path)
        if not resolved_path.is_absolute():
            normalized["screenshot_path"] = str((base_path / resolved_path).resolve())

    try:
        return TradeEntry.model_validate(normalized)
    except Exception as exc:  # pragma: no cover - pydantic exception formatting varies
        raise TradeJournalValidationError(str(exc)) from exc


def load_trade_entry_from_json(json_path: Union[str, Path]) -> TradeEntry:
    """Load and validate a trade entry from a JSON file."""

    path = Path(json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TradeJournalValidationError("Trade payload JSON must be a single JSON object.")
    return load_trade_entry(payload, base_path=path.parent)
