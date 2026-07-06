from __future__ import annotations

import argparse
import re
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "gdp_yoy_quarterly.csv"


def parse_quarter_label(label: object) -> tuple[pd.Timestamp, int] | tuple[pd.NaT, None]:
    match = re.fullmatch(r"(\d{4})年第1(?:-(\d))?季度", str(label).strip())
    if not match:
        return pd.NaT, None
    year = int(match.group(1))
    quarter = int(match.group(2) or 1)
    return pd.Timestamp(year=year, month=quarter * 3, day=1), quarter


def fetch_gdp_yoy(start: str = "2008-01-01") -> pd.DataFrame:
    raw = ak.macro_china_gdp().rename(
        columns={
            "季度": "quarter_label",
            "国内生产总值-同比增长": "gdp_yoy_growth_pct",
        }
    )
    data = raw[["quarter_label", "gdp_yoy_growth_pct"]].copy()
    parsed = data["quarter_label"].map(parse_quarter_label)
    data["quarter_end_month"] = [item[0] for item in parsed]
    data["quarter"] = [item[1] for item in parsed]
    data["gdp_yoy_growth_pct"] = pd.to_numeric(data["gdp_yoy_growth_pct"], errors="coerce")
    data = data.dropna(subset=["quarter_end_month"]).sort_values("quarter_end_month")
    data = data[data["quarter_end_month"] >= pd.Timestamp(start)]
    if data.empty:
        raise RuntimeError("No GDP year-on-year data returned for the requested range.")

    quarter_index = pd.date_range(
        data["quarter_end_month"].min(), data["quarter_end_month"].max(), freq="3MS", name="quarter_end_month"
    )
    quarterly = data.set_index("quarter_end_month").reindex(quarter_index)
    quarterly["is_filled"] = quarterly["gdp_yoy_growth_pct"].isna()
    quarterly["gdp_yoy_growth_pct"] = quarterly["gdp_yoy_growth_pct"].ffill()
    quarterly["quarter"] = quarterly.index.quarter
    labels = pd.Series(
        [f"{date.year}年第1-{date.quarter}季度" if date.quarter > 1 else f"{date.year}年第1季度" for date in quarterly.index],
        index=quarterly.index,
    )
    quarterly["quarter_label"] = quarterly["quarter_label"].fillna(labels)
    quarterly["source"] = "AKShare macro_china_gdp / Eastmoney"

    result = quarterly.reset_index()
    result["quarter_end_month"] = result["quarter_end_month"].dt.strftime("%Y-%m-%d")
    return result[
        ["quarter_end_month", "quarter_label", "quarter", "gdp_yoy_growth_pct", "is_filled", "source"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China GDP year-on-year quarterly data from AKShare.")
    parser.add_argument("--start", default="2008-01-01", help="Start date, default: 2008-01-01")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    df = fetch_gdp_yoy(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['quarter_end_month'].min()} to {df['quarter_end_month'].max()}")
    print(f"Filled quarters: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
