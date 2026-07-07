from __future__ import annotations

import argparse
import re
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "宏观数据爬取"
IMPORT_OUTPUT = "import_amount_yoy_monthly.csv"
TRADE_BALANCE_OUTPUT = "trade_balance_monthly.csv"


def parse_month(label: object) -> pd.Timestamp | pd.NaT:
    match = re.search(r"(\d{4}).*?(\d{1,2})", str(label))
    if not match:
        return pd.NaT
    return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)


def fetch_trade_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = ak.macro_china_hgjck()
    data = raw.rename(
        columns={
            "月份": "month_label",
            "当月出口额-金额": "export_amount_1000_usd",
            "当月出口额-同比增长": "export_yoy_growth_pct",
            "当月进口额-金额": "import_amount_1000_usd",
            "当月进口额-同比增长": "import_yoy_growth_pct",
        }
    ).copy()
    data["month"] = data["month_label"].map(parse_month)
    value_columns = [
        "export_amount_1000_usd",
        "export_yoy_growth_pct",
        "import_amount_1000_usd",
        "import_yoy_growth_pct",
    ]
    for column in value_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = (
        data.dropna(subset=["month", *value_columns])
        .sort_values("month")
        .drop_duplicates("month", keep="last")
    )
    if data.empty:
        raise RuntimeError("No import/export data returned.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["trade_balance_1000_usd"] = (
        monthly["export_amount_1000_usd"] - monthly["import_amount_1000_usd"]
    )
    monthly["source"] = "AKShare macro_china_hgjck / Eastmoney"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    import_frame = result[
        [
            "month",
            "month_label",
            "import_amount_1000_usd",
            "import_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]
    balance_frame = result[
        [
            "month",
            "month_label",
            "export_amount_1000_usd",
            "import_amount_1000_usd",
            "trade_balance_1000_usd",
            "export_yoy_growth_pct",
            "import_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]
    return import_frame, balance_frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China import YoY and trade balance data.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"CSV output directory, default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args()

    import_frame, balance_frame = fetch_trade_data()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (import_frame, args.output_dir / IMPORT_OUTPUT),
        (balance_frame, args.output_dir / TRADE_BALANCE_OUTPUT),
    ]
    for frame, output in outputs:
        frame.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"Saved {len(frame)} rows to {output}")
        print(f"Range: {frame['month'].min()} to {frame['month'].max()}")
        print(f"Filled months: {int(frame['is_filled'].sum())}")


if __name__ == "__main__":
    main()
