from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
import re
from datetime import date
from pathlib import Path

import akshare as ak
import pandas as pd
import requests
from akshare.utils import demjson


DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "宏观数据爬取"


def decode_trading_economics_chart(page_slug: str, chart_code: str) -> pd.DataFrame:
    page_url = f"https://zh.tradingeconomics.com/china/{page_slug}"
    headers = {"User-Agent": "Mozilla/5.0"}
    page = requests.get(page_url, headers=headers, timeout=30)
    page.raise_for_status()
    token = re.search(r"TEChartsToken = '([^']+)'", page.text)
    key = re.search(r"TEObfuscationkey = '([^']+)'", page.text)
    datasource = re.search(r"TEChartsDatasource = '([^']+)'", page.text)
    if not token or not key or not datasource:
        raise RuntimeError(f"Unable to discover Trading Economics chart endpoint for {page_slug}.")

    chart = requests.get(
        f"{datasource.group(1)}/economics/{chart_code}",
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

    data = pd.DataFrame(observations, columns=["value", "timestamp", "reference_date", "date"])
    data["month"] = pd.to_datetime(data["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    return data.dropna(subset=["month", "value"])[["month", "value"]]


def reindex_monthly(data: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    data = data.sort_values("month").drop_duplicates("month", keep="last")
    index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(index)
    monthly["is_filled"] = monthly[value_columns].isna().any(axis=1)
    monthly[value_columns] = monthly[value_columns].ffill()
    return monthly.reset_index()


def add_yoy_features(frame: pd.DataFrame, yoy_column: str) -> pd.DataFrame:
    frame[f"{yoy_column}_change_3m"] = frame[yoy_column] - frame[yoy_column].shift(3)
    frame[f"{yoy_column}_change_3m"] = frame[f"{yoy_column}_change_3m"].fillna(0.0)
    frame[f"{yoy_column}_ma3"] = frame[yoy_column].rolling(3, min_periods=1).mean()
    frame[f"{yoy_column}_improving_3m"] = frame[f"{yoy_column}_change_3m"] > 0
    frame["turned_positive"] = (frame[yoy_column] > 0) & (frame[yoy_column].shift(1) <= 0)
    return frame


def fetch_industrial_enterprise_profit() -> pd.DataFrame:
    data = decode_trading_economics_chart("corporate-profits", "chinacorpro").rename(
        columns={"value": "industrial_profit_ytd_100m_cny"}
    )
    # Trading Economics publishes China industrial profits in million CNY.
    data["industrial_profit_ytd_100m_cny"] = data["industrial_profit_ytd_100m_cny"] / 100
    data = data.sort_values("month")
    previous = data[["month", "industrial_profit_ytd_100m_cny"]].copy()
    previous["month"] = previous["month"] + pd.DateOffset(years=1)
    previous = previous.rename(columns={"industrial_profit_ytd_100m_cny": "previous_year_ytd_100m_cny"})
    data = data.merge(previous, on="month", how="left")
    data["profit_ytd_yoy_pct"] = (
        data["industrial_profit_ytd_100m_cny"] / data["previous_year_ytd_100m_cny"] - 1
    ) * 100
    data = data.dropna(subset=["profit_ytd_yoy_pct"])
    result = reindex_monthly(data[["month", "industrial_profit_ytd_100m_cny", "profit_ytd_yoy_pct"]], [
        "industrial_profit_ytd_100m_cny",
        "profit_ytd_yoy_pct",
    ])
    result = add_yoy_features(result, "profit_ytd_yoy_pct")
    result["source"] = "Trading Economics public chart / China Total Industrial Profits"
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "industrial_profit_ytd_100m_cny",
            "profit_ytd_yoy_pct",
            "profit_ytd_yoy_pct_change_3m",
            "profit_ytd_yoy_pct_ma3",
            "profit_ytd_yoy_pct_improving_3m",
            "turned_positive",
            "is_filled",
            "source",
        ]
    ]


def fetch_surveyed_unemployment() -> pd.DataFrame:
    data = decode_trading_economics_chart("unemployment-rate", "cnuerate").rename(
        columns={"value": "surveyed_unemployment_rate_pct"}
    )
    result = reindex_monthly(data, ["surveyed_unemployment_rate_pct"])
    result["unemployment_rate_mom_change_pct"] = result["surveyed_unemployment_rate_pct"].diff()
    result["unemployment_rate_ma3_pct"] = result["surveyed_unemployment_rate_pct"].rolling(3, min_periods=1).mean()
    result["unemployment_rate_up_3m"] = (
        result["surveyed_unemployment_rate_pct"]
        > result["surveyed_unemployment_rate_pct"].shift(1)
    ) & (
        result["surveyed_unemployment_rate_pct"].shift(1)
        > result["surveyed_unemployment_rate_pct"].shift(2)
    )
    result["source"] = "Trading Economics public chart / China Unemployment Rate"
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    result["unemployment_rate_mom_change_pct"] = result["unemployment_rate_mom_change_pct"].fillna(0.0)
    return result[
        [
            "month",
            "surveyed_unemployment_rate_pct",
            "unemployment_rate_mom_change_pct",
            "unemployment_rate_ma3_pct",
            "unemployment_rate_up_3m",
            "is_filled",
            "source",
        ]
    ]


def fetch_rrr() -> pd.DataFrame:
    raw = ak.macro_china_reserve_requirement_ratio().rename(
        columns={
            "公布时间": "publish_date",
            "生效时间": "effective_date",
            "大型金融机构-调整后": "large_bank_rrr_pct",
            "中小金融机构-调整后": "small_bank_rrr_pct",
            "大型金融机构-调整幅度": "large_bank_rrr_change_pct",
            "中小金融机构-调整幅度": "small_bank_rrr_change_pct",
        }
    )
    data = raw[
        [
            "publish_date",
            "effective_date",
            "large_bank_rrr_pct",
            "small_bank_rrr_pct",
            "large_bank_rrr_change_pct",
            "small_bank_rrr_change_pct",
            "备注",
        ]
    ].copy()
    data["publish_date"] = pd.to_datetime(data["publish_date"], format="%Y年%m月%d日", errors="coerce")
    data["effective_date"] = pd.to_datetime(data["effective_date"], format="%Y年%m月%d日", errors="coerce")
    numeric_columns = [
        "large_bank_rrr_pct",
        "small_bank_rrr_pct",
        "large_bank_rrr_change_pct",
        "small_bank_rrr_change_pct",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["effective_date", "large_bank_rrr_pct", "small_bank_rrr_pct"]).sort_values(
        "effective_date"
    )
    daily_index = pd.date_range(data["effective_date"].min(), pd.Timestamp(date.today()), freq="D", name="date")
    events = data.set_index("effective_date")
    daily = events.reindex(daily_index)
    daily["is_event_day"] = daily["large_bank_rrr_pct"].notna()
    daily["rrr_cut_event"] = daily["large_bank_rrr_change_pct"] < 0
    daily["rrr_hike_event"] = daily["large_bank_rrr_change_pct"] > 0
    daily[["large_bank_rrr_pct", "small_bank_rrr_pct"]] = daily[
        ["large_bank_rrr_pct", "small_bank_rrr_pct"]
    ].ffill()
    daily["large_bank_rrr_change_pct"] = daily["large_bank_rrr_change_pct"].fillna(0.0)
    daily["small_bank_rrr_change_pct"] = daily["small_bank_rrr_change_pct"].fillna(0.0)
    daily["is_filled"] = ~daily["is_event_day"]
    daily["rrr_cut_past_30d"] = daily["rrr_cut_event"].rolling(30, min_periods=1).max().astype(bool)
    daily["rrr_cut_past_60d"] = daily["rrr_cut_event"].rolling(60, min_periods=1).max().astype(bool)
    daily["rrr_cut_past_90d"] = daily["rrr_cut_event"].rolling(90, min_periods=1).max().astype(bool)
    daily["large_bank_rrr_change_1y_pct"] = daily["large_bank_rrr_pct"] - daily["large_bank_rrr_pct"].shift(365)
    daily["small_bank_rrr_change_1y_pct"] = daily["small_bank_rrr_pct"] - daily["small_bank_rrr_pct"].shift(365)
    daily[["large_bank_rrr_change_1y_pct", "small_bank_rrr_change_1y_pct"]] = daily[
        ["large_bank_rrr_change_1y_pct", "small_bank_rrr_change_1y_pct"]
    ].fillna(0.0)
    daily["source"] = "AKShare macro_china_reserve_requirement_ratio / Eastmoney"

    result = daily.reset_index()
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    result["publish_date"] = result["publish_date"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "date",
            "publish_date",
            "large_bank_rrr_pct",
            "small_bank_rrr_pct",
            "large_bank_rrr_change_pct",
            "small_bank_rrr_change_pct",
            "large_bank_rrr_change_1y_pct",
            "small_bank_rrr_change_1y_pct",
            "is_event_day",
            "rrr_cut_event",
            "rrr_hike_event",
            "rrr_cut_past_30d",
            "rrr_cut_past_60d",
            "rrr_cut_past_90d",
            "is_filled",
            "source",
        ]
    ]


def parse_sina_month(raw: pd.Series) -> pd.Series:
    text = raw.astype(str).str.strip()
    return pd.to_datetime(text, format="%Y.%m", errors="coerce").dt.to_period("M").dt.to_timestamp()


def fetch_electricity_consumption() -> pd.DataFrame:
    try:
        raw = ak.macro_china_society_electricity()
    except Exception:
        raw = fetch_sina_electricity_consumption()
    raw = raw.rename(
        columns={
            "统计时间": "month_label",
            "全社会用电量": "electricity_consumption_ytd_10k_kwh",
            "全社会用电量同比": "electricity_consumption_ytd_yoy_pct",
            "第二产业用电量": "secondary_industry_consumption_ytd_10k_kwh",
            "第二产业用电量同比": "secondary_industry_consumption_ytd_yoy_pct",
            "第三产业用电量": "tertiary_industry_consumption_ytd_10k_kwh",
            "第三产业用电量同比": "tertiary_industry_consumption_ytd_yoy_pct",
        }
    )
    data = raw[
        [
            "month_label",
            "electricity_consumption_ytd_10k_kwh",
            "electricity_consumption_ytd_yoy_pct",
            "secondary_industry_consumption_ytd_10k_kwh",
            "secondary_industry_consumption_ytd_yoy_pct",
            "tertiary_industry_consumption_ytd_10k_kwh",
            "tertiary_industry_consumption_ytd_yoy_pct",
        ]
    ].copy()
    data["month"] = parse_sina_month(data["month_label"])
    value_columns = [column for column in data.columns if column.endswith("_pct") or column.endswith("_kwh")]
    for column in value_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["month", "electricity_consumption_ytd_yoy_pct"])
    result = reindex_monthly(data[["month", *value_columns]], value_columns)
    result = add_yoy_features(result, "electricity_consumption_ytd_yoy_pct")
    result["source"] = "AKShare macro_china_society_electricity / Sina"
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            *value_columns,
            "electricity_consumption_ytd_yoy_pct_change_3m",
            "electricity_consumption_ytd_yoy_pct_ma3",
            "electricity_consumption_ytd_yoy_pct_improving_3m",
            "turned_positive",
            "is_filled",
            "source",
        ]
    ]


