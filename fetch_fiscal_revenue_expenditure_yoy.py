from __future__ import annotations

import argparse
import re
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "fiscal_revenue_expenditure_yoy_monthly.csv"


def parse_month(label: object) -> pd.Timestamp | pd.NaT:
    match = re.search(r"(\d{4}).*?(\d{1,2})", str(label))
    if not match:
        return pd.NaT
    return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)


def fetch_fiscal_revenue() -> pd.DataFrame:
    raw = ak.macro_china_czsr()
    data = raw.rename(
        columns={
            "月份": "month_label",
            "当月": "fiscal_revenue_monthly_100m_cny",
            "当月-同比增长": "fiscal_revenue_monthly_yoy_pct",
            "累计": "fiscal_revenue_ytd_100m_cny",
            "累计-同比增长": "fiscal_revenue_ytd_yoy_pct",
        }
    ).copy()
    data["month"] = data["month_label"].map(parse_month)
    value_columns = [
        "fiscal_revenue_monthly_100m_cny",
        "fiscal_revenue_monthly_yoy_pct",
        "fiscal_revenue_ytd_100m_cny",
        "fiscal_revenue_ytd_yoy_pct",
    ]
    for column in value_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = (
        data.dropna(subset=["month", "fiscal_revenue_ytd_100m_cny", "fiscal_revenue_ytd_yoy_pct"])
        .sort_values("month")
        .drop_duplicates("month", keep="last")
    )
    if data.empty:
        raise RuntimeError("No fiscal revenue data returned.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = "AKShare macro_china_czsr / Eastmoney; expenditure not exposed by stable AKShare source"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "fiscal_revenue_monthly_100m_cny",
            "fiscal_revenue_monthly_yoy_pct",
            "fiscal_revenue_ytd_100m_cny",
            "fiscal_revenue_ytd_yoy_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China fiscal revenue YoY data.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_fiscal_revenue()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
