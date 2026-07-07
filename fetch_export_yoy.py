from __future__ import annotations

import argparse
import re
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "export_amount_yoy_monthly.csv"


def parse_month(label: object) -> pd.Timestamp | pd.NaT:
    match = re.search(r"(\d{4}).*?(\d{1,2})", str(label))
    if not match:
        return pd.NaT
    return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)


def fetch_export_yoy(start: str | None = None) -> pd.DataFrame:
    raw = ak.macro_china_hgjck()
    data = raw.rename(
        columns={
            "月份": "month_label",
            "当月出口额-金额": "export_amount_1000_usd",
            "当月出口额-同比增长": "export_yoy_growth_pct",
        }
    ).copy()

    data["month"] = data["month_label"].map(parse_month)
    data["export_amount_1000_usd"] = pd.to_numeric(data["export_amount_1000_usd"], errors="coerce")
    data["export_yoy_growth_pct"] = pd.to_numeric(data["export_yoy_growth_pct"], errors="coerce")
    data = (
        data.dropna(subset=["month", "export_amount_1000_usd", "export_yoy_growth_pct"])
        .sort_values("month")
        .drop_duplicates("month", keep="last")
    )
    if start:
        data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No export amount YoY data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    value_columns = ["export_amount_1000_usd", "export_yoy_growth_pct"]
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = "AKShare macro_china_hgjck / Eastmoney"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "export_amount_1000_usd",
            "export_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China monthly export amount YoY data.")
    parser.add_argument("--start", default=None, help="Optional start month, for example: 2008-01-01")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_export_yoy(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
