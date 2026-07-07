from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "china_treasury_yield_daily.csv"
DEFAULT_START = "2010-01-01"


def iter_yearly_windows(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[str, str]]:
    windows: list[tuple[str, str]] = []
    current = start
    while current <= end:
        window_end = min(current + pd.DateOffset(months=11, days=27), end)
        windows.append((current.strftime("%Y%m%d"), window_end.strftime("%Y%m%d")))
        current = window_end + pd.DateOffset(days=1)
    return windows


def fetch_china_treasury_yield(start: str = DEFAULT_START, end: str | None = None) -> pd.DataFrame:
    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end) if end else pd.Timestamp(datetime.now().date())
    frames = []
    for window_start, window_end in iter_yearly_windows(start_date, end_date):
        chunk = ak.bond_china_yield(start_date=window_start, end_date=window_end)
        frames.append(chunk)
    raw = pd.concat(frames, ignore_index=True)
    data = raw[raw["曲线名称"].astype(str).eq("中债国债收益率曲线")].rename(
        columns={
            "日期": "date",
            "3月": "treasury_3m_yield_pct",
            "6月": "treasury_6m_yield_pct",
            "1年": "treasury_1y_yield_pct",
            "3年": "treasury_3y_yield_pct",
            "5年": "treasury_5y_yield_pct",
            "7年": "treasury_7y_yield_pct",
            "10年": "treasury_10y_yield_pct",
            "30年": "treasury_30y_yield_pct",
        }
    ).copy()
    value_columns = [
        "treasury_3m_yield_pct",
        "treasury_6m_yield_pct",
        "treasury_1y_yield_pct",
        "treasury_3y_yield_pct",
        "treasury_5y_yield_pct",
        "treasury_7y_yield_pct",
        "treasury_10y_yield_pct",
        "treasury_30y_yield_pct",
    ]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in value_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = (
        data.dropna(subset=["date", *value_columns])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
    )
    if data.empty:
        raise RuntimeError("No China treasury yield data returned.")

    daily_index = pd.date_range(data["date"].min(), data["date"].max(), freq="D", name="date")
    daily = data.set_index("date").reindex(daily_index)
    daily["is_filled"] = daily[value_columns].isna().any(axis=1)
    daily[value_columns] = daily[value_columns].ffill()
    daily["term_spread_10y_1y_pct"] = daily["treasury_10y_yield_pct"] - daily["treasury_1y_yield_pct"]
    daily["source"] = "AKShare bond_china_yield / ChinaBond"

    result = daily.reset_index()
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    return result[["date", *value_columns, "term_spread_10y_1y_pct", "is_filled", "source"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China treasury yield curve data.")
    parser.add_argument("--start", default=DEFAULT_START, help=f"Start date, default: {DEFAULT_START}")
    parser.add_argument("--end", default=None, help="Optional end date, for example: 2026-07-07")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_china_treasury_yield(start=args.start, end=args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['date'].min()} to {df['date'].max()}")
    print(f"Filled days: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
