-- Private operational schema. Apply only to a protected Supabase/PostgreSQL project.
-- Keep row-level security enabled and access this table with server-side credentials;
-- the public demo intentionally does not grant anonymous or browser access.
create table if not exists public.trade_journal_trades (
  notion_page_id uuid primary key,
  notion_page_url text not null,
  notion_created_time timestamptz,
  notion_last_edited_time timestamptz,
  synced_at timestamptz not null default timezone('utc', now()),
  trade_name text,
  trade_date date,
  instrument text,
  direction text,
  account_type text,
  account_label text,
  entry_time timestamptz,
  exit_time timestamptz,
  trade_window text,
  entry_price numeric,
  exit_price numeric,
  stop_price numeric,
  target_price numeric,
  contracts numeric,
  hold_minutes integer,
  result text,
  pnl numeric,
  realized_r numeric,
  planned_r numeric,
  moved_to_be boolean,
  partials_taken boolean,
  bias_4h text,
  bias_1h text,
  htf_bias_aligned boolean,
  htf_fvg_timeframe text,
  htf_fvg_respected boolean,
  itm_sweep_occurred boolean,
  sweep_inside_gap boolean,
  target_draw text,
  ltf_trigger_timeframe text,
  inverse_fvg_formed boolean,
  inverse_fvg_clean boolean,
  market_structure_flip_present boolean,
  a_plus_setup boolean,
  setup_grade text,
  suboptimal_conditions boolean,
  forced_trade boolean,
  doubled_down boolean,
  overtraded boolean,
  size_appropriate boolean,
  rule_break_severity text,
  stop_placement_valid boolean,
  target_placement_valid boolean,
  be_timing text,
  exit_quality text,
  confidence integer,
  clarity integer,
  patience integer,
  emotional_state text,
  hesitated boolean,
  chased boolean,
  entry_rationale text,
  what_went_well text,
  what_went_wrong text,
  lesson text,
  next_time_rule text,
  coach_feedback text,
  screenshot_name text,
  screenshot_url text,
  screenshot_source text,
  screenshot_expiry_time timestamptz,
  raw_notion_page jsonb
);

create index if not exists trade_journal_trades_trade_date_idx
  on public.trade_journal_trades (trade_date desc);

create index if not exists trade_journal_trades_entry_time_idx
  on public.trade_journal_trades (entry_time desc);

create index if not exists trade_journal_trades_instrument_idx
  on public.trade_journal_trades (instrument);

create index if not exists trade_journal_trades_setup_grade_idx
  on public.trade_journal_trades (setup_grade);

create index if not exists trade_journal_trades_result_idx
  on public.trade_journal_trades (result);

alter table public.trade_journal_trades enable row level security;
