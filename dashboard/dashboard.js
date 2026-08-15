const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});
const els = {
  filtersForm: document.getElementById("filtersForm"),
  resetFilters: document.getElementById("resetFilters"),
  presetChips: document.getElementById("presetChips"),
  recentTradeSpotlight: document.getElementById("recentTradeSpotlight"),
  summaryGrid: document.getElementById("summaryGrid"),
  equityCurve: document.getElementById("equityCurve"),
  equityCaption: document.getElementById("equityCaption"),
  highlightsList: document.getElementById("highlightsList"),
  weeklyScorecards: document.getElementById("weeklyScorecards"),
  monthlyScorecards: document.getElementById("monthlyScorecards"),
  instrumentChart: document.getElementById("instrumentChart"),
  tradeWindowChart: document.getElementById("tradeWindowChart"),
  setupGradeChart: document.getElementById("setupGradeChart"),
  emotionChart: document.getElementById("emotionChart"),
  weekdayChart: document.getElementById("weekdayChart"),
  disciplineChart: document.getElementById("disciplineChart"),
  recentTradesBody: document.getElementById("recentTradesBody"),
  syncTimestamp: document.getElementById("syncTimestamp"),
  sourceMode: document.getElementById("sourceMode"),
  sampleCaption: document.getElementById("sampleCaption"),
  startDate: document.getElementById("startDate"),
  endDate: document.getElementById("endDate"),
  instrumentSelect: document.getElementById("instrumentSelect"),
  accountTypeSelect: document.getElementById("accountTypeSelect"),
  setupGradeSelect: document.getElementById("setupGradeSelect"),
  resultSelect: document.getElementById("resultSelect"),
  pulseHeadline: document.getElementById("pulseHeadline"),
  pulseSubhead: document.getElementById("pulseSubhead"),
  pulseBadges: document.getElementById("pulseBadges"),
  pulseSparkline: document.getElementById("pulseSparkline"),
  pulseMetrics: document.getElementById("pulseMetrics"),
  bestInsight: document.getElementById("bestInsight"),
  leakInsight: document.getElementById("leakInsight"),
  focusInsight: document.getElementById("focusInsight"),
  deskTradesInView: document.getElementById("deskTradesInView"),
  deskScope: document.getElementById("deskScope"),
  deskProfitFactor: document.getElementById("deskProfitFactor"),
  deskDrawdown: document.getElementById("deskDrawdown"),
  reviewNote: document.getElementById("reviewNote"),
  riskNote: document.getElementById("riskNote"),
};

let refreshTimer = null;
let inFlightLoad = null;
let presetDefinitions = [];
let latestPayload = null;
let eventsBound = false;
let runtimeOptions = {
  errorTitle: "Dashboard unavailable",
  onPayload: null,
  onError: null,
};
const HIDDEN_LABELS = new Set(["unspecified"]);
const WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SCORECARD_LIMITS = { weekly: 8, monthly: 6 };
const FLAG_FIELDS = [
  ["forced_trade", "Forced trade"],
  ["overtraded", "Overtraded"],
  ["doubled_down", "Doubled down"],
  ["chased", "Chased"],
  ["hesitated", "Hesitated"],
  ["suboptimal_conditions", "Suboptimal conditions"],
];
function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return currencyFormatter.format(value);
}

function formatSignedCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  if (value > 0) {
    return `+${currencyFormatter.format(value)}`;
  }
  return currencyFormatter.format(value);
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return numberFormatter.format(value);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${percentFormatter.format(value)}%`;
}

function formatDateTime(value) {
  if (!value) {
    return "No data yet";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function parseIsoDate(value) {
  if (!value) {
    return null;
  }
  const text = String(value).slice(0, 10);
  const parts = text.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return null;
  }
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function parseIsoDateTime(value) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function toFloat(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function toInt(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const parsed = parseInt(String(value), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function normalizeTradeRow(row) {
  const aggregateOnly = row.aggregate_only === true;
  const tradeCountWeight = aggregateOnly ? (toInt(row.aggregate_trade_count, 0) || 0) : 1;
  return {
    ...row,
    trade_date_obj: parseIsoDate(row.trade_date),
    entry_time_obj: parseIsoDateTime(row.entry_time),
    pnl_value: toFloat(row.pnl, 0) || 0,
    realized_r_value: toFloat(row.realized_r, null),
    hold_minutes_value: toInt(row.hold_minutes, null),
    aggregate_only: aggregateOnly,
    aggregate_trade_count_value: toInt(row.aggregate_trade_count, 0) || 0,
    trade_count_weight: tradeCountWeight,
  };
}

function mergeDailyResultAggregateRows(rows) {
  return [...rows];
}

function availableFilterValues(trades) {
  const known = trades.filter((trade) => trade.aggregate_only !== true);
  const fields = ["instrument", "account_type", "setup_grade", "result"];
  const values = {};
  fields.forEach((field) => {
    values[field] = [...new Set(known.map((trade) => trade[field]).filter((value) => value))].sort();
  });
  return values;
}

function applyFilters(trades, filters) {
  const startDate = parseIsoDate(filters.start_date);
  const endDate = parseIsoDate(filters.end_date);
  return trades.filter((trade) => {
    const tradeDate = trade.trade_date_obj;
    if (startDate && tradeDate && tradeDate < startDate) {
      return false;
    }
    if (endDate && tradeDate && tradeDate > endDate) {
      return false;
    }
    if (trade.aggregate_only === true && (filters.instrument || filters.setup_grade || filters.result)) {
      return false;
    }
    if (filters.instrument && trade.instrument !== filters.instrument) {
      return false;
    }
    if (filters.account_type && trade.account_type !== filters.account_type) {
      return false;
    }
    if (filters.setup_grade && trade.setup_grade !== filters.setup_grade) {
      return false;
    }
    if (filters.result && trade.result !== filters.result) {
      return false;
    }
    return true;
  });
}

function sortTradesDesc(trades) {
  return [...trades].sort((a, b) => {
    const aDate = a.trade_date_obj ? a.trade_date_obj.getTime() : 0;
    const bDate = b.trade_date_obj ? b.trade_date_obj.getTime() : 0;
    if (aDate !== bDate) {
      return bDate - aDate;
    }
    return String(b.entry_time || "").localeCompare(String(a.entry_time || ""));
  });
}

function countTradeUnits(trades) {
  return trades.reduce((acc, trade) => acc + (toInt(trade.trade_count_weight, 0) || 0), 0);
}

function aggregateAdjustmentSummary(trades) {
  const aggregateRows = trades.filter((trade) => trade.aggregate_only === true);
  return {
    day_count: aggregateRows.length,
    trade_count: countTradeUnits(aggregateRows),
    total_pnl: aggregateRows.reduce((acc, trade) => acc + (trade.pnl_value || 0), 0),
    dates: aggregateRows.map((trade) => trade.trade_date).sort(),
  };
}

function computeWinRate(wins, losses) {
  const decisiveTrades = wins + losses;
  if (!decisiveTrades) {
    return null;
  }
  return (wins / decisiveTrades) * 100;
}

function groupMetrics(trades, field, fallbackLabel = "Unspecified") {
  const grouped = new Map();
  trades.forEach((trade) => {
    if (trade.aggregate_only === true) {
      return;
    }
    const label = trade[field] || fallbackLabel;
    if (!grouped.has(label)) {
      grouped.set(label, { label, count: 0, wins: 0, losses: 0, breakevens: 0, pnl: 0 });
    }
    const bucket = grouped.get(label);
    bucket.count += 1;
    bucket.pnl += trade.pnl_value || 0;
    if (trade.result === "Win") {
      bucket.wins += 1;
    } else if (trade.result === "Loss") {
      bucket.losses += 1;
    } else if (trade.result === "Breakeven") {
      bucket.breakevens += 1;
    }
  });
  return [...grouped.values()]
    .map((bucket) => ({
      ...bucket,
      avg_pnl: bucket.pnl / (bucket.count || 1),
      win_rate: computeWinRate(bucket.wins, bucket.losses),
    }))
    .sort((a, b) => (b.pnl - a.pnl) || (b.count - a.count));
}

function buildEquityCurve(trades) {
  const daily = new Map();
  trades.forEach((trade) => {
    if (!trade.trade_date) {
      return;
    }
    const key = trade.trade_date;
    if (!daily.has(key)) {
      daily.set(key, { date: key, daily_pnl: 0, count: 0 });
    }
    const bucket = daily.get(key);
    bucket.daily_pnl += trade.pnl_value || 0;
    bucket.count += toInt(trade.trade_count_weight, 0) || 0;
  });
  let cumulative = 0;
  return [...daily.keys()].sort().map((key) => {
    const bucket = daily.get(key);
    cumulative += bucket.daily_pnl;
    return { ...bucket, cumulative_pnl: cumulative };
  });
}

function buildWeekdayPerformance(trades) {
  const grouped = new Map(WEEKDAY_ORDER.map((day) => [day, { label: day, count: 0, pnl: 0 }]));
  trades.forEach((trade) => {
    if (!trade.trade_date_obj) {
      return;
    }
    const day = WEEKDAY_ORDER[trade.trade_date_obj.getDay() === 0 ? 6 : trade.trade_date_obj.getDay() - 1];
    const bucket = grouped.get(day);
    bucket.count += toInt(trade.trade_count_weight, 0) || 0;
    bucket.pnl += trade.pnl_value || 0;
  });
  return WEEKDAY_ORDER
    .map((day) => grouped.get(day))
    .filter((row) => row.count > 0)
    .map((row) => ({ ...row, avg_pnl: row.pnl / row.count }));
}

function buildFlagPerformance(trades) {
  const known = trades.filter((trade) => trade.aggregate_only !== true);
  const sampleSize = known.length || 1;
  const rows = [];
  FLAG_FIELDS.forEach(([field, label]) => {
    const flagged = known.filter((trade) => trade[field] === true);
    if (!flagged.length) {
      return;
    }
    const pnl = flagged.reduce((acc, trade) => acc + (trade.pnl_value || 0), 0);
    const wins = flagged.filter((trade) => trade.result === "Win").length;
    const losses = flagged.filter((trade) => trade.result === "Loss").length;
    rows.push({
      label,
      count: flagged.length,
      share_of_sample: (flagged.length / sampleSize) * 100,
      pnl,
      avg_pnl: pnl / flagged.length,
      win_rate: computeWinRate(wins, losses),
    });
  });
  return rows.sort((a, b) => a.pnl - b.pnl);
}

function summarizeSample(trades) {
  if (!trades.length) {
    return {
      total_trades: 0,
      total_pnl: 0,
      avg_trade: 0,
      win_rate: 0,
      profit_factor: null,
      average_r: null,
      average_hold_minutes: null,
      best_trade: null,
      worst_trade: null,
      gross_profit: 0,
      gross_loss: 0,
      known_trade_count: 0,
      aggregate_only_trade_count: 0,
      aggregate_only_day_count: 0,
      aggregate_only_pnl: 0,
    };
  }
  const known = trades.filter((trade) => trade.aggregate_only !== true);
  const aggregateAdjustments = aggregateAdjustmentSummary(trades);
  const pnls = trades.map((trade) => trade.pnl_value || 0);
  const knownPnls = known.map((trade) => trade.pnl_value || 0);
  const wins = pnls.filter((value) => value > 0);
  const losses = pnls.filter((value) => value < 0);
  const winsCount = known.filter((trade) => trade.result === "Win").length;
  const lossesCount = known.filter((trade) => trade.result === "Loss").length;
  const realizedRs = known.map((trade) => trade.realized_r_value).filter((value) => value !== null);
  const holdMinutes = known.map((trade) => trade.hold_minutes_value).filter((value) => value !== null);
  const grossProfit = wins.reduce((left, right) => left + right, 0);
  const grossLoss = losses.reduce((left, right) => left + right, 0);
  const tradeUnits = countTradeUnits(trades);
  return {
    total_trades: tradeUnits,
    total_pnl: pnls.reduce((left, right) => left + right, 0),
    avg_trade: pnls.reduce((left, right) => left + right, 0) / Math.max(tradeUnits, 1),
    win_rate: computeWinRate(winsCount, lossesCount),
    profit_factor: grossLoss ? (grossProfit / Math.abs(grossLoss)) : null,
    average_r: realizedRs.length ? (realizedRs.reduce((left, right) => left + right, 0) / realizedRs.length) : null,
    average_hold_minutes: holdMinutes.length ? (holdMinutes.reduce((left, right) => left + right, 0) / holdMinutes.length) : null,
    best_trade: knownPnls.length ? Math.max(...knownPnls) : null,
    worst_trade: knownPnls.length ? Math.min(...knownPnls) : null,
    gross_profit: grossProfit,
    gross_loss: grossLoss,
    known_trade_count: known.length,
    aggregate_only_trade_count: aggregateAdjustments.trade_count,
    aggregate_only_day_count: aggregateAdjustments.day_count,
    aggregate_only_pnl: aggregateAdjustments.total_pnl,
  };
}

function buildStreaks(trades) {
  const known = trades.filter((trade) => trade.aggregate_only !== true);
  if (!known.length) {
    return { current: { type: null, count: 0, label: "No trades yet" }, max_win_streak: 0, max_loss_streak: 0 };
  }
  const ordered = sortTradesDesc(known).reverse();
  let currentType = null;
  let currentCount = 0;
  let maxWin = 0;
  let maxLoss = 0;
  let runningType = null;
  let runningCount = 0;
  ordered.forEach((trade) => {
    const result = trade.result;
    if (result === runningType) {
      runningCount += 1;
    } else {
      runningType = result;
      runningCount = 1;
    }
    if (result === "Win") {
      maxWin = Math.max(maxWin, runningCount);
    }
    if (result === "Loss") {
      maxLoss = Math.max(maxLoss, runningCount);
    }
    currentType = runningType;
    currentCount = runningCount;
  });
  const streakWord = currentCount === 1 ? "trade" : "streak";
  return {
    current: {
      type: currentType,
      count: currentCount,
      label: currentType ? `${currentCount} ${String(currentType).toLowerCase()} ${streakWord}` : "No trades yet",
    },
    max_win_streak: maxWin,
    max_loss_streak: maxLoss,
  };
}

function buildHighlights(trades, byInstrument, byTradeWindow, flagPerformance) {
  const highlights = [];
  if (byInstrument.length) {
    const best = byInstrument[0];
    highlights.push({
      title: "Best instrument",
      value: best.label,
      detail: `${best.count} trades, ${best.win_rate.toFixed(1)}% win rate, $${best.pnl.toFixed(2)}`,
    });
  }
  if (byTradeWindow.length) {
    const best = byTradeWindow[0];
    highlights.push({
      title: "Strongest window",
      value: best.label,
      detail: `${best.count} trades, $${best.avg_pnl.toFixed(2)} avg per trade`,
    });
  }
  if (flagPerformance.length) {
    const leak = flagPerformance.reduce((min, row) => (row.pnl < min.pnl ? row : min), flagPerformance[0]);
    highlights.push({
      title: "Biggest leak",
      value: leak.label,
      detail: `${leak.count} trades flagged, $${leak.pnl.toFixed(2)} total`,
    });
  }
  if (!highlights.length && trades.length) {
    highlights.push({
      title: "Sample size",
      value: String(trades.length),
      detail: "You have enough synced trades to start tracking patterns.",
    });
  }
  return highlights.slice(0, 3);
}

function buildRecentTrades(trades, limit = 12) {
  return sortTradesDesc(trades.filter((trade) => trade.aggregate_only !== true)).slice(0, limit).map((trade) => ({
    trade_name: trade.trade_name,
    trade_date: trade.trade_date,
    instrument: trade.instrument,
    direction: trade.direction,
    result: trade.result,
    pnl: trade.pnl_value,
    setup_grade: trade.setup_grade,
    trade_window: trade.trade_window,
    emotional_state: trade.emotional_state,
  }));
}

function formatMonthDay(value) {
  return value.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function monthEndFor(monthStart) {
  return new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, 0));
}

function buildPeriodScorecards(trades, period) {
  const limit = SCORECARD_LIMITS[period];
  const grouped = new Map();
  trades.forEach((trade) => {
    if (!trade.trade_date_obj) {
      return;
    }
    const date = new Date(Date.UTC(
      trade.trade_date_obj.getFullYear(),
      trade.trade_date_obj.getMonth(),
      trade.trade_date_obj.getDate(),
    ));
    let periodStart;
    let periodEnd;
    if (period === "weekly") {
      const weekday = (date.getUTCDay() + 6) % 7;
      periodStart = new Date(date);
      periodStart.setUTCDate(date.getUTCDate() - weekday);
      periodEnd = new Date(periodStart);
      periodEnd.setUTCDate(periodStart.getUTCDate() + 6);
    } else {
      periodStart = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
      periodEnd = monthEndFor(periodStart);
    }
    const key = periodStart.toISOString().slice(0, 10);
    if (!grouped.has(key)) {
      grouped.set(key, { period_start: periodStart, period_end: periodEnd, trades: [] });
    }
    grouped.get(key).trades.push(trade);
  });

  return [...grouped.keys()].sort().reverse().slice(0, limit).map((key) => {
    const bucket = grouped.get(key);
    const periodTrades = bucket.trades;
    const knownPeriodTrades = periodTrades.filter((trade) => trade.aggregate_only !== true);
    const summary = summarizeSample(periodTrades);
    const daily = new Map();
    periodTrades.forEach((trade) => {
      if (!trade.trade_date) {
        return;
      }
      daily.set(trade.trade_date, (daily.get(trade.trade_date) || 0) + (trade.pnl_value || 0));
    });
    const dailyEntries = [...daily.entries()];
    const bestDay = dailyEntries.sort((left, right) => right[1] - left[1])[0];
    const topInstrument = groupMetrics(knownPeriodTrades, "instrument")[0];
    const topSetup = groupMetrics(knownPeriodTrades, "setup_grade")[0];
    const aggregateAdjustments = aggregateAdjustmentSummary(periodTrades);
    const wins = knownPeriodTrades.filter((trade) => trade.result === "Win").length;
    const losses = knownPeriodTrades.filter((trade) => trade.result === "Loss").length;
    const breakevens = knownPeriodTrades.filter((trade) => trade.result === "Breakeven").length;
    const greenDays = dailyEntries.filter((entry) => entry[1] > 0).length;
    const redDays = dailyEntries.filter((entry) => entry[1] < 0).length;
    const flatDays = dailyEntries.filter((entry) => entry[1] === 0).length;

    const title = period === "weekly"
      ? `Week of ${formatMonthDay(bucket.period_start)}`
      : bucket.period_start.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
    const subtitle = `${formatMonthDay(bucket.period_start)} - ${formatMonthDay(bucket.period_end)}`;
    return {
      period,
      period_key: key,
      title,
      subtitle,
      start_date: key,
      end_date: bucket.period_end.toISOString().slice(0, 10),
      total_trades: summary.total_trades,
      trading_days: dailyEntries.length,
      wins,
      losses,
      breakevens,
      green_days: greenDays,
      red_days: redDays,
      flat_days: flatDays,
      total_pnl: summary.total_pnl,
      avg_trade: summary.avg_trade,
      win_rate: summary.win_rate,
      profit_factor: summary.profit_factor,
      average_r: summary.average_r,
      best_trade: summary.best_trade,
      worst_trade: summary.worst_trade,
      best_day_label: bestDay ? formatMonthDay(parseIsoDate(bestDay[0])) : null,
      best_day_pnl: bestDay ? bestDay[1] : null,
      top_instrument: topInstrument ? topInstrument.label : null,
      top_instrument_pnl: topInstrument ? topInstrument.pnl : null,
      top_setup_grade: topSetup ? topSetup.label : null,
      top_setup_grade_pnl: topSetup ? topSetup.pnl : null,
      aggregate_only_trade_count: aggregateAdjustments.trade_count,
      aggregate_only_day_count: aggregateAdjustments.day_count,
      aggregate_only_pnl: aggregateAdjustments.total_pnl,
      aggregate_only_dates: aggregateAdjustments.dates,
    };
  });
}

function buildDashboardPayload(rawRows, filters) {
  const mergedRows = mergeDailyResultAggregateRows(rawRows || []);
  const normalized = mergedRows.map(normalizeTradeRow);
  const filtered = applyFilters(normalized, filters);
  const aggregateAdjustments = aggregateAdjustmentSummary(filtered);
  const sourceAggregateAdjustments = aggregateAdjustmentSummary(normalized);
  const filteredKnownTrades = filtered.filter((trade) => trade.aggregate_only !== true);
  const byInstrument = groupMetrics(filtered, "instrument");
  const byTradeWindow = groupMetrics(filtered, "trade_window");
  const bySetupGrade = groupMetrics(filtered, "setup_grade");
  const byEmotionalState = groupMetrics(filtered, "emotional_state");
  const flagPerformance = buildFlagPerformance(filtered);
  const streaks = buildStreaks(filtered);
  return {
    generated_at: new Date().toISOString(),
    filters: {
      active: { ...filters },
      available: availableFilterValues(normalized),
      result_count: countTradeUnits(filtered),
      source_count: countTradeUnits(normalized),
      known_result_count: filteredKnownTrades.length,
      known_source_count: normalized.filter((trade) => trade.aggregate_only !== true).length,
    },
    summary: { ...summarizeSample(filtered), ...streaks },
    highlights: buildHighlights(filtered, byInstrument, byTradeWindow, flagPerformance),
    scorecards: {
      weekly: buildPeriodScorecards(filtered, "weekly"),
      monthly: buildPeriodScorecards(filtered, "monthly"),
    },
    charts: {
      equity_curve: buildEquityCurve(filtered),
      by_instrument: byInstrument,
      by_trade_window: byTradeWindow,
      by_setup_grade: bySetupGrade,
      by_emotional_state: byEmotionalState,
      weekday_performance: buildWeekdayPerformance(filtered),
      discipline_flags: flagPerformance,
    },
    recent_trades: buildRecentTrades(filtered),
    aggregate_adjustments: { filtered: aggregateAdjustments, source: sourceAggregateAdjustments },
    source: { mode: "snapshot", label: "Local data snapshot", auto_sync: { enabled: false } },
  };
}

async function fetchDashboardPayload(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });

  const response = await fetch(`/api/dashboard-data?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Dashboard API returned ${response.status}`);
  }
  const payload = await response.json();
  if (!payload?.summary || !payload?.charts) {
    throw new Error("Dashboard API returned an unexpected payload.");
  }
  return payload;
}

function formatInterval(seconds) {
  if (!seconds || Number.isNaN(Number(seconds))) {
    return "—";
  }
  const totalSeconds = Number(seconds);
  if (totalSeconds % 3600 === 0) {
    return `${totalSeconds / 3600}h`;
  }
  if (totalSeconds % 60 === 0) {
    return `${totalSeconds / 60}m`;
  }
  return `${totalSeconds}s`;
}

function capitalize(value) {
  if (!value) {
    return "";
  }
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}

function isoDate(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function shiftDays(date, days) {
  const shifted = new Date(date);
  shifted.setDate(shifted.getDate() + days);
  return shifted;
}

function startOfWeek(date) {
  const result = new Date(date);
  const weekday = result.getDay();
  const offset = weekday === 0 ? -6 : 1 - weekday;
  result.setDate(result.getDate() + offset);
  return result;
}

function currentFilters() {
  const formData = new FormData(els.filtersForm);
  const params = new URLSearchParams();
  for (const [key, value] of formData.entries()) {
    if (String(value).trim()) {
      params.set(key, value);
    }
  }
  return params;
}

function currentActiveFiltersFromInputs() {
  return {
    start_date: els.startDate.value || null,
    end_date: els.endDate.value || null,
    instrument: els.instrumentSelect.value || null,
    account_type: els.accountTypeSelect.value || null,
    setup_grade: els.setupGradeSelect.value || null,
    result: els.resultSelect.value || null,
  };
}

function setSelectOptions(selectEl, options, selectedValue) {
  const placeholder = selectEl.querySelector("option")?.textContent || "All";
  selectEl.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  selectEl.appendChild(empty);

  options.forEach((optionValue) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue;
    if (optionValue === selectedValue) {
      option.selected = true;
    }
    selectEl.appendChild(option);
  });
}

function populateFilters(payload) {
  const { active, available } = payload.filters;
  els.startDate.value = active.start_date || "";
  els.endDate.value = active.end_date || "";
  setSelectOptions(els.instrumentSelect, available.instrument || [], active.instrument);
  setSelectOptions(els.accountTypeSelect, available.account_type || [], active.account_type);
  setSelectOptions(els.setupGradeSelect, available.setup_grade || [], active.setup_grade);
  setSelectOptions(els.resultSelect, available.result || [], active.result);
}

function toneClass(value, thresholds = {}) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return "";
  }
  const positiveFloor = thresholds.positiveFloor ?? 0;
  const negativeCeiling = thresholds.negativeCeiling ?? 0;
  if (numeric > positiveFloor) {
    return "positive";
  }
  if (numeric < negativeCeiling) {
    return "negative";
  }
  return "";
}

function setTone(strongEl, tone) {
  const parent = strongEl?.parentElement;
  if (!parent) {
    return;
  }
  parent.classList.remove("positive", "negative");
  if (tone) {
    parent.classList.add(tone);
  }
}

function isUsableLabel(value) {
  if (value === null || value === undefined) {
    return false;
  }
  const normalized = String(value).trim().toLowerCase();
  return Boolean(normalized) && !HIDDEN_LABELS.has(normalized);
}

function displayLabel(value) {
  return isUsableLabel(value) ? value : "—";
}

function filterUsableRows(rows) {
  return (rows || []).filter((row) => isUsableLabel(row.label));
}

function tradeOutcomeTone(trade) {
  const result = String(trade?.result || "").toLowerCase();
  if (result === "win") {
    return "positive";
  }
  if (result === "loss") {
    return "negative";
  }

  const pnl = Number(trade?.pnl) || 0;
  if (Math.abs(pnl) >= 25) {
    return toneClass(pnl);
  }
  return "";
}

function joinPresent(parts, separator = " · ") {
  return parts.filter(Boolean).join(separator);
}

function computeMaxDrawdown(points) {
  let peak = 0;
  let peakDate = null;
  let maxDrawdown = 0;
  let troughDate = null;

  points.forEach((point) => {
    const value = Number(point.cumulative_pnl) || 0;
    if (value > peak) {
      peak = value;
      peakDate = point.date;
    }
    const drawdown = peak - value;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
      troughDate = point.date;
    }
  });

  return { value: maxDrawdown, peakDate, troughDate };
}

function describeFilterScope(active) {
  const parts = [];
  if (active.start_date || active.end_date) {
    if (active.start_date && active.end_date) {
      parts.push(`${active.start_date} to ${active.end_date}`);
    } else if (active.start_date) {
      parts.push(`Since ${active.start_date}`);
    } else if (active.end_date) {
      parts.push(`Through ${active.end_date}`);
    }
  }
  if (active.account_type) {
    parts.push(active.account_type);
  }
  if (active.instrument) {
    parts.push(active.instrument);
  }
  if (active.setup_grade) {
    parts.push(`${active.setup_grade} setups`);
  }
  if (active.result) {
    parts.push(active.result);
  }
  return parts.length ? parts.join(" / ") : "All synced trades";
}

function buildMiniSparkline(points) {
  if (!points.length) {
    return `<div class="compact-empty">No curve yet for this filter set.</div>`;
  }

  const width = 640;
  const height = 108;
  const padding = { top: 10, right: 10, bottom: 10, left: 10 };
  const values = points.map((point) => Number(point.cumulative_pnl) || 0);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const zeroY = padding.top + ((max - 0) / range) * innerHeight;

  const coords = points.map((point, index) => {
    const x = padding.left + (innerWidth * index) / Math.max(points.length - 1, 1);
    const y = padding.top + ((max - (Number(point.cumulative_pnl) || 0)) / range) * innerHeight;
    return { x, y, point };
  });

  const linePath = coords
    .map((coord, index) => `${index === 0 ? "M" : "L"} ${coord.x.toFixed(1)} ${coord.y.toFixed(1)}`)
    .join(" ");
  const areaPath = `${linePath} L ${coords.at(-1).x.toFixed(1)} ${(height - padding.bottom).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(height - padding.bottom).toFixed(1)} Z`;

  return `
    <svg class="mini-sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Trading pulse sparkline">
      <line class="sparkline-grid" x1="${padding.left}" y1="${padding.top}" x2="${width - padding.right}" y2="${padding.top}"></line>
      <line class="sparkline-grid" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
      <line class="sparkline-baseline" x1="${padding.left}" y1="${zeroY.toFixed(1)}" x2="${width - padding.right}" y2="${zeroY.toFixed(1)}"></line>
      <path class="sparkline-fill" d="${areaPath}"></path>
      <path class="sparkline-line" d="${linePath}"></path>
      <circle class="sparkline-end" cx="${coords.at(-1).x.toFixed(1)}" cy="${coords.at(-1).y.toFixed(1)}" r="4.5"></circle>
    </svg>
  `;
}

function findBestRow(rows) {
  const visibleRows = filterUsableRows(rows);
  if (!visibleRows.length) {
    return null;
  }
  return visibleRows[0];
}

function findWorstRow(rows) {
  const visibleRows = filterUsableRows(rows);
  if (!visibleRows.length) {
    return null;
  }
  return [...visibleRows].sort((a, b) => (Number(a.pnl) || 0) - (Number(b.pnl) || 0))[0];
}

function buildCommandMetrics(payload) {
  const summary = payload.summary || {};
  const charts = payload.charts || {};
  const drawdown = computeMaxDrawdown(charts.equity_curve || []);
  const bestSetup = findBestRow(charts.by_setup_grade || []);
  const worstWindow = findWorstRow(charts.by_trade_window || []);

  return [
    {
      label: "Net P&L",
      value: formatSignedCurrency(summary.total_pnl),
      meta: `${formatNumber(summary.total_trades || 0)} trades in scope`,
      tone: toneClass(summary.total_pnl),
    },
    {
      label: "Win rate",
      value: formatPercent(summary.win_rate),
      meta: `Gross profit ${formatCurrency(summary.gross_profit)}`,
      tone: toneClass(summary.win_rate, { positiveFloor: 50, negativeCeiling: 50 }),
    },
    {
      label: "Expectancy",
      value: formatSignedCurrency(summary.avg_trade),
      meta: "Average P&L per trade",
      tone: toneClass(summary.avg_trade),
    },
    {
      label: "Avg R",
      value: summary.average_r === null ? "—" : formatNumber(summary.average_r),
      meta: "Realized R on scored trades",
      tone: toneClass(summary.average_r),
    },
    {
      label: "Profit factor",
      value: summary.profit_factor === null ? "—" : formatNumber(summary.profit_factor),
      meta: `Gross loss ${formatCurrency(summary.gross_loss)}`,
      tone: toneClass(summary.profit_factor, { positiveFloor: 1, negativeCeiling: 1 }),
    },
    {
      label: "Max drawdown",
      value: formatCurrency(drawdown.value),
      meta: drawdown.troughDate ? `Deepest pullback into ${drawdown.troughDate}` : "No drawdown yet",
      tone: drawdown.value > 0 ? "negative" : "",
    },
    {
      label: "Total trades",
      value: formatNumber(summary.total_trades || 0),
      meta: `${formatNumber(summary.known_trade_count || 0)} journal rows tagged`,
      tone: "",
    },
    {
      label: "Best setup",
      value: bestSetup?.label || "—",
      meta: bestSetup ? `${formatSignedCurrency(bestSetup.pnl)} total, ${formatPercent(bestSetup.win_rate)} win rate` : "No setup breakdown yet",
      tone: bestSetup && Number(bestSetup.pnl) > 0 ? "positive" : "",
    },
    {
      label: "Worst window",
      value: worstWindow?.label || "—",
      meta: worstWindow ? `${formatSignedCurrency(worstWindow.pnl)} total, ${formatSignedCurrency(worstWindow.avg_pnl)} avg` : "No trade-window breakdown yet",
      tone: worstWindow && Number(worstWindow.pnl) < 0 ? "negative" : "",
    },
  ];
}

function renderCommandCenter(payload) {
  const summary = payload.summary || {};
  const charts = payload.charts || {};
  const active = payload.filters?.active || {};
  const bestSetup = findBestRow(charts.by_setup_grade || []);
  const bestWindow = findBestRow(charts.by_trade_window || []);
  const worstWindow = findWorstRow(charts.by_trade_window || []);
  const biggestLeak = findWorstRow(charts.discipline_flags || []);
  const drawdown = computeMaxDrawdown(charts.equity_curve || []);
  const scope = describeFilterScope(active);
  const mode = payload.source?.mode || "live";

  els.pulseHeadline.textContent = "Workflow Analytics Dashboard";
  els.pulseSubhead.textContent = [
    formatSignedCurrency(summary.total_pnl),
    `${formatPercent(summary.win_rate)} win rate`,
    `${formatSignedCurrency(summary.avg_trade)} expectancy`,
  ].join(" | ");

  const badges = [
    {
      label: mode === "demo" ? "Synthetic dataset" : mode === "snapshot" ? "Snapshot feed" : "Private live feed",
      tone: mode === "live" ? "positive" : "",
    },
    {
      label: `${formatNumber(summary.total_trades || 0)} records`,
      tone: "",
    },
    {
      label: drawdown.value ? `MDD ${formatCurrency(drawdown.value)}` : "Flat drawdown",
      tone: drawdown.value ? "negative" : "positive",
    },
  ];

  if (bestSetup?.label) {
    badges.push({
      label: `${bestSetup.label} segment`,
      tone: Number(bestSetup.pnl) > 0 ? "positive" : "",
    });
  }

  els.pulseBadges.innerHTML = badges.map((badge) => `
    <span class="command-badge ${badge.tone || ""}">${badge.label}</span>
  `).join("");

  els.pulseSparkline.innerHTML = buildMiniSparkline(charts.equity_curve || []);

  els.pulseMetrics.innerHTML = buildCommandMetrics(payload).map((metric) => `
    <article class="command-metric ${metric.tone || ""}">
      <span>${metric.label}</span>
      <strong>${metric.value}</strong>
      <p>${metric.meta}</p>
    </article>
  `).join("");

  els.bestInsight.textContent = bestSetup
    ? `${bestSetup.label} setups are leading${bestWindow ? `, especially during ${bestWindow.label}` : ""}.`
    : "More tagged records are needed before a reliable setup pattern stands out.";

  els.leakInsight.textContent = worstWindow
    ? `${worstWindow.label} is the weakest time window at ${formatSignedCurrency(worstWindow.pnl)} total.`
    : biggestLeak
      ? `${biggestLeak.label} is the most costly process flag in the current scope.`
      : "No obvious weak window appears in the current scope.";

  els.focusInsight.textContent = biggestLeak
    ? `Review ${biggestLeak.label.toLowerCase()} decisions; flagged records averaged ${formatSignedCurrency(biggestLeak.avg_pnl)}.`
    : bestSetup
      ? `Compare the ${bestSetup.label} segment against the broader sample before changing the workflow.`
      : "Keep tagging records consistently so the analytics can surface clearer process patterns.";

  els.deskTradesInView.textContent = formatNumber(summary.total_trades || 0);
  els.deskScope.textContent = scope;
  els.deskProfitFactor.textContent = summary.profit_factor === null ? "—" : formatNumber(summary.profit_factor);
  els.deskDrawdown.textContent = formatCurrency(drawdown.value);

  setTone(els.deskProfitFactor, toneClass(summary.profit_factor, { positiveFloor: 1, negativeCeiling: 1 }));
  setTone(els.deskDrawdown, drawdown.value > 0 ? "negative" : "");

  els.reviewNote.textContent = bestSetup
    ? `${bestSetup.label} setups are producing ${formatSignedCurrency(bestSetup.avg_pnl)} per trade with a ${formatPercent(bestSetup.win_rate)} win rate.`
    : `Win rate is ${formatPercent(summary.win_rate)} across ${formatNumber(summary.total_trades || 0)} trades in the current scope.`;

  if (biggestLeak) {
    els.riskNote.textContent = `${biggestLeak.label} flags are costing ${formatSignedCurrency(biggestLeak.pnl)} total, and max drawdown is ${formatCurrency(drawdown.value)}.`;
  } else if (worstWindow) {
    els.riskNote.textContent = `${worstWindow.label} remains the weakest window. Protect size there while the sample catches up.`;
  } else {
    els.riskNote.textContent = drawdown.value
      ? `Current max drawdown is ${formatCurrency(drawdown.value)}. Keep execution tight while the curve rebuilds.`
      : "No major risk note yet. Keep the filter scope tight and stay selective.";
  }
}

function summaryCards(payload) {
  const summary = payload.summary || {};
  const scope = describeFilterScope(payload.filters?.active || {});
  return [
    {
      label: "Gross profit",
      value: formatCurrency(summary.gross_profit),
      meta: `Gross loss ${formatCurrency(summary.gross_loss)}`,
      tone: "positive",
    },
    {
      label: "Best trade",
      value: formatCurrency(summary.best_trade),
      meta: `Worst trade ${formatCurrency(summary.worst_trade)}`,
      tone: toneClass(summary.best_trade),
    },
    {
      label: "Current streak",
      value: summary.current?.count ? `${summary.current.count}` : "0",
      meta: summary.current?.label || "No streak yet",
      tone: summary.current?.type === "Win" ? "positive" : summary.current?.type === "Loss" ? "negative" : "",
    },
    {
      label: "Max streaks",
      value: `${formatNumber(summary.max_win_streak || 0)} / ${formatNumber(summary.max_loss_streak || 0)}`,
      meta: "Win streak / loss streak",
      tone: "",
    },
    {
      label: "Average hold",
      value: summary.average_hold_minutes === null ? "—" : `${formatNumber(summary.average_hold_minutes)}m`,
      meta: "Time in market",
      tone: "",
    },
    {
      label: "Review scope",
      value: formatNumber(summary.total_trades || 0),
      meta: scope,
      tone: "",
    },
    {
      label: "Journal rows",
      value: formatNumber(summary.known_trade_count || 0),
      meta: "Direct trade-level entries",
      tone: "",
    },
    {
      label: "Aggregate days",
      value: formatNumber(summary.aggregate_only_day_count || 0),
      meta: `${formatNumber(summary.aggregate_only_trade_count || 0)} aggregate-only trades`,
      tone: "",
    },
  ];
}

function renderSummary(payload) {
  els.summaryGrid.innerHTML = "";
  summaryCards(payload).forEach((card, index) => {
    const node = document.createElement("article");
    node.className = `summary-card ${card.tone}`.trim();
    node.style.animationDelay = `${120 + index * 45}ms`;
    node.innerHTML = `
      <div class="summary-label">${card.label}</div>
      <div class="summary-value">${card.value}</div>
      <div class="summary-meta">${card.meta}</div>
    `;
    els.summaryGrid.appendChild(node);
  });
}

function buildRecentTradeInsight(trade) {
  const windowLabel = isUsableLabel(trade.trade_window) ? trade.trade_window : "the current window";
  const setupLabel = isUsableLabel(trade.setup_grade) ? `${trade.setup_grade} setup` : "latest setup";
  const directionLabel = trade.direction ? trade.direction.toLowerCase() : "trade";
  const stateLabel = isUsableLabel(trade.emotional_state)
    ? `${trade.emotional_state.toLowerCase()} execution`
    : "execution context";
  const pnlLabel = formatSignedCurrency(trade.pnl);
  const result = String(trade.result || "").toLowerCase();

  if (result === "win") {
    return `${setupLabel} ${directionLabel} in ${windowLabel} closed ${pnlLabel}. ${capitalize(stateLabel)} is worth replaying if the process matched plan.`;
  }
  if (result === "loss") {
    return `${setupLabel} ${directionLabel} in ${windowLabel} finished ${pnlLabel}. Replay the sequence and check whether the execution stayed aligned once pressure showed up.`;
  }
  if (result === "breakeven") {
    return `${setupLabel} ${directionLabel} in ${windowLabel} scratched near flat. ${capitalize(stateLabel)} protected capital; review whether the exit was disciplined or early.`;
  }
  return `${setupLabel} ${directionLabel} from the latest session finished ${pnlLabel}. ${capitalize(stateLabel)} is the first thing to review.`;
}

function renderRecentTradeSpotlight(trades) {
  if (!els.recentTradeSpotlight) {
    return;
  }

  const trade = (trades || [])[0];
  if (!trade) {
    els.recentTradeSpotlight.innerHTML = `<div class="empty-state">No recent trade is available for the current filter set.</div>`;
    return;
  }

  const tone = tradeOutcomeTone(trade);
  const heading = trade.trade_name
    || joinPresent([isUsableLabel(trade.instrument) ? trade.instrument : null, trade.direction], " ")
    || "Latest trade";
  const identityLine = joinPresent([
    trade.trade_date || null,
    isUsableLabel(trade.instrument) ? trade.instrument : null,
    trade.direction || null,
    isUsableLabel(trade.trade_window) ? trade.trade_window : null,
  ]);
  const resultLabel = trade.result || "Recent trade";
  const stats = [
    { label: "P&L", value: formatSignedCurrency(trade.pnl), tone: toneClass(trade.pnl) },
    { label: "Result", value: resultLabel, tone },
    { label: "Setup", value: displayLabel(trade.setup_grade), tone: "" },
    { label: "Window", value: displayLabel(trade.trade_window), tone: "" },
    { label: "State", value: displayLabel(trade.emotional_state), tone: "" },
    {
      label: "Instrument",
      value: joinPresent([isUsableLabel(trade.instrument) ? trade.instrument : null, trade.direction], " · ") || "—",
      tone: "",
    },
  ];

  els.recentTradeSpotlight.innerHTML = `
    <div class="recent-trade-shell ${tone}">
      <div class="recent-trade-copy">
        <div class="recent-trade-status-row">
          <span class="recent-trade-status ${tone}">${resultLabel}</span>
          <span class="recent-trade-date">${trade.trade_date || "—"}</span>
        </div>
        <h3>${heading}</h3>
        <p class="recent-trade-meta">${identityLine || "Most recent trade in the current review scope."}</p>
        <p class="recent-trade-note">${buildRecentTradeInsight(trade)}</p>
      </div>
      <div class="recent-trade-stats">
        ${stats.map((stat, index) => `
          <article class="recent-trade-stat ${stat.tone || ""}" style="animation-delay: ${90 + index * 40}ms;">
            <span>${stat.label}</span>
            <strong>${stat.value}</strong>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function renderHighlights(highlights) {
  const visibleHighlights = (highlights || []).filter((item) => isUsableLabel(item.value));
  if (!visibleHighlights.length) {
    els.highlightsList.innerHTML = `<div class="empty-state">Keep syncing trades and tagging setups so this review rail can surface sharper edge notes.</div>`;
    return;
  }

  els.highlightsList.innerHTML = "";
  visibleHighlights.forEach((item) => {
    const card = document.createElement("article");
    card.className = "highlight-card";
    card.innerHTML = `
      <h3>${item.title}</h3>
      <div class="highlight-value">${item.value}</div>
      <div class="metric-meta">${item.detail}</div>
    `;
    els.highlightsList.appendChild(card);
  });
}

function renderScorecards(container, scorecards, emptyMessage) {
  if (!scorecards.length) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  container.innerHTML = scorecards.map((card) => {
    const pnl = Number(card.total_pnl) || 0;
    const tone = toneClass(pnl);
    const winLossLine = `${formatNumber(card.wins || 0)}W / ${formatNumber(card.losses || 0)}L / ${formatNumber(card.breakevens || 0)} BE`;
    const bestDayValue = card.best_day_label
      ? `${card.best_day_label} · ${formatCurrency(card.best_day_pnl)}`
      : "—";
    const topInstrumentValue = isUsableLabel(card.top_instrument)
      ? `${card.top_instrument} · ${formatCurrency(card.top_instrument_pnl)}`
      : "—";
    const topSetupValue = isUsableLabel(card.top_setup_grade)
      ? `${card.top_setup_grade} · ${formatCurrency(card.top_setup_grade_pnl)}`
      : "—";
    const aggregateOnlyLine = card.aggregate_only_trade_count
      ? `<span class="scorecard-pill aggregate-pill">+ ${formatNumber(card.aggregate_only_trade_count)} aggregate-only trades</span>`
      : "";
    const aggregateOnlyNote = card.aggregate_only_trade_count
      ? `<div class="scorecard-footnote">Includes ${formatNumber(card.aggregate_only_trade_count)} aggregate-only trades from Daily Results on ${(card.aggregate_only_dates || []).join(", ")}. Win/loss breakdown, setup notes, and drill-down rows still reflect only trade-level journal entries.</div>`
      : "";

    return `
      <article class="scorecard-card ${tone}">
        <div class="scorecard-head">
          <div>
            <div class="scorecard-title">${card.title}</div>
            <div class="scorecard-subtitle">${card.subtitle}</div>
          </div>
          <div class="scorecard-total ${tone}">${formatCurrency(card.total_pnl)}</div>
        </div>
        <div class="scorecard-strip">
          <span class="scorecard-pill">${formatNumber(card.total_trades)} trades</span>
          <span class="scorecard-pill">${formatNumber(card.trading_days)} trading days</span>
          <span class="scorecard-pill">${winLossLine}</span>
          <span class="scorecard-pill">${formatNumber(card.green_days || 0)} green / ${formatNumber(card.red_days || 0)} red</span>
          ${aggregateOnlyLine}
        </div>
        <div class="scorecard-stats">
          <div class="scorecard-stat">
            <span>Win rate</span>
            <strong>${formatPercent(card.win_rate)}</strong>
          </div>
          <div class="scorecard-stat">
            <span>Avg trade</span>
            <strong>${formatCurrency(card.avg_trade)}</strong>
          </div>
          <div class="scorecard-stat">
            <span>Avg R</span>
            <strong>${card.average_r === null ? "—" : formatNumber(card.average_r)}</strong>
          </div>
          <div class="scorecard-stat">
            <span>Profit factor</span>
            <strong>${card.profit_factor === null ? "—" : formatNumber(card.profit_factor)}</strong>
          </div>
        </div>
        <div class="scorecard-notes">
          <div class="scorecard-note">
            <span>Best day</span>
            <strong>${bestDayValue}</strong>
          </div>
          <div class="scorecard-note">
            <span>Top instrument</span>
            <strong>${topInstrumentValue}</strong>
          </div>
          <div class="scorecard-note">
            <span>Best setup</span>
            <strong>${topSetupValue}</strong>
          </div>
        </div>
        ${aggregateOnlyNote}
      </article>
    `;
  }).join("");
}

function buildLineChart(points) {
  if (!points.length) {
    return `<div class="empty-state">No trades match the current filters, so there is no curve to draw yet.</div>`;
  }

  const width = 900;
  const height = 320;
  const padding = { top: 20, right: 20, bottom: 42, left: 56 };
  const values = points.map((point) => Number(point.cumulative_pnl) || 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const coords = points.map((point, index) => {
    const x = padding.left + (innerWidth * index) / Math.max(points.length - 1, 1);
    const y = padding.top + ((max - point.cumulative_pnl) / range) * innerHeight;
    return { x, y, point };
  });

  const linePath = coords
    .map((coord, index) => `${index === 0 ? "M" : "L"} ${coord.x.toFixed(1)} ${coord.y.toFixed(1)}`)
    .join(" ");
  const areaPath = `${linePath} L ${coords.at(-1).x.toFixed(1)} ${(height - padding.bottom).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(height - padding.bottom).toFixed(1)} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = padding.top + innerHeight * ratio;
    const value = max - range * ratio;
    return { y, value };
  });

  const firstDate = points[0].date;
  const lastDate = points.at(-1).date;
  const tickLines = ticks.map((tick) => `
    <g>
      <line class="chart-grid-line" x1="${padding.left}" y1="${tick.y}" x2="${width - padding.right}" y2="${tick.y}"></line>
      <text class="chart-axis-label" x="4" y="${tick.y + 4}">${formatCurrency(tick.value)}</text>
    </g>
  `).join("");
  const dots = coords.map((coord) => `
    <circle class="chart-dot" cx="${coord.x}" cy="${coord.y}" r="4.5">
      <title>${coord.point.date}: ${formatCurrency(coord.point.cumulative_pnl)}</title>
    </circle>
  `).join("");

  return `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Equity curve">
      ${tickLines}
      <path class="chart-fill-path" d="${areaPath}"></path>
      <path class="chart-line-path" d="${linePath}"></path>
      ${dots}
      <text class="chart-axis-label" x="${padding.left}" y="${height - 12}">${firstDate}</text>
      <text class="chart-axis-label" x="${width - padding.right}" y="${height - 12}" text-anchor="end">${lastDate}</text>
    </svg>
  `;
}

