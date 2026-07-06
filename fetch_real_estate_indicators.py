from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import akshare as ak
import pandas as pd
import requests


DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "宏观数据爬取"
INVESTMENT_OUTPUT = "real_estate_development_investment_yoy_monthly.csv"
SALES_AREA_OUTPUT = "commercial_housing_sales_area_yoy_monthly.csv"


def parse_month(label: object) -> pd.Timestamp | pd.NaT:
    match = re.search(r"(\d{4}).*?(\d{1,2})", str(label))
    if not match:
        return pd.NaT
    return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)


def select_indicator(raw: pd.DataFrame, keyword: str) -> pd.Series:
    matches = [index for index in raw.index if keyword in str(index)]
    if not matches:
        available = ", ".join(map(str, raw.index))
        raise RuntimeError(f"Indicator containing '{keyword}' was not found. Available: {available}")
    return raw.loc[matches[0]]


def normalize_monthly_indicator(
    series: pd.Series,
    value_column: str,
    source: str,
) -> pd.DataFrame:
    data = pd.DataFrame({"month_label": series.index, value_column: series.values})
    data["month"] = data["month_label"].map(parse_month)
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce")
    data = data.dropna(subset=["month", value_column]).sort_values("month").drop_duplicates("month")
    if data.empty:
        raise RuntimeError(f"No valid data returned for {value_column}.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly[value_column].isna()
    monthly[value_column] = monthly[value_column].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = source

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[["month", "month_label", value_column, "is_filled", "source"]]


def fetch_mapped_indicator(code: str) -> pd.Series:
    url = "https://www.steelx2.com/Handler2022/GetCommodityChartData.ashx"
    response = requests.get(
        url,
        params={"type": "main", "indicesid": code, "cityid": "", "datetype": "Full"},
        headers={"User-Agent": "Mozilla/5.0", "Referer": f"https://www.steelx2.com/indices/{code}"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("Success"):
        raise RuntimeError(f"Mapped indicator {code} returned an error: {payload.get('Msg')}")
    records = json.loads(payload["Data"]["ChartData"])
    data = pd.DataFrame(records)
    return pd.Series(data["Price"].to_numpy(), index=data["PriceDate"], name=code)


def fetch_real_estate_indicators() -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        investment_raw = ak.macro_china_nbs_nation(
            kind="月度数据",
            path="房地产 > 房地产开发投资",
            period="1980-",
        )
        sales_raw = ak.macro_china_nbs_nation(
            kind="月度数据",
            path="房地产 > 房地产施工、销售和待售情况",
            period="1980-",
        )
        investment_series = select_indicator(investment_raw, "房地产开发投资额_累计增长")
        sales_series = select_indicator(sales_raw, "商品房销售面积_累计增长")
        source = "AKShare macro_china_nbs_nation / National Bureau of Statistics"
    except (requests.RequestException, ValueError, KeyError, RuntimeError):
        investment_series = fetch_mapped_indicator("167")
        sales_series = fetch_mapped_indicator("170")
        source = "AKShare built-in indicator mapping 167/170 / SteelX2"

    investment = normalize_monthly_indicator(
        investment_series,
        "real_estate_development_investment_yoy_pct",
        source,
    )
    sales_area = normalize_monthly_indicator(
        sales_series,
        "commercial_housing_sales_area_yoy_pct",
        source,
    )
    return investment, sales_area


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch China real-estate investment and commercial housing sales-area YoY data."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"CSV output directory, default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args()

    investment, sales_area = fetch_real_estate_indicators()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (investment, args.output_dir / INVESTMENT_OUTPUT),
        (sales_area, args.output_dir / SALES_AREA_OUTPUT),
    ]
    for frame, output in outputs:
        frame.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"Saved {len(frame)} rows to {output}")
        print(f"Range: {frame['month'].min()} to {frame['month'].max()}")
        print(f"Filled months: {int(frame['is_filled'].sum())}")


if __name__ == "__main__":
    main()
