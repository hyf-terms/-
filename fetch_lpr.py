from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "lpr_monthly.csv"


def fetch_lpr(start: str | None = None) -> pd.DataFrame:
    raw = ak.macro_china_lpr()
    data = raw.rename(
        columns={
            "TRADE_DATE": "trade_date",
            "LPR1Y": "lpr_1y_pct",
            "LPR5Y": "lpr_5y_pct",
        }
    ).copy()

    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce")
    data["month"] = data["trade_date"].dt.to_period("M").dt.to_timestamp()
    data["lpr_1y_pct"] = pd.to_numeric(data["lpr_1y_pct"], errors="coerce")
    data["lpr_5y_pct"] = pd.to_numeric(data["lpr_5y_pct"], errors="coerce")
    data = (
        data.dropna(subset=["month", "lpr_1y_pct", "lpr_5y_pct"])
        .sort_values("trade_date")
        .drop_duplicates("month", keep="last")
    )
    if start:
        data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No complete LPR data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    value_columns = ["lpr_1y_pct", "lpr_5y_pct"]
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    monthly["source"] = "AKShare macro_china_lpr / National Interbank Funding Center"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    result["trade_date"] = result["trade_date"].dt.strftime("%Y-%m-%d")
    return result[["month", "trade_date", "lpr_1y_pct", "lpr_5y_pct", "is_filled", "source"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China LPR monthly data.")
    parser.add_argument("--start", default=None, help="Optional start month, for example: 2019-08-01")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_lpr(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