function renderMetricBars(container, rows, emptyMessage) {
  const visibleRows = filterUsableRows(rows);
  if (!visibleRows.length) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  const maxMagnitude = Math.max(...visibleRows.map((row) => Math.abs(Number(row.pnl) || 0)), 1);
  container.innerHTML = "";
  visibleRows.forEach((row) => {
    const pnl = Number(row.pnl) || 0;
    const width = Math.max((Math.abs(pnl) / maxMagnitude) * 100, 4);
    const tone = toneClass(pnl);
    const node = document.createElement("div");
    node.className = "metric-row";
    node.innerHTML = `
      <div class="metric-label-row">
        <div class="metric-label">${row.label}</div>
        <div class="metric-value ${tone}">${formatCurrency(pnl)}</div>
      </div>
      <div class="metric-track">
        <div class="metric-bar ${tone}" style="width: ${width}%"></div>
      </div>
      <div class="metric-meta">${row.count} trades${row.win_rate !== undefined ? `, ${formatPercent(row.win_rate)} win rate` : ""}${row.avg_pnl !== undefined ? `, ${formatSignedCurrency(row.avg_pnl)} avg` : ""}</div>
    `;
    container.appendChild(node);
  });
}

function renderRecentTrades(trades) {
  if (!trades.length) {
    els.recentTradesBody.innerHTML = `<tr><td colspan="8"><div class="empty-state">No trades match the current filters.</div></td></tr>`;
    return;
  }

  els.recentTradesBody.innerHTML = trades.map((trade) => {
    const tradeName = trade.trade_name || "Untitled trade";
    const pnlClass = toneClass(trade.pnl);
    const resultClass = trade.result === "Win" ? "win" : trade.result === "Loss" ? "loss" : "";
    return `
      <tr>
        <td>${tradeName}</td>
        <td>${trade.trade_date || "—"}</td>
        <td>${displayLabel(trade.instrument)} ${trade.direction ? `<span class="metric-meta">· ${trade.direction}</span>` : ""}</td>
        <td><span class="trade-result ${resultClass}">${trade.result || "—"}</span></td>
        <td><span class="money ${pnlClass}">${formatCurrency(trade.pnl)}</span></td>
        <td>${displayLabel(trade.setup_grade)}</td>
        <td>${displayLabel(trade.trade_window)}</td>
        <td>${displayLabel(trade.emotional_state)}</td>
      </tr>
    `;
  }).join("");
}

