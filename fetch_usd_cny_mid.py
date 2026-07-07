from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "usd_cny_mid_daily.csv"
DEFAULT_START = "2019-01-01"


def fetch_usd_cny_mid(start: str | None = DEFAULT_START, years: int | None = None) -> pd.DataFrame:
    raw = ak.currency_boc_safe()
    data = raw.rename(columns={"日期": "date", "美元": "usd_cny_mid_per_100_usd"}).copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["usd_cny_mid_per_100_usd"] = pd.to_numeric(
        data["usd_cny_mid_per_100_usd"], errors="coerce"
    )
    data = (
        data.dropna(subset=["date", "usd_cny_mid_per_100_usd"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
    )
    if data.empty:
        raise RuntimeError("No USD/CNY official central parity data returned.")

    end_date = data["date"].max()
    start_date = pd.Timestamp(start) if start else end_date - pd.DateOffset(years=years or 5)
    data = data[data["date"] >= start_date]
    if data.empty:
        raise RuntimeError("No USD/CNY official central parity data returned for the requested range.")

    daily_index = pd.date_range(data["date"].min(), data["date"].max(), freq="D", name="date")
    daily = data.set_index("date").reindex(daily_index)
    daily["is_filled"] = daily["usd_cny_mid_per_100_usd"].isna()
    daily["usd_cny_mid_per_100_usd"] = daily["usd_cny_mid_per_100_usd"].ffill()
    daily["usd_cny_mid"] = daily["usd_cny_mid_per_100_usd"] / 100
    daily["daily_change_pct"] = daily["usd_cny_mid"].pct_change(fill_method=None) * 100
    daily["daily_change_pct"] = daily["daily_change_pct"].fillna(0.0)
    daily["source"] = "AKShare currency_boc_safe / SAFE official central parity"

    result = daily.reset_index()
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "date",
            "usd_cny_mid",
            "usd_cny_mid_per_100_usd",
            "daily_change_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch official USD/CNY central parity data.")
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help=f"Start date, default: {DEFAULT_START}",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=None,
        help="Lookback years when --start is empty, for example: --start '' --years 5",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_usd_cny_mid(start=args.start, years=args.years)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['date'].min()} to {df['date'].max()}")
    print(f"Filled days: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
