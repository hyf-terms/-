from __future__ import annotations

import argparse
import re
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "fixed_asset_investment_yoy_monthly.csv"


def parse_month(label: object) -> pd.Timestamp | pd.NaT:
    match = re.search(r"(\d{4}).*?(\d{1,2})", str(label))
    if not match:
        return pd.NaT
    return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)


def fetch_fixed_asset_investment_yoy(start: str | None = None) -> pd.DataFrame:
    raw = ak.macro_china_gdzctz()
    data = raw.rename(
        columns={
            "月份": "month_label",
            "自年初累计": "fixed_asset_investment_ytd_100m_cny",
        }
    ).copy()
    data["month"] = data["month_label"].map(parse_month)
    data["fixed_asset_investment_ytd_100m_cny"] = pd.to_numeric(
        data["fixed_asset_investment_ytd_100m_cny"], errors="coerce"
    )

    data = (
        data.dropna(subset=["month", "fixed_asset_investment_ytd_100m_cny"])
        .sort_values("month")
        .drop_duplicates("month", keep="last")
    )
    if data.empty:
        raise RuntimeError("No fixed asset investment data returned.")

    previous_year = data[["month", "fixed_asset_investment_ytd_100m_cny"]].copy()
    previous_year["month"] = previous_year["month"] + pd.DateOffset(years=1)
    previous_year = previous_year.rename(
        columns={"fixed_asset_investment_ytd_100m_cny": "previous_year_ytd_100m_cny"}
    )
    data = data.merge(previous_year, on="month", how="left")
    data["ytd_yoy_growth_pct"] = (
        data["fixed_asset_investment_ytd_100m_cny"] / data["previous_year_ytd_100m_cny"] - 1
    ) * 100
    data = data.dropna(subset=["ytd_yoy_growth_pct"])
    if start:
        data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No fixed asset investment YoY data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    value_columns = ["fixed_asset_investment_ytd_100m_cny", "ytd_yoy_growth_pct"]
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = "AKShare macro_china_gdzctz / Eastmoney"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "fixed_asset_investment_ytd_100m_cny",
            "ytd_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China fixed asset investment YoY data.")
    parser.add_argument("--start", default=None, help="Optional start month, for example: 2009-02-01")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_fixed_asset_investment_yoy(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
