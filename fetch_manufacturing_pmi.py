from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "manufacturing_pmi_monthly.csv"


def normalize_month(raw_month: pd.Series) -> pd.Series:
    cleaned = (
        raw_month.astype(str)
        .str.replace("年", "-", regex=False)
        .str.replace("月份", "", regex=False)
        .str.replace("月", "", regex=False)
    )
    return pd.to_datetime(cleaned, format="%Y-%m", errors="coerce")


def fetch_manufacturing_pmi(start: str | None = None) -> pd.DataFrame:
    historical = ak.macro_china_pmi_yearly().rename(
        columns={"日期": "release_date", "今值": "manufacturing_pmi"}
    )
    historical_data = historical[["release_date", "manufacturing_pmi"]].copy()
    historical_data["release_date"] = pd.to_datetime(historical_data["release_date"], errors="coerce")
    historical_data["manufacturing_pmi"] = pd.to_numeric(
        historical_data["manufacturing_pmi"], errors="coerce"
    )
    historical_data = historical_data.dropna(subset=["release_date", "manufacturing_pmi"])
    historical_data["month"] = historical_data["release_date"].map(
        lambda date: (date - pd.offsets.MonthBegin(1) if date.day <= 5 else date).to_period("M").to_timestamp()
    )
    historical_data["month_label"] = historical_data["month"].dt.strftime("%Y年%m月份")
    historical_data["source"] = "AKShare macro_china_pmi_yearly / Jin10"

    recent = ak.macro_china_pmi().rename(
        columns={
            "月份": "month_label",
            "制造业-指数": "manufacturing_pmi",
        }
    )
    recent_data = recent[["month_label", "manufacturing_pmi"]].copy()
    recent_data["month"] = normalize_month(recent_data["month_label"])
    recent_data["manufacturing_pmi"] = pd.to_numeric(recent_data["manufacturing_pmi"], errors="coerce")
    recent_data["release_date"] = pd.NaT
    recent_data["source"] = "AKShare macro_china_pmi / Eastmoney"

    data = pd.concat(
        [
            historical_data[["month", "month_label", "manufacturing_pmi", "release_date", "source"]],
            recent_data[["month", "month_label", "manufacturing_pmi", "release_date", "source"]],
        ],
        ignore_index=True,
    )
    data = data.dropna(subset=["month", "manufacturing_pmi"]).drop_duplicates("month", keep="last")
    data = data.sort_values("month")
    if start:
        data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No manufacturing PMI data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly["manufacturing_pmi"].isna()
    monthly["manufacturing_pmi"] = monthly["manufacturing_pmi"].ffill()
    monthly["yoy_growth_pct"] = monthly["manufacturing_pmi"].pct_change(periods=12, fill_method=None) * 100
    monthly = monthly.dropna(subset=["yoy_growth_pct"])
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = monthly["source"].ffill().bfill()

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    result["release_date"] = result["release_date"].dt.strftime("%Y-%m-%d")
    return result[
        ["month", "month_label", "manufacturing_pmi", "yoy_growth_pct", "release_date", "is_filled", "source"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China official manufacturing PMI from AKShare.")
    parser.add_argument("--start", default=None, help="Optional start month; default uses all available months")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    df = fetch_manufacturing_pmi(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
