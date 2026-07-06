from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "ppi_yoy_monthly.csv"


def fetch_ppi_yoy() -> pd.DataFrame:
    historical = ak.macro_china_ppi_yearly().rename(
        columns={"日期": "release_date", "今值": "ppi_yoy_growth_pct"}
    )
    data = historical[["release_date", "ppi_yoy_growth_pct"]].copy()
    data["release_date"] = pd.to_datetime(data["release_date"], errors="coerce")
    data["ppi_yoy_growth_pct"] = pd.to_numeric(data["ppi_yoy_growth_pct"], errors="coerce")
    data = data.dropna(subset=["release_date", "ppi_yoy_growth_pct"])
    data["month"] = (data["release_date"] - pd.offsets.MonthBegin(1)).dt.to_period("M").dt.to_timestamp()
    data["source"] = "AKShare macro_china_ppi_yearly / Jin10"

    recent = ak.macro_china_ppi().rename(columns={"当月同比增长": "ppi_yoy_growth_pct"})
    recent_data = recent[["月份", "ppi_yoy_growth_pct"]].copy()
    recent_data["month"] = pd.to_datetime(
        recent_data["月份"].astype(str).str.replace("年", "-", regex=False).str.replace("月份", "", regex=False),
        format="%Y-%m",
        errors="coerce",
    )
    recent_data["ppi_yoy_growth_pct"] = pd.to_numeric(recent_data["ppi_yoy_growth_pct"], errors="coerce")
    recent_data["release_date"] = pd.NaT
    recent_data["source"] = "AKShare macro_china_ppi / Eastmoney"
    data = pd.concat(
        [data, recent_data[["month", "release_date", "ppi_yoy_growth_pct", "source"]]],
        ignore_index=True,
    )
    data = data.dropna(subset=["month", "ppi_yoy_growth_pct"]).drop_duplicates("month", keep="last")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly["ppi_yoy_growth_pct"].isna()
    monthly["ppi_yoy_growth_pct"] = monthly["ppi_yoy_growth_pct"].ffill()
    monthly["source"] = monthly["source"].ffill().bfill()

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    result["release_date"] = result["release_date"].dt.strftime("%Y-%m-%d")
    return result[["month", "ppi_yoy_growth_pct", "release_date", "is_filled", "source"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China PPI year-on-year monthly data from AKShare.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()
    df = fetch_ppi_yoy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
