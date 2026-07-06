from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "industrial_value_growth_monthly.csv"


def normalize_month(raw_month: pd.Series) -> pd.Series:
    """Convert strings like '2026年05月份' to month-start timestamps."""
    cleaned = (
        raw_month.astype(str)
        .str.replace("年", "-", regex=False)
        .str.replace("月份", "", regex=False)
        .str.replace("月", "", regex=False)
    )
    return pd.to_datetime(cleaned, format="%Y-%m", errors="coerce")


def fetch_industrial_value(start: str = "2008-01-01") -> pd.DataFrame:
    raw = ak.macro_china_gyzjz()
    raw = raw.rename(
        columns={
            "月份": "month_label",
            "同比增长": "yoy_growth_pct",
            "累计增长": "ytd_growth_pct",
            "发布时间": "publish_date",
        }
    )

    data = raw.copy()
    data["month"] = normalize_month(data["month_label"])
    data["publish_date"] = pd.to_datetime(data["publish_date"], errors="coerce")
    data["yoy_growth_pct"] = pd.to_numeric(data["yoy_growth_pct"], errors="coerce")
    data["ytd_growth_pct"] = pd.to_numeric(data["ytd_growth_pct"], errors="coerce")

    data = data.dropna(subset=["month"]).sort_values("month")
    data = data[data["month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No industrial value growth data returned for the requested range.")

    monthly_index = pd.date_range(
        data["month"].min(),
        data["month"].max(),
        freq="MS",
        name="month",
    )

    data = data.set_index("month")
    monthly = data.reindex(monthly_index)
    monthly["is_filled"] = monthly["yoy_growth_pct"].isna() & monthly["ytd_growth_pct"].isna()
    monthly[["yoy_growth_pct", "ytd_growth_pct"]] = monthly[
        ["yoy_growth_pct", "ytd_growth_pct"]
    ].ffill()
    month_labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(month_labels)
    monthly["source"] = "AKShare macro_china_gyzjz / Eastmoney"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    result["publish_date"] = result["publish_date"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "yoy_growth_pct",
            "ytd_growth_pct",
            "publish_date",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch China industrial value added growth data from AKShare."
    )
    parser.add_argument("--start", default="2008-01-01", help="Start month, default: 2008-01-01")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_industrial_value(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