function buildPresetDefinitions(payload) {
  const available = payload.filters?.available || {};
  const now = new Date();
  const today = isoDate(now);
  const thisWeekStart = isoDate(startOfWeek(now));
  const last30Start = isoDate(shiftDays(now, -29));
  const definitions = [
    {
      id: "today",
      label: "Today",
      isActive: (active) => active.start_date === today && active.end_date === today,
      apply(active) {
        const alreadyActive = this.isActive(active);
        els.startDate.value = alreadyActive ? "" : today;
        els.endDate.value = alreadyActive ? "" : today;
      },
    },
    {
      id: "this-week",
      label: "This Week",
      isActive: (active) => active.start_date === thisWeekStart && active.end_date === today,
      apply(active) {
        const alreadyActive = this.isActive(active);
        els.startDate.value = alreadyActive ? "" : thisWeekStart;
        els.endDate.value = alreadyActive ? "" : today;
      },
    },
    {
      id: "last-30",
      label: "Last 30D",
      isActive: (active) => active.start_date === last30Start && active.end_date === today,
      apply(active) {
        const alreadyActive = this.isActive(active);
        els.startDate.value = alreadyActive ? "" : last30Start;
        els.endDate.value = alreadyActive ? "" : today;
      },
    },
  ];

  if ((available.account_type || []).includes("Funded")) {
    definitions.push({
      id: "funded",
      label: "Funded",
      isActive: (active) => active.account_type === "Funded",
      apply(active) {
        els.accountTypeSelect.value = active.account_type === "Funded" ? "" : "Funded";
      },
    });
  }

  const preferredGrade = ["A+", "A", "B+"].find((value) => (available.setup_grade || []).includes(value));
  if (preferredGrade) {
    definitions.push({
      id: `grade-${preferredGrade}`,
      label: `${preferredGrade} Setups`,
      isActive: (active) => active.setup_grade === preferredGrade,
      apply(active) {
        els.setupGradeSelect.value = active.setup_grade === preferredGrade ? "" : preferredGrade;
      },
    });
  }

  return definitions;
}

