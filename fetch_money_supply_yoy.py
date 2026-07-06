from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import akshare as ak
import pandas as pd
import requests
from akshare.utils import demjson


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "money_supply_yoy_monthly.csv"


def normalize_month(raw_month: pd.Series) -> pd.Series:
    return pd.to_datetime(raw_month.astype(str), format="%Y.%m", errors="coerce")


def find_earliest_complete_month(data: pd.DataFrame) -> pd.Timestamp:
    observed = set(data["month"])
    end = data["month"].max()
    for start in sorted(observed):
        if all(month in observed for month in pd.date_range(start, end, freq="MS")):
            return start
    raise RuntimeError("Unable to find a continuous M1/M2 monthly range.")


def fetch_raw_money_supply(attempts: int = 3) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return ak.macro_china_supply_of_money()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    try:
        return fetch_sina_money_supply_fallback()
    except Exception as fallback_error:
        raise RuntimeError("AKShare money-supply source failed after retries.") from fallback_error


def fetch_sina_money_supply_fallback() -> pd.DataFrame:
    url = (
        "https://quotes.sina.com.cn/mac/api/jsonp_v3.php/"
        "SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
    )
    params = {"cate": "fininfo", "event": "1", "from": "0", "num": "31", "condition": ""}
    frames: list[pd.DataFrame] = []
    column_names: list[str] | None = None
    page_count = 1
    page = 0
    while page < page_count:
        params["from"] = str(page * 31)
        response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        data_text = response.text
        data_json = demjson.decode(data_text[data_text.find("{") : -3])
        if page == 0:
            page_count = math.ceil(int(data_json["count"]) / 31)
            column_names = [item[1] for item in data_json["config"]["all"]]
        frames.append(pd.DataFrame(data_json["data"]))
        page += 1
    result = pd.concat(frames, ignore_index=True)
    result.columns = column_names
    return result


def fetch_money_supply_yoy(start: str | None = None) -> pd.DataFrame:
    raw = fetch_raw_money_supply().rename(
        columns={
            "统计时间": "month_label",
            "货币(狭义货币M1)同比增长": "m1_yoy_growth_pct",
            "货币和准货币（广义货币M2）同比增长": "m2_yoy_growth_pct",
        }
    )

    data = raw[["month_label", "m1_yoy_growth_pct", "m2_yoy_growth_pct"]].copy()
    data["month"] = normalize_month(data["month_label"])
    data["m1_yoy_growth_pct"] = pd.to_numeric(data["m1_yoy_growth_pct"], errors="coerce")
    data["m2_yoy_growth_pct"] = pd.to_numeric(data["m2_yoy_growth_pct"], errors="coerce")
    data = data.dropna(subset=["month", "m1_yoy_growth_pct", "m2_yoy_growth_pct"]).sort_values("month")
    effective_start = pd.Timestamp(start) if start else find_earliest_complete_month(data)
    data = data[data["month"] >= effective_start]
    if data.empty:
        raise RuntimeError("No M1 or M2 year-on-year data returned for the requested range.")

    monthly_index = pd.date_range(data["month"].min(), data["month"].max(), freq="MS", name="month")
    monthly = data.set_index("month").reindex(monthly_index)
    growth_columns = ["m1_yoy_growth_pct", "m2_yoy_growth_pct"]
    monthly["is_filled"] = monthly[growth_columns].isna().any(axis=1)
    monthly[growth_columns] = monthly[growth_columns].ffill()
    labels = pd.Series(monthly.index.strftime("%Y年%m月份"), index=monthly.index)
    monthly["month_label"] = monthly["month_label"].fillna(labels)
    monthly["source"] = "AKShare macro_china_supply_of_money / PBOC"

    result = monthly.reset_index()
    result["month"] = result["month"].dt.strftime("%Y-%m-%d")
    return result[
        [
            "month",
            "month_label",
            "m1_yoy_growth_pct",
            "m2_yoy_growth_pct",
            "is_filled",
            "source",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch China M1 and M2 year-on-year monthly data from AKShare.")
    parser.add_argument("--start", default=None, help="Optional start month; default uses earliest complete range")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    df = fetch_money_supply_yoy(start=args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {args.output}")
    print(f"Range: {df['month'].min()} to {df['month'].max()}")
    print(f"Filled months: {int(df['is_filled'].sum())}")


if __name__ == "__main__":
    main()
