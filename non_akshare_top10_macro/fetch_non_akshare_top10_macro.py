from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import requests


DEFAULT_OUTPUT_DIR = Path(r"C:\Users\hyf\Desktop\工作\网站爬取宏观数据")
TODAY = pd.Timestamp(date.today())


TE_SERIES = {
    "manufacturing_pmi": {
        "page_slug": "business-confidence",
        "chart_code": "CHBUBCIN",
        "value_column": "manufacturing_pmi",
        "source": "Trading Economics public chart / China NBS Manufacturing PMI",
        "source_url": "https://tradingeconomics.com/china/business-confidence",
    },
    "industrial_value_added_yoy": {
        "page_slug": "industrial-production",
        "chart_code": "CHVAIOY",
        "value_column": "industrial_value_added_yoy_pct",
        "source": "Trading Economics public chart / China Industrial Production",
        "source_url": "https://tradingeconomics.com/china/industrial-production",
    },
    "social_financing": {
        "page_slug": "total-social-financing",
        "chart_code": "CHNTSF",
        "value_column": "social_financing_100m_cny",
        "source": "Trading Economics public chart / China Total Social Financing",
        "source_url": "https://tradingeconomics.com/china/total-social-financing",
    },
    "m1": {
        "page_slug": "money-supply-m1",
        "chart_code": "CHINAMONSUPM1",
        "value_column": "m1_billion_cny",
        "source": "Trading Economics public chart / China Money Supply M1",
        "source_url": "https://tradingeconomics.com/china/money-supply-m1",
    },
    "m2": {
        "page_slug": "money-supply-m2",
        "chart_code": "CHINAMONSUPM2",
        "value_column": "m2_billion_cny",
        "source": "Trading Economics public chart / China Money Supply M2",
        "source_url": "https://tradingeconomics.com/china/money-supply-m2",
    },
    "lpr": {
        "page_slug": "interest-rate",
        "chart_code": "CHLR12M",
        "value_column": "lpr_1y_pct",
        "source": "Trading Economics public chart / China Loan Prime Rate",
        "source_url": "https://tradingeconomics.com/china/interest-rate",
    },
    "cpi_yoy": {
        "page_slug": "inflation-cpi",
        "chart_code": "CNCPIYOY",
        "value_column": "cpi_yoy_pct",
        "source": "Trading Economics public chart / China Inflation Rate",
        "source_url": "https://tradingeconomics.com/china/inflation-cpi",
    },
    "ppi_yoy": {
        "page_slug": "producer-prices-change",
        "chart_code": "CHINAPROPRICHA",
        "value_column": "ppi_yoy_pct",
        "source": "Trading Economics public chart / China Producer Prices Change",
        "source_url": "https://tradingeconomics.com/china/producer-prices-change",
    },
    "fixed_asset_investment_yoy": {
        "page_slug": "fixed-asset-investment",
        "chart_code": "CHINAFIXASSINV",
        "value_column": "fixed_asset_investment_ytd_yoy_pct",
        "source": "Trading Economics public chart / China Fixed Asset Investment",
        "source_url": "https://tradingeconomics.com/china/fixed-asset-investment",
    },
    "exports": {
        "page_slug": "exports",
        "chart_code": "CNFREXPD",
        "value_column": "export_amount_billion_usd",
        "source": "Trading Economics public chart / China Exports",
        "source_url": "https://tradingeconomics.com/china/exports",
    },
}


def default_start() -> pd.Timestamp:
    return (TODAY.replace(day=1) - pd.DateOffset(years=10)).normalize()


def discover_te_endpoint(page_slug: str) -> tuple[str, str, bytes]:
    url = f"https://tradingeconomics.com/china/{page_slug}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    token = re.search(r"TEChartsToken = '([^']+)'", response.text)
    key = re.search(r"TEObfuscationkey = '([^']+)'", response.text)
    datasource = re.search(r"TEChartsDatasource = '([^']+)'", response.text)
    if not token or not key or not datasource:
        raise RuntimeError(f"Unable to discover Trading Economics chart endpoint: {page_slug}")
    return datasource.group(1), token.group(1), key.group(1).encode("utf-8")