function renderPresetChips(payload) {
  if (!els.presetChips) {
    return;
  }
  presetDefinitions = buildPresetDefinitions(payload);
  const active = payload.filters?.active || {};
  els.presetChips.innerHTML = presetDefinitions.map((preset) => `
    <button type="button" class="preset-chip ${preset.isActive(active) ? "active" : ""}" data-preset="${preset.id}">
      ${preset.label}
    </button>
  `).join("");
}

function scheduleAutoRefresh(payload) {
  if (refreshTimer) {
    window.clearTimeout(refreshTimer);
    refreshTimer = null;
  }

  const autoSync = payload?.source?.auto_sync;
  if (!autoSync?.enabled || !autoSync.interval_seconds) {
    return;
  }

  refreshTimer = window.setTimeout(() => {
    loadDashboard({ silent: true }).catch(showError);
  }, Number(autoSync.interval_seconds) * 1000);
}

function updateSourceStatus(payload) {
  const sourceCount = payload.filters.source_count || 0;
  const resultCount = payload.filters.result_count || 0;
  const knownSourceCount = payload.filters.known_source_count || sourceCount;
  const aggregateSource = payload.aggregate_adjustments?.source || {};
  const mode = payload.source?.mode || "live";
  const autoSync = payload.source?.auto_sync || {};
  const label = payload.source?.label || (
    mode === "demo" ? "Demo dataset" :
    mode === "snapshot" ? "Imported snapshot" :
    "Live data"
  );

  els.sourceMode.textContent = label;
  els.sourceMode.className = `mode-pill ${mode === "demo" ? "demo" : mode === "snapshot" ? "snapshot" : "live"}`;
  els.syncTimestamp.textContent = formatDateTime(payload.generated_at);

  if (mode === "demo") {
    els.sampleCaption.textContent = `${resultCount} records in scope from a ${sourceCount}-record deterministic synthetic dataset.`;
    return;
  }

  const aggregateLine = aggregateSource.trade_count
    ? ` Includes ${formatNumber(aggregateSource.trade_count)} aggregate-only Daily Results trades across ${formatNumber(aggregateSource.day_count)} days.`
    : "";

  if (mode === "snapshot") {
    els.sampleCaption.textContent = `${resultCount} trades in scope from ${formatNumber(knownSourceCount)} imported journal trades.${aggregateLine}`;
    return;
  }

  if (autoSync.enabled) {
    const syncLine = autoSync.last_error
      ? ` Last sync hiccup: ${autoSync.last_error}.`
      : autoSync.last_synced_at
        ? ` Last Notion sync ${formatDateTime(autoSync.last_synced_at)}.`
        : autoSync.is_syncing
          ? " Syncing from Notion now."
          : " Waiting for first Notion sync.";
    els.sampleCaption.textContent = `${resultCount} trades in scope from ${formatNumber(knownSourceCount)} journal trades.${aggregateLine} Auto-sync every ${formatInterval(autoSync.interval_seconds)}.${syncLine}`;
    return;
  }

  els.sampleCaption.textContent = `${resultCount} trades in scope from ${formatNumber(knownSourceCount)} synced journal trades.${aggregateLine}`;
}