def fetch_sina_electricity_consumption() -> pd.DataFrame:
    url = "https://quotes.sina.com.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601557771972/MacPage_Service.get_pagedata"
    params = {"cate": "industry", "event": "6", "from": "0", "num": "31", "condition": ""}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/mac/"}
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data_text = response.text
    data_json = demjson.decode(data_text[data_text.find("{") : -3])
    page_num = math.ceil(int(data_json["count"]) / 31)
    big_df = pd.DataFrame(data_json["data"])
    for page in range(1, page_num):
        params.update({"from": page * 31})
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data_text = response.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        big_df = pd.concat([big_df, pd.DataFrame(data_json["data"])], ignore_index=True)

    big_df.columns = [
        "统计时间",
        "全社会用电量",
        "全社会用电量同比",
        "各行业用电量合计",
        "各行业用电量合计同比",
        "第一产业用电量",
        "第一产业用电量同比",
        "第二产业用电量",
        "第二产业用电量同比",
        "第三产业用电量",
        "第三产业用电量同比",
        "城乡居民生活用电量合计",
        "城乡居民生活用电量合计同比",
        "城镇居民用电量",
        "城镇居民用电量同比",
        "乡村居民用电量",
        "乡村居民用电量同比",
    ]
    for column in big_df.columns[1:]:
        big_df[column] = pd.to_numeric(big_df[column], errors="coerce")
    return big_df.sort_values("统计时间", ignore_index=True)