def decode_te_payload(encoded_json: str, key: bytes) -> list:
    encrypted = base64.b64decode(encoded_json)
    compressed = bytes(value ^ key[index % len(key)] for index, value in enumerate(encrypted))
    return json.loads(gzip.decompress(compressed).decode("utf-8"))


def fetch_te_series(name: str) -> pd.DataFrame:
    config = TE_SERIES[name]
    datasource, token, key = discover_te_endpoint(config["page_slug"])
    response = requests.get(
        f"{datasource}/economics/{config['chart_code']}",
        params={"span": "max"},
        headers={"x-api-key": token, "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    payload = decode_te_payload(response.json(), key)
    observations = payload[0]["series"][0]["serie"]["data"]
    frame = pd.DataFrame(observations, columns=["value", "timestamp", "reference_date", "date"])
    frame["month"] = pd.to_datetime(frame["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    frame[config["value_column"]] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["month", config["value_column"]])
    frame = frame.sort_values(["month", "timestamp"]).drop_duplicates("month", keep="last")
    frame["source"] = config["source"]
    frame["source_url"] = config["source_url"]
    return frame[["month", config["value_column"], "source", "source_url"]]


def reindex_monthly(frame: pd.DataFrame, value_columns: list[str], start: pd.Timestamp) -> pd.DataFrame:
    frame = frame.sort_values("month").drop_duplicates("month", keep="last")
    frame = frame[frame["month"] <= TODAY]
    frame = frame[frame["month"] >= start]
    if frame.empty:
        raise RuntimeError("No data after start date filter.")
    monthly_index = pd.date_range(frame["month"].min(), frame["month"].max(), freq="MS", name="month")
    monthly = frame.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    for column in ["source", "source_url"]:
        if column in monthly.columns:
            monthly[column] = monthly[column].ffill().bfill()
    return monthly.reset_index()


def add_same_month_yoy(frame: pd.DataFrame, value_column: str, yoy_column: str) -> pd.DataFrame:
    previous = frame[["month", value_column]].copy()
    previous["month"] = previous["month"] + pd.DateOffset(years=1)
    previous = previous.rename(columns={value_column: f"{value_column}_previous_year"})
    result = frame.merge(previous, on="month", how="left")
    result[yoy_column] = (result[value_column] / result[f"{value_column}_previous_year"] - 1.0) * 100
    return result


def save_csv(frame: pd.DataFrame, output: Path, date_column: str = "month") -> None:
    result = frame.copy()
    result[date_column] = pd.to_datetime(result[date_column]).dt.strftime("%Y-%m-%d")
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(result):4d} rows: {output.name} ({result[date_column].min()} to {result[date_column].max()})")


def fetch_manufacturing_pmi(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("manufacturing_pmi")
    return reindex_monthly(frame, ["manufacturing_pmi"], start)


def fetch_industrial_value_added(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("industrial_value_added_yoy")
    return reindex_monthly(frame, ["industrial_value_added_yoy_pct"], start)


def fetch_social_financing(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("social_financing")
    return reindex_monthly(frame, ["social_financing_100m_cny"], start)


def fetch_money_supply_yoy(start: pd.Timestamp) -> pd.DataFrame:
    # Pull one extra year so YoY can be calculated for the requested start month.
    source_start = start - pd.DateOffset(years=1)
    m1 = reindex_monthly(fetch_te_series("m1"), ["m1_billion_cny"], source_start)
    m2 = reindex_monthly(fetch_te_series("m2"), ["m2_billion_cny"], source_start)
    frame = m1.merge(m2, on="month", suffixes=("_m1", "_m2"))
    frame = add_same_month_yoy(frame, "m1_billion_cny", "m1_yoy_pct")
    frame = add_same_month_yoy(frame, "m2_billion_cny", "m2_yoy_pct")
    frame["is_filled"] = frame["is_filled_m1"] | frame["is_filled_m2"]
    frame["source"] = "Trading Economics public chart / China Money Supply M1 and M2"
    frame["source_url"] = "https://tradingeconomics.com/china/money-supply-m1; https://tradingeconomics.com/china/money-supply-m2"
    frame = frame[frame["month"] >= start]
    return frame[
        [
            "month",
            "m1_billion_cny",
            "m1_billion_cny_previous_year",
            "m1_yoy_pct",
            "m2_billion_cny",
            "m2_billion_cny_previous_year",
            "m2_yoy_pct",
            "is_filled",
            "source",
            "source_url",
        ]
    ]


def fetch_lpr(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("lpr")
    return reindex_monthly(frame, ["lpr_1y_pct"], start)


def fetch_cpi_yoy(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("cpi_yoy")
    return reindex_monthly(frame, ["cpi_yoy_pct"], start)


def fetch_ppi_yoy(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("ppi_yoy")
    return reindex_monthly(frame, ["ppi_yoy_pct"], start)


def fetch_fixed_asset_investment_yoy(start: pd.Timestamp) -> pd.DataFrame:
    frame = fetch_te_series("fixed_asset_investment_yoy")
    return reindex_monthly(frame, ["fixed_asset_investment_ytd_yoy_pct"], start)


def fetch_export_amount_yoy(start: pd.Timestamp) -> pd.DataFrame:
    source_start = start - pd.DateOffset(years=1)
    frame = reindex_monthly(fetch_te_series("exports"), ["export_amount_billion_usd"], source_start)
    frame = add_same_month_yoy(frame, "export_amount_billion_usd", "export_amount_yoy_pct")
    frame = frame[frame["month"] >= start]
    return frame[
        [
            "month",
            "export_amount_billion_usd",
            "export_amount_billion_usd_previous_year",
            "export_amount_yoy_pct",
            "is_filled",
            "source",
            "source_url",
        ]
    ]


def fetch_china_long_term_bond_yield(start: pd.Timestamp) -> pd.DataFrame:
    page_url = "https://tradingeconomics.com/china/government-bond-yield"
    datasource, token, key = discover_te_endpoint("government-bond-yield")
    response = requests.get(
        f"{datasource}/markets/GCNY10YR:GOV",
        params={"span": "max"},
        headers={"x-api-key": token, "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    payload = decode_te_payload(response.json(), key)
    observations = payload["series"][0]["data"]
    frame = pd.DataFrame(observations, columns=["timestamp", "china_10y_government_bond_yield_pct", "change_pct", "change_abs"])
    frame["month"] = pd.to_datetime(frame["timestamp"], unit="s", errors="coerce").dt.to_period("M").dt.to_timestamp()
    frame["china_10y_government_bond_yield_pct"] = pd.to_numeric(
        frame["china_10y_government_bond_yield_pct"], errors="coerce"
    )
    frame = frame.dropna(subset=["month", "china_10y_government_bond_yield_pct"])
    frame = frame.sort_values("timestamp").drop_duplicates("month", keep="last")
    frame["source"] = "Trading Economics public market chart / China 10Y Government Bond Yield"
    frame["source_url"] = page_url
    return reindex_monthly(frame, ["china_10y_government_bond_yield_pct"], start)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch top 10 China macro factors from non-AKShare web sources.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start", type=str, default=default_start().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    start = pd.Timestamp(args.start).to_period("M").to_timestamp()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    outputs = [
        ("manufacturing_pmi_monthly.csv", fetch_manufacturing_pmi(start)),
        ("industrial_value_added_yoy_monthly.csv", fetch_industrial_value_added(start)),
        ("social_financing_monthly.csv", fetch_social_financing(start)),
        ("money_supply_m1_m2_yoy_monthly.csv", fetch_money_supply_yoy(start)),
        ("lpr_monthly.csv", fetch_lpr(start)),
        ("cpi_yoy_monthly.csv", fetch_cpi_yoy(start)),
        ("ppi_yoy_monthly.csv", fetch_ppi_yoy(start)),
        ("fixed_asset_investment_yoy_monthly.csv", fetch_fixed_asset_investment_yoy(start)),
        ("export_amount_yoy_monthly.csv", fetch_export_amount_yoy(start)),
        ("china_long_term_government_bond_yield_monthly.csv", fetch_china_long_term_bond_yield(start)),
    ]

    for filename, frame in outputs:
        save_csv(frame, args.output_dir / filename)


if __name__ == "__main__":
    main()
