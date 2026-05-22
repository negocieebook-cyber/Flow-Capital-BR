from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import BASE_DIR, ensure_directories, get_database_path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_db() -> None:
    additions = [
        ("asset_metrics_weekly", "udvr", "real"),
        ("asset_metrics_weekly", "ddvr", "real"),
        ("asset_metrics_weekly", "tape_signal", "text"),
    ]
    with get_connection() as conn:
        for table, col, col_type in additions:
            try:
                conn.execute(f"alter table {table} add column {col} {col_type}")
            except sqlite3.OperationalError:
                pass


def init_db() -> None:
    ensure_directories()
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_db()


def _to_records(rows: pd.DataFrame | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(rows, pd.DataFrame):
        clean = rows.where(pd.notnull(rows), None)
        return clean.to_dict("records")
    return rows


def _upsert(table: str, rows: pd.DataFrame | list[dict[str, Any]], columns: list[str]) -> None:
    records = _to_records(rows)
    if not records:
        return
    placeholders = ", ".join([f":{col}" for col in columns])
    updates = ", ".join([f"{col}=excluded.{col}" for col in columns if col not in {"week_date", "ticker", "sector"}])
    conflict = "(week_date, sector)" if table == "sector_metrics_weekly" else "(week_date, ticker)"
    sql = f"""
        insert into {table} ({", ".join(columns)})
        values ({placeholders})
        on conflict {conflict} do update set {updates}
    """
    with get_connection() as conn:
        conn.executemany(sql, [{col: row.get(col) for col in columns} for row in records])


def insert_asset_prices_weekly(rows: pd.DataFrame | list[dict[str, Any]]) -> None:
    _upsert(
        "asset_prices_weekly",
        rows,
        ["week_date", "ticker", "sector", "open", "high", "low", "close", "volume", "financial_volume", "source"],
    )


def insert_asset_metrics_weekly(rows: pd.DataFrame | list[dict[str, Any]]) -> None:
    _upsert(
        "asset_metrics_weekly",
        rows,
        [
            "week_date",
            "ticker",
            "sector",
            "weekly_return",
            "benchmark_return",
            "relative_return",
            "relative_strength",
            "rs_ratio",
            "rs_momentum",
            "volume_relative",
            "financial_volume",
            "score",
            "quadrant",
            "individual_reading",
            "unusual_volume_label",
            "udvr",
            "ddvr",
            "tape_signal",
        ],
    )


def insert_sector_metrics_weekly(rows: pd.DataFrame | list[dict[str, Any]]) -> None:
    _upsert(
        "sector_metrics_weekly",
        rows,
        [
            "week_date",
            "sector",
            "weekly_return",
            "benchmark_return",
            "relative_return",
            "rs_ratio",
            "rs_momentum",
            "volume_relative",
            "internal_confirmation",
            "confirmed_stocks_count",
            "neutral_stocks_count",
            "divergent_stocks_count",
            "unusual_positive_volume_count",
            "unusual_negative_volume_count",
            "valid_stocks_count",
            "score",
            "quadrant",
            "narrative_label",
            "confirmation_label",
            "concentration_alert",
        ],
    )


def get_asset_history(ticker: str | None = None) -> pd.DataFrame:
    sql = "select * from asset_metrics_weekly"
    params: tuple[Any, ...] = ()
    if ticker:
        sql += " where ticker = ?"
        params = (ticker,)
    sql += " order by week_date"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_sector_history(sector: str | None = None) -> pd.DataFrame:
    sql = "select * from sector_metrics_weekly"
    params: tuple[Any, ...] = ()
    if sector:
        sql += " where sector = ?"
        params = (sector,)
    sql += " order by week_date"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_previous_sector_metrics(week_date: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            select * from sector_metrics_weekly
            where week_date < ?
            and week_date = (select max(week_date) from sector_metrics_weekly where week_date < ?)
            """,
            conn,
            params=(week_date, week_date),
        )


def get_previous_asset_metrics(week_date: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            select * from asset_metrics_weekly
            where week_date < ?
            and week_date = (select max(week_date) from asset_metrics_weekly where week_date < ?)
            """,
            conn,
            params=(week_date, week_date),
        )


def register_report_run(week_date: str, status: str, pdf_path: str | None = None, telegram_sent: int = 0) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "insert into report_runs (week_date, status, pdf_path, telegram_sent) values (?, ?, ?, ?)",
            (week_date, status, pdf_path, telegram_sent),
        )
        return int(cursor.lastrowid)


def register_report_error(week_date: str, error_message: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "insert into report_runs (week_date, status, error_message) values (?, ?, ?)",
            (week_date, "error", error_message),
        )
        return int(cursor.lastrowid)


def mark_telegram_sent(report_run_id: int) -> None:
    with get_connection() as conn:
        conn.execute("update report_runs set telegram_sent = 1 where id = ?", (report_run_id,))
