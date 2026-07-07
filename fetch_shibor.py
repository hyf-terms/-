from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "shibor_daily.csv"
DEFAULT_START = "2017-03-17"


def fetch_shibor() -> pd.DataFrame:
    raw = ak.macro_china_shibor_all()
    data = raw.rename(
        columns={
            "日期": "date",
            "O/N-定价": "shibor_overnight_pct",
            "1W-定价": "shibor_1w_pct",
            "2W-定价": "shibor_2w_pct",
            "1M-定价": "shibor_1m_pct",
            "3M-定价": "shibor_3m_pct",
            "6M-定价": "shibor_6m_pct",
            "9M-定价": "shibor_9m_pct",
            "1Y-定价": "shibor_1y_pct",
        }
    ).copy()
    value_columns = [
        "shibor_overnight_pct",
        "shibor_1w_pct",
        "shibor_2w_pct",
        "shibor_1m_pct",
        "shibor_3m_pct",
        "shibor_6m_pct",
        "shibor_9m_pct",
        "shibor_1y_pct",
    ]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in value_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = (
        data.dropna(subset=["date", *value_columns])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
    )
    data = data[data["date"] >= pd.Timestamp(DEFAULT_START)]
    if data.empty:
        raise RuntimeError("No SHIBOR data returned.")

    daily_index = pd.date_range(data["date"].min(), data["date"].max(), freq="D", name="date")
    daily = data.set_index("date").reindex(daily_index)
    daily["is_filled"] = daily[value_columns].isna().any(axis=1)
    daily[value_columns] = daily[value_columns].ffill()
    daily["source"] = "AKShare macro_china_shibor_all / Jin10"

    result = daily.reset_index()
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    return result[["date", *value_columns, "is_filled", "source"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China SHIBOR daily data.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path, default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    df = fetch_shibor()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['date'].min()} to {df['date'].max()}")
    print(f"Filled days: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