def fetch_electricity_output() -> pd.DataFrame:
    data = decode_trading_economics_chart("electricity-production", "chinaelepro").rename(
        columns={"value": "electricity_output_gwh"}
    )
    data = data.sort_values("month")
    previous = data[["month", "electricity_output_gwh"]].copy()
    previous["month"] = previous["month"] + pd.DateOffset(years=1)
    previous = previous.rename(columns={"electricity_output_gwh": "previous_year_output_gwh"})
    data = data.merge(previous, on="month", how="left")
    data["electricity_output_yoy_pct"] = (
        data["electricity_output_gwh"] / data["previous_year_output_gwh"] - 1
    ) * 100
    data = data.dropna(subset=["electricity_output_yoy_pct"])
    result = reindex_monthly(data[["month", "electricity_output_gwh", "electricity_output_yoy_pct"]], [
        "electricity_output_gwh",
        "electricity_output_yoy_pct",
    ])
    result = add_yoy_features(result, "electricity_output_yoy_pct")
    result["source"] = "Trading Economics public chart / China Electricity Production"
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "electricity_output_gwh",
            "electricity_output_yoy_pct",
            "electricity_output_yoy_pct_change_3m",
            "electricity_output_yoy_pct_ma3",
            "electricity_output_yoy_pct_improving_3m",
            "turned_positive",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch macro factor extension data.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"CSV output directory, default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (fetch_industrial_enterprise_profit(), "industrial_enterprise_profit_yoy_monthly.csv"),
        (fetch_surveyed_unemployment(), "surveyed_unemployment_rate_monthly.csv"),
        (fetch_rrr(), "reserve_requirement_ratio.csv"),
        (fetch_electricity_consumption(), "electricity_consumption_yoy_monthly.csv"),
        (fetch_electricity_output(), "electricity_output_yoy_monthly.csv"),
    ]
    for frame, filename in outputs:
        output = args.output_dir / filename
        frame.to_csv(output, index=False, encoding="utf-8-sig")
        date_column = "date" if "date" in frame.columns else "month"
        print(f"Saved {len(frame)} rows to {output}")
        print(f"Range: {frame[date_column].min()} to {frame[date_column].max()}")
        print(f"Filled rows: {int(frame['is_filled'].sum())}")


if __name__ == "__main__":
    main()
