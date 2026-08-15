"""Central schema definition for payload validation and Notion mapping."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import SCREENSHOT_PROPERTY_NAME


@dataclass(frozen=True)
class SelectOption:
    name: str
    color: str = "default"


@dataclass(frozen=True)
class PropertyDefinition:
    payload_key: str
    notion_name: str
    notion_type: str
    required: bool = False
    options: tuple[SelectOption, ...] = field(default_factory=tuple)
    number_format: str = "number"


TRADE_JOURNAL_PROPERTIES: tuple[PropertyDefinition, ...] = (
    PropertyDefinition("trade_name", "Trade Name", "title", required=True),
    PropertyDefinition("date", "Date", "date", required=True),
    PropertyDefinition(
        "instrument",
        "Instrument",
        "select",
        required=True,
        options=(SelectOption("MNQ", "blue"), SelectOption("MES", "green")),
    ),
    PropertyDefinition(
        "direction",
        "Direction",
        "select",
        required=True,
        options=(SelectOption("Long", "green"), SelectOption("Short", "red")),
    ),
    PropertyDefinition(
        "account_type",
        "Account Type",
        "select",
        options=(
            SelectOption("Funded", "blue"),
            SelectOption("Eval", "yellow"),
            SelectOption("Backtest", "gray"),
            SelectOption("Papertrade", "orange"),
        ),
    ),
    PropertyDefinition("account_label", "Account Label", "rich_text"),
    PropertyDefinition("entry_time", "Entry Time", "date"),
    PropertyDefinition("exit_time", "Exit Time", "date"),
    PropertyDefinition(
        "trade_window",
        "Trade Window",
        "select",
        options=(
            SelectOption("Pre-10:00", "blue"),
            SelectOption("10:00-10:30", "yellow"),
            SelectOption("10:30-11:00", "orange"),
        ),
    ),
    PropertyDefinition("entry_price", "Entry Price", "number"),
    PropertyDefinition("exit_price", "Exit Price", "number"),
    PropertyDefinition("stop_price", "Stop Price", "number"),
    PropertyDefinition("target_price", "Target Price", "number"),
    PropertyDefinition("contracts", "Contracts", "number"),
    PropertyDefinition("hold_minutes", "Hold Minutes", "number"),
    PropertyDefinition(
        "result",
        "Result",
        "select",
        options=(
            SelectOption("Win", "green"),
            SelectOption("Loss", "red"),
            SelectOption("Breakeven", "gray"),
        ),
    ),
    PropertyDefinition("pnl", "P&L $", "number", number_format="dollar"),
    PropertyDefinition("realized_r", "Realized R", "number"),
    PropertyDefinition("planned_r", "Planned R", "number"),
    PropertyDefinition("moved_to_be", "Moved to BE", "checkbox"),
    PropertyDefinition("partials_taken", "Partials Taken", "checkbox"),
    PropertyDefinition(
        "bias_4h",
        "4H Bias",
        "select",
        options=(
            SelectOption("Bullish", "green"),
            SelectOption("Bearish", "red"),
            SelectOption("Neutral", "gray"),
        ),
    ),
    PropertyDefinition(
        "bias_1h",
        "1H Bias",
        "select",
        options=(
            SelectOption("Bullish", "green"),
            SelectOption("Bearish", "red"),
            SelectOption("Neutral", "gray"),
        ),
    ),
    PropertyDefinition("htf_bias_aligned", "HTF Bias Aligned", "checkbox"),
    PropertyDefinition(
        "htf_fvg_timeframe",
        "HTF FVG Timeframe",
        "select",
        options=(
            SelectOption("5M", "blue"),
            SelectOption("15M", "yellow"),
            SelectOption("1H", "orange"),
            SelectOption("4H", "red"),
            SelectOption("None", "gray"),
        ),
    ),
    PropertyDefinition("htf_fvg_respected", "HTF FVG Respected", "checkbox"),
    PropertyDefinition("itm_sweep_occurred", "ITM Sweep Occurred", "checkbox"),
    PropertyDefinition("sweep_inside_gap", "Sweep Inside Gap", "checkbox"),
    PropertyDefinition(
        "target_draw",
        "Target Draw",
        "select",
        options=(
            SelectOption("Opposing 1H High", "yellow"),
            SelectOption("Opposing 1H Low", "yellow"),
            SelectOption("Opposing 4H High", "orange"),
            SelectOption("Opposing 4H Low", "orange"),
            SelectOption("LRL Below", "red"),
            SelectOption("LRL Above / 1H Highs", "yellow"),
            SelectOption("-2 Standard Deviation", "blue"),
            SelectOption("1:1 / No Clear DOL Below", "red"),
            SelectOption("5M Gap / Higher-Timeframe Continuation", "blue"),
            SelectOption("All Time Highs / 4H Highs", "green"),
            SelectOption("4H Highs and NWOG", "purple"),
            SelectOption("Other", "gray"),
        ),
    ),
    PropertyDefinition(
        "ltf_trigger_timeframe",
        "LTF Trigger Timeframe",
        "select",
        options=(
            SelectOption("30S", "purple"),
            SelectOption("1M", "blue"),
            SelectOption("2M", "green"),
            SelectOption("3M", "yellow"),
            SelectOption("5M", "orange"),
            SelectOption("None", "gray"),
        ),
    ),
    PropertyDefinition("inverse_fvg_formed", "Inverse FVG Formed", "checkbox"),
    PropertyDefinition("inverse_fvg_clean", "Inverse FVG Clean", "checkbox"),
    PropertyDefinition("market_structure_flip_present", "Market Structure Flip Present", "checkbox"),
    PropertyDefinition("a_plus_setup", "A+ Setup", "checkbox"),
    PropertyDefinition(
        "setup_grade",
        "Setup Grade",
        "select",
        options=(
            SelectOption("A+", "green"),
            SelectOption("A", "blue"),
            SelectOption("B", "yellow"),
            SelectOption("C", "red"),
        ),
    ),
    PropertyDefinition("suboptimal_conditions", "Suboptimal Conditions", "checkbox"),
    PropertyDefinition("forced_trade", "Forced Trade", "checkbox"),
    PropertyDefinition("doubled_down", "Doubled Down", "checkbox"),
    PropertyDefinition("overtraded", "Overtraded", "checkbox"),
    PropertyDefinition("size_appropriate", "Size Appropriate", "checkbox"),
    PropertyDefinition(
        "rule_break_severity",
        "Rule Break Severity",
        "select",
        options=(
            SelectOption("None", "green"),
            SelectOption("Minor", "yellow"),
            SelectOption("Moderate", "orange"),
            SelectOption("Major", "red"),
            SelectOption("High", "red"),
        ),
    ),
    PropertyDefinition("stop_placement_valid", "Stop Placement Valid", "checkbox"),
    PropertyDefinition("target_placement_valid", "Target Placement Valid", "checkbox"),
    PropertyDefinition(
        "be_timing",
        "BE Timing",
        "select",
        options=(
            SelectOption("Proper", "green"),
            SelectOption("Too Early", "yellow"),
            SelectOption("Too Late", "orange"),
            SelectOption("Improper", "red"),
            SelectOption("Missed", "red"),
            SelectOption("Not Used", "gray"),
        ),
    ),
    PropertyDefinition(
        "exit_quality",
        "Exit Quality",
        "select",
        options=(
            SelectOption("Good", "green"),
            SelectOption("Okay", "yellow"),
            SelectOption("Poor", "red"),
        ),
    ),
    PropertyDefinition("confidence", "Confidence", "number"),
    PropertyDefinition("clarity", "Clarity", "number"),
    PropertyDefinition("patience", "Patience", "number"),
    PropertyDefinition(
        "emotional_state",
        "Emotional State",
        "select",
        options=(
            SelectOption("Calm", "green"),
            SelectOption("Slightly Emotional", "yellow"),
            SelectOption("Frustrated", "orange"),
            SelectOption("FOMO", "red"),
            SelectOption("Greedy", "orange"),
            SelectOption("Revenge", "red"),
            SelectOption("Tired", "gray"),
        ),
    ),
    PropertyDefinition("hesitated", "Hesitated", "checkbox"),
    PropertyDefinition("chased", "Chased", "checkbox"),
    PropertyDefinition("entry_rationale", "Entry Rationale", "rich_text"),
    PropertyDefinition("what_went_well", "What Went Well", "rich_text"),
    PropertyDefinition("what_went_wrong", "What Went Wrong", "rich_text"),
    PropertyDefinition("lesson", "Lesson", "rich_text"),
    PropertyDefinition("next_time_rule", "Next-Time Rule", "rich_text"),
    PropertyDefinition("coach_feedback", "Coach Feedback", "rich_text"),
    PropertyDefinition("screenshot", SCREENSHOT_PROPERTY_NAME, "files"),
)


def build_data_source_properties() -> dict[str, dict]:
    """Build the Notion data source schema from the central property definitions."""

    properties: dict[str, dict] = {}
    for definition in TRADE_JOURNAL_PROPERTIES:
        if definition.notion_type == "title":
            properties[definition.notion_name] = {"title": {}}
        elif definition.notion_type == "date":
            properties[definition.notion_name] = {"date": {}}
        elif definition.notion_type == "select":
            properties[definition.notion_name] = {
                "select": {
                    "options": [
                        {"name": option.name, "color": option.color} for option in definition.options
                    ]
                }
            }
        elif definition.notion_type == "rich_text":
            properties[definition.notion_name] = {"rich_text": {}}
        elif definition.notion_type == "number":
            properties[definition.notion_name] = {"number": {"format": definition.number_format}}
        elif definition.notion_type == "checkbox":
            properties[definition.notion_name] = {"checkbox": {}}
        elif definition.notion_type == "files":
            properties[definition.notion_name] = {"files": {}}
        else:
            raise ValueError(f"Unsupported Notion property type: {definition.notion_type}")
    return properties


def expected_property_map() -> dict[str, PropertyDefinition]:
    """Return schema definitions keyed by Notion property name."""

    return {definition.notion_name: definition for definition in TRADE_JOURNAL_PROPERTIES}
