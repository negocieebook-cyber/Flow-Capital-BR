create table if not exists asset_prices_weekly (
  id integer primary key autoincrement,
  week_date text not null,
  ticker text not null,
  sector text,
  open real,
  high real,
  low real,
  close real,
  volume real,
  financial_volume real,
  source text,
  created_at text default current_timestamp,
  unique (week_date, ticker)
);

create table if not exists asset_metrics_weekly (
  id integer primary key autoincrement,
  week_date text not null,
  ticker text not null,
  sector text,
  weekly_return real,
  benchmark_return real,
  relative_return real,
  relative_strength real,
  rs_ratio real,
  rs_momentum real,
  volume_relative real,
  financial_volume real,
  score real,
  quadrant text,
  individual_reading text,
  unusual_volume_label text,
  udvr real,
  ddvr real,
  tape_signal text,
  created_at text default current_timestamp,
  unique (week_date, ticker)
);

create table if not exists sector_metrics_weekly (
  id integer primary key autoincrement,
  week_date text not null,
  sector text not null,
  weekly_return real,
  benchmark_return real,
  relative_return real,
  rs_ratio real,
  rs_momentum real,
  volume_relative real,
  internal_confirmation real,
  confirmed_stocks_count integer,
  neutral_stocks_count integer,
  divergent_stocks_count integer,
  unusual_positive_volume_count integer,
  unusual_negative_volume_count integer,
  valid_stocks_count integer,
  score real,
  quadrant text,
  narrative_label text,
  confirmation_label text,
  concentration_alert text,
  created_at text default current_timestamp,
  unique (week_date, sector)
);

create table if not exists report_runs (
  id integer primary key autoincrement,
  week_date text not null,
  status text not null,
  pdf_path text,
  telegram_sent integer default 0,
  error_message text,
  created_at text default current_timestamp
);