async function loadDashboard(options = {}) {
  if (inFlightLoad) {
    return inFlightLoad;
  }

  const { silent = false } = options;
  inFlightLoad = (async () => {
    const params = currentFilters();
    if (!silent) {
      els.syncTimestamp.textContent = "Refreshing command center...";
      els.sampleCaption.textContent = "Pulling the latest dashboard snapshot.";
      els.pulseSubhead.textContent = "Refreshing live performance stats...";
    }

    const activeFilters = currentActiveFiltersFromInputs();
    const payload = await fetchDashboardPayload(activeFilters);
    latestPayload = payload;
    populateFilters(payload);
    renderPresetChips(payload);
    updateSourceStatus(payload);
    renderCommandCenter(payload);
    renderRecentTradeSpotlight(payload.recent_trades || []);
    renderSummary(payload);
    renderHighlights(payload.highlights || []);
    renderScorecards(
      els.weeklyScorecards,
      payload.scorecards?.weekly || [],
      "No weekly scorecards yet for the current filter set.",
    );
    renderScorecards(
      els.monthlyScorecards,
      payload.scorecards?.monthly || [],
      "No monthly scorecards yet for the current filter set.",
    );
    els.equityCurve.innerHTML = buildLineChart(payload.charts?.equity_curve || []);
    renderMetricBars(els.instrumentChart, payload.charts?.by_instrument || [], "No instrument data yet.");
    renderMetricBars(els.tradeWindowChart, payload.charts?.by_trade_window || [], "No trade-window data yet.");
    renderMetricBars(els.setupGradeChart, payload.charts?.by_setup_grade || [], "No setup-grade data yet.");
    renderMetricBars(els.emotionChart, payload.charts?.by_emotional_state || [], "No emotional-state data yet.");
    renderMetricBars(els.weekdayChart, payload.charts?.weekday_performance || [], "No weekday data yet.");
    renderMetricBars(els.disciplineChart, payload.charts?.discipline_flags || [], "No discipline flags have been logged yet.");
    renderRecentTrades(payload.recent_trades || []);

    const equity = payload.charts?.equity_curve || [];
    if (equity.length) {
      const first = equity[0];
      const last = equity.at(-1);
      els.equityCaption.textContent = `${equity.length} trading days from ${first.date} to ${last.date}.`;
    } else {
      els.equityCaption.textContent = "No curve available for the current filter set.";
    }

    runtimeOptions.onPayload?.(payload);
    scheduleAutoRefresh(payload);
    return payload;
  })().finally(() => {
    inFlightLoad = null;
  });

  return inFlightLoad;
}

