from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "money_supply_yoy_monthly.csv"


def normalize_month(raw_month: pd.Series) -> pd.Series:
    cleaned = (
        raw_month.astype(str)
        .str.replace("年", "-", regex=False)
        .str.replace("月份", "", regex=False)
        .str.replace("月", "", regex=False)
    )
    return pd.to_datetime(cleaned, format="%Y-%m", errors="coerce")


def fetch_money_supply_yoy(start: str = "2008-01-01") -> pd.DataFrame:
    raw = ak.macro_china_money_supply().rename(
        columns={
            "月份": "month_label",
            "货币(M1)-同比增长": "m1_yoy_growth_pct",
            "货币和准货币(M2)-同比增长": "m2_yoy_growth_pct",
        }
    )

    data = raw[["month_label", "m1_yoy_growth_pct", "m2_yoy_growth_pct"]].copy()
    data["month"] = normalize_month(data["month_label"])
    data["m1_yoy_growth_pct"] = pd.to_numeric(data["m1_yoy_growth_pct"], errors="coerce")
    data["m2_yoy_growth_pct"] = pd.to_numeric(data["m2_yoy_growth_pct"], errors="coerce")
    data = data.dropna(subset=["month"]).sort_values("month")
    data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No M1 or M2 year-on-year data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    growth_columns = ["m1_yoy_growth_pct", "m2_yoy_growth_pct"]
    monthly["is_filled"] = monthly[growth_columns].isna().any(axis=1)
    monthly[growth_columns] = monthly[growth_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = "AKShare macro_china_money_supply / Eastmoney"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "m1_yoy_growth_pct",
            "m2_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China M1 and M2 year-on-year monthly data from AKShare.")
    parser.add_argument("--start", default="2008-01-01", help="Start month, default: 2008-01-01")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    df = fetch_money_supply_yoy(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
