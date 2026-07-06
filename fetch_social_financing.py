from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from pathlib import Path

import akshare as ak
import pandas as pd
import requests


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "social_financing_monthly.csv"


def normalize_month(raw_month: pd.Series) -> pd.Series:
    text = raw_month.astype(str).str.strip()
    compact = pd.to_datetime(text, format="%Y%m", errors="coerce")
    dotted = pd.to_datetime(text, format="%Y.%m", errors="coerce")
    return compact.fillna(dotted).dt.to_period("M").dt.to_timestamp()


def fetch_akshare_social_financing() -> pd.DataFrame:
    raw = ak.macro_china_shrzgm().rename(
        columns={"月份": "month_label", "社会融资规模增量": "social_financing_flow_100m_cny"}
    )
    data = raw[["month_label", "social_financing_flow_100m_cny"]].copy()
    data["month"] = normalize_month(data["month_label"])
    data["social_financing_flow_100m_cny"] = pd.to_numeric(
        data["social_financing_flow_100m_cny"], errors="coerce"
    )
    data = data.dropna(subset=["month", "social_financing_flow_100m_cny"])
    data["source"] = "AKShare macro_china_shrzgm / MOFCOM"
    return data[["month", "social_financing_flow_100m_cny", "source"]]


def fetch_fallback_social_financing() -> pd.DataFrame:
    page_url = "https://zh.tradingeconomics.com/china/total-social-financing"
    headers = {"User-Agent": "Mozilla/5.0"}
    page = requests.get(page_url, headers=headers, timeout=30)
    page.raise_for_status()
    token = re.search(r"TEChartsToken = '([^']+)'", page.text)
    key = re.search(r"TEObfuscationkey = '([^']+)'", page.text)
    datasource = re.search(r"TEChartsDatasource = '([^']+)'", page.text)
    if not token or not key or not datasource:
        raise RuntimeError("Unable to discover the public social-financing chart endpoint.")

    chart = requests.get(
        f"{datasource.group(1)}/economics/chntsf",
        params={"span": "max"},
        headers={"x-api-key": token.group(1), "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    chart.raise_for_status()
    encrypted = base64.b64decode(chart.json())
    key_bytes = key.group(1).encode("utf-8")
    compressed = bytes(value ^ key_bytes[index % len(key_bytes)] for index, value in enumerate(encrypted))
    payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
    observations = payload[0]["series"][0]["serie"]["data"]

    data = pd.DataFrame(observations, columns=["y", "timestamp", "reference_date", "date"])
    data["month"] = pd.to_datetime(data["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    data["social_financing_flow_100m_cny"] = pd.to_numeric(data["y"], errors="coerce")
    data = data.dropna(subset=["month", "social_financing_flow_100m_cny"])
    data["source"] = "PBOC via Trading Economics public chart (AKShare fallback)"
    return data[["month", "social_financing_flow_100m_cny", "source"]]


def fetch_social_financing() -> pd.DataFrame:
    try:
        data = fetch_akshare_social_financing()
    except (requests.RequestException, ValueError, KeyError, RuntimeError):
        data = fetch_fallback_social_financing()
    data = data.sort_values("month").drop_duplicates("month", keep="last")
    if data.empty:
        raise RuntimeError("No social financing data returned.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    monthly["is_filled"] = monthly["social_financing_flow_100m_cny"].isna()
    monthly["social_financing_flow_100m_cny"] = monthly["social_financing_flow_100m_cny"].ffill()
    monthly["source"] = monthly["source"].ffill().bfill()

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[["month", "social_financing_flow_100m_cny", "is_filled", "source"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China monthly social financing flow data.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()
    df = fetch_social_financing()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")
    print(f"Source: {df['source'].iloc[-1]}")


if __name__ == "__main__":
    main()