function resetFilters() {
  els.filtersForm.reset();
  loadDashboard().catch(showError);
}

function showError(error) {
  console.error(error);
  if (refreshTimer) {
    window.clearTimeout(refreshTimer);
    refreshTimer = null;
  }

  els.sourceMode.textContent = "Unavailable";
  els.sourceMode.className = "mode-pill";
  els.syncTimestamp.textContent = "Could not load dashboard";
  els.sampleCaption.textContent = error.message;
  els.pulseHeadline.textContent = runtimeOptions.errorTitle;
  els.pulseSubhead.textContent = error.message;
  els.pulseBadges.innerHTML = "";
  els.pulseSparkline.innerHTML = `<div class="compact-empty">No pulse sparkline available.</div>`;
  els.pulseMetrics.innerHTML = `<div class="empty-state">The analytics dashboard could not load.</div>`;
  els.bestInsight.textContent = "No edge note available.";
  els.leakInsight.textContent = "No leak note available.";
  els.focusInsight.textContent = "No focus note available.";
  els.deskTradesInView.textContent = "—";
  els.deskScope.textContent = "No filter scope";
  els.deskProfitFactor.textContent = "—";
  els.deskDrawdown.textContent = "—";
  els.reviewNote.textContent = "Check the dashboard data source and try again.";
  els.riskNote.textContent = "No risk note available.";
  els.recentTradeSpotlight.innerHTML = `<div class="empty-state">No recent trade snapshot is available.</div>`;
  els.summaryGrid.innerHTML = `<div class="empty-state">The dashboard could not load. Check your data source and try again.</div>`;
  els.weeklyScorecards.innerHTML = `<div class="empty-state">No scorecards available.</div>`;
  els.monthlyScorecards.innerHTML = `<div class="empty-state">No scorecards available.</div>`;
  els.equityCurve.innerHTML = `<div class="empty-state">No chart available.</div>`;
  els.highlightsList.innerHTML = `<div class="empty-state">No highlights available.</div>`;
  [
    els.instrumentChart,
    els.tradeWindowChart,
    els.setupGradeChart,
    els.emotionChart,
    els.weekdayChart,
    els.disciplineChart,
  ].forEach((node) => {
    node.innerHTML = `<div class="empty-state">No data available.</div>`;
  });
  els.recentTradesBody.innerHTML = "";
  runtimeOptions.onError?.(error);
}

function bindEvents() {
  if (eventsBound) {
    return;
  }
  eventsBound = true;

  els.filtersForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadDashboard().catch(showError);
  });

  els.resetFilters?.addEventListener("click", resetFilters);

  els.presetChips?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-preset]");
    if (!button) {
      return;
    }

    const preset = presetDefinitions.find((item) => item.id === button.dataset.preset);
    if (!preset) {
      return;
    }

    preset.apply(currentActiveFiltersFromInputs());
    loadDashboard().catch(showError);
  });
}

export function createDashboardApp(options = {}) {
  runtimeOptions = {
    ...runtimeOptions,
    ...options,
  };
  bindEvents();
  return {
    start() {
      return loadDashboard().catch(showError);
    },
    loadDashboard(options = {}) {
      return loadDashboard(options).catch(showError);
    },
    getPayload() {
      return latestPayload;
    },
    getFilters() {
      return currentActiveFiltersFromInputs();
    },
    showError,
  };
}

const dashboardApp = createDashboardApp({
  errorTitle: "Dashboard unavailable",
});

dashboardApp.start();
