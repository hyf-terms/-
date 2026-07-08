from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT = Path.home() / "Desktop" / "宏观数据爬取" / "release_calendar.csv"
DEFAULT_DATA_DIR = Path.home() / "Desktop" / "宏观数据爬取"


OUTPUT_COLUMNS = [
    "indicator",
    "frequency",
    "period",
    "period_start",
    "period_end",
    "release_date",
    "available_date",
    "date_quality",
    "source",
    "notes",
]


def month_bounds(month: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    period_start = month.dt.to_period("M").dt.to_timestamp()
    period_end = period_start + pd.offsets.MonthEnd(0)
    period_label = period_start.dt.strftime("%Y-%m")
    return period_label, period_start, period_end


def quarter_bounds(quarter_end: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    period_end = quarter_end.dt.to_period("Q").dt.end_time.dt.normalize()
    period_start = quarter_end.dt.to_period("Q").dt.start_time
    period_label = quarter_end.dt.to_period("Q").astype(str)
    return period_label, period_start, period_end


def calendar_frame(
    indicator: str,
    frequency: str,
    period_start: pd.Series,
    period_end: pd.Series,
    release_date: pd.Series | pd.NaT,
    source: str,
    notes: str,
    date_quality: str = "actual",
) -> pd.DataFrame:
    period_start = pd.to_datetime(period_start, errors="coerce")
    period_end = pd.to_datetime(period_end, errors="coerce")
    if isinstance(release_date, pd.Series):
        release = pd.to_datetime(release_date, errors="coerce")
    else:
        release = pd.Series(pd.NaT, index=period_start.index)
    period = (
        period_start.dt.to_period("Q").astype(str)
        if frequency == "quarterly"
        else period_start.dt.strftime("%Y-%m")
        if frequency == "monthly"
        else period_start.dt.strftime("%Y-%m-%d")
    )
    quality = pd.Series(date_quality, index=period_start.index)
    quality = quality.mask(release.isna(), "missing")
    frame = pd.DataFrame(
        {
            "indicator": indicator,
            "frequency": frequency,
            "period": period,
            "period_start": period_start,
            "period_end": period_end,
            "release_date": release,
            "available_date": release,
            "date_quality": quality,
            "source": source,
            "notes": notes,
        }
    )
    return frame.dropna(subset=["period_start", "period_end"])


def jin10_monthly_previous_period(func, indicator: str, source: str, notes: str) -> pd.DataFrame:
    raw = func().rename(columns={"日期": "release_date", "今值": "actual"})
    data = raw[["release_date", "actual"]].copy()
    data["release_date"] = pd.to_datetime(data["release_date"], errors="coerce")
    data["actual"] = pd.to_numeric(data["actual"], errors="coerce")
    data = data.dropna(subset=["release_date", "actual"])
    # CPI, PPI, import/export and industrial production are usually released for the previous statistical month.
    period_start = (data["release_date"].dt.to_period("M") - 1).dt.to_timestamp()
    period_end = period_start + pd.offsets.MonthEnd(0)
    return calendar_frame(indicator, "monthly", period_start, period_end, data["release_date"], source, notes)


def jin10_monthly_same_period(func, indicator: str, source: str, notes: str) -> pd.DataFrame:
    raw = func().rename(columns={"日期": "release_date", "今值": "actual"})
    data = raw[["release_date", "actual"]].copy()
    data["release_date"] = pd.to_datetime(data["release_date"], errors="coerce")
    data["actual"] = pd.to_numeric(data["actual"], errors="coerce")
    data = data.dropna(subset=["release_date", "actual"])
    period_start = data["release_date"].dt.to_period("M").dt.to_timestamp()
    period_end = period_start + pd.offsets.MonthEnd(0)
    return calendar_frame(indicator, "monthly", period_start, period_end, data["release_date"], source, notes)


def gdp_release_calendar() -> pd.DataFrame:
    raw = ak.macro_china_gdp_yearly().rename(columns={"日期": "release_date", "今值": "actual"})
    data = raw[["release_date", "actual"]].copy()
    data["release_date"] = pd.to_datetime(data["release_date"], errors="coerce")
    data["actual"] = pd.to_numeric(data["actual"], errors="coerce")
    data = data.dropna(subset=["release_date", "actual"])
    release_quarter = data["release_date"].dt.to_period("Q")
    period_quarter = release_quarter - 1
    period_start = period_quarter.dt.start_time
    period_end = period_quarter.dt.end_time.dt.normalize()
    return calendar_frame(
        "gdp_yoy",
        "quarterly",
        period_start,
        period_end,
        data["release_date"],
        "AKShare macro_china_gdp_yearly / Jin10",
        "GDP release date; period mapped to previous quarter.",
    )


def read_csv_fallback(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def calendar_from_month_csv(
    data_dir: Path,
    filename: str,
    indicator: str,
    source: str,
    notes: str,
    release_column: str | None = None,
) -> pd.DataFrame:
    path = data_dir / filename
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    data = read_csv_fallback(path)
    if "month" not in data.columns:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    month = pd.to_datetime(data["month"], errors="coerce")
    _, period_start, period_end = month_bounds(month)
    release = pd.to_datetime(data[release_column], errors="coerce") if release_column in data.columns else pd.NaT
    return calendar_frame(indicator, "monthly", period_start, period_end, release, source, notes)


def calendar_from_quarter_csv(
    data_dir: Path,
    filename: str,
    indicator: str,
    source: str,
    notes: str,
) -> pd.DataFrame:
    path = data_dir / filename
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    data = read_csv_fallback(path)
    if "quarter_end_month" not in data.columns:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    quarter_end = pd.to_datetime(data["quarter_end_month"], errors="coerce")
    _, period_start, period_end = quarter_bounds(quarter_end)
    return calendar_frame(indicator, "quarterly", period_start, period_end, pd.NaT, source, notes)


def lpr_calendar(data_dir: Path) -> pd.DataFrame:
    for filename in ("lpr_monthly.csv", "LPR.csv"):
        path = data_dir / filename
        if path.exists():
            data = read_csv_fallback(path)
            break
    else:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    month = pd.to_datetime(data["month"], errors="coerce")
    _, period_start, period_end = month_bounds(month)
    release = pd.to_datetime(data.get("trade_date"), errors="coerce")
    return calendar_frame(
        "lpr",
        "monthly",
        period_start,
        period_end,
        release,
        "AKShare macro_china_lpr / National Interbank Funding Center",
        "trade_date used as LPR release/effective date.",
        date_quality="actual",
    )


def rrr_calendar(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "reserve_requirement_ratio.csv"
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    data = read_csv_fallback(path)
    event_column = "is_event_day" if "is_event_day" in data.columns else "是否生效日" if "是否生效日" in data.columns else None
    if event_column is None:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    event_mask = data[event_column].astype(str).str.lower().isin(["true", "1", "yes"])
    data = data[event_mask].copy()
    period_start = pd.to_datetime(data["date"], errors="coerce")
    period_end = period_start
    release = pd.to_datetime(data.get("publish_date"), errors="coerce")
    return calendar_frame(
        "reserve_requirement_ratio",
        "event",
        period_start,
        period_end,
        release,
        "AKShare macro_china_reserve_requirement_ratio / Eastmoney",
        "release_date is PBOC announcement date; period_start is effective date.",
        date_quality="actual",
    )


def build_release_calendar(data_dir: Path) -> pd.DataFrame:
    frames = [
        jin10_monthly_previous_period(
            ak.macro_china_cpi_yearly,
            "cpi_yoy",
            "AKShare macro_china_cpi_yearly / Jin10",
            "Actual CPI release date; period mapped to previous statistical month.",
        ),
        jin10_monthly_previous_period(
            ak.macro_china_ppi_yearly,
            "ppi_yoy",
            "AKShare macro_china_ppi_yearly / Jin10",
            "Actual PPI release date; period mapped to previous statistical month.",
        ),
        jin10_monthly_same_period(
            ak.macro_china_pmi_yearly,
            "manufacturing_pmi",
            "AKShare macro_china_pmi_yearly / Jin10",
            "Actual official manufacturing PMI release date; period mapped to release month.",
        ),
        gdp_release_calendar(),
        jin10_monthly_previous_period(
            ak.macro_china_exports_yoy,
            "export_amount_yoy",
            "AKShare macro_china_exports_yoy / Jin10",
            "Actual customs export release date; period mapped to previous statistical month.",
        ),
        jin10_monthly_previous_period(
            ak.macro_china_imports_yoy,
            "import_amount_yoy",
            "AKShare macro_china_imports_yoy / Jin10",
            "Actual customs import release date; period mapped to previous statistical month.",
        ),
        jin10_monthly_previous_period(
            ak.macro_china_industrial_production_yoy,
            "industrial_value_added_yoy",
            "AKShare macro_china_industrial_production_yoy / Jin10",
            "Actual industrial production release date; period mapped to previous statistical month.",
        ),
        calendar_from_month_csv(
            data_dir,
            "industrial_value_growth_monthly.csv",
            "industrial_value_added_yoy",
            "AKShare macro_china_gyzjz / Eastmoney",
            "publish_date from Eastmoney industrial value CSV.",
            "publish_date",
        ),
        calendar_from_month_csv(
            data_dir,
            "money_supply_yoy_monthly.csv",
            "money_supply_m1_m2_yoy",
            "AKShare macro_china_supply_of_money / PBOC",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "social_financing_monthly.csv",
            "social_financing",
            "PBOC / Trading Economics fallback",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "fixed_asset_investment_yoy_monthly.csv",
            "fixed_asset_investment_yoy",
            "AKShare macro_china_gdzctz / Eastmoney",
            "Release date generally aligns with NBS monthly activity release; exact date unavailable in stable source.",
        ),
        calendar_from_month_csv(
            data_dir,
            "retail_sales_yoy_monthly.csv",
            "retail_sales_yoy",
            "AKShare macro_china_consumer_goods_retail / Eastmoney",
            "Release date generally aligns with NBS monthly activity release; exact date unavailable in stable source.",
        ),
        calendar_from_month_csv(
            data_dir,
            "surveyed_unemployment_rate_monthly.csv",
            "surveyed_unemployment_rate",
            "Trading Economics public chart",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "industrial_enterprise_profit_yoy_monthly.csv",
            "industrial_enterprise_profit_yoy",
            "Trading Economics public chart",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "electricity_consumption_yoy_monthly.csv",
            "electricity_consumption_yoy",
            "AKShare macro_china_society_electricity / Sina",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "electricity_output_yoy_monthly.csv",
            "electricity_output_yoy",
            "Trading Economics public chart",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "real_estate_development_investment_yoy_monthly.csv",
            "real_estate_development_investment_yoy",
            "NBS / SteelX2 fallback",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_month_csv(
            data_dir,
            "commercial_housing_sales_area_yoy_monthly.csv",
            "commercial_housing_sales_area_yoy",
            "NBS / SteelX2 fallback",
            "Release date unavailable in stable source; period retained for future-function audit.",
        ),
        calendar_from_quarter_csv(
            data_dir,
            "gdp_yoy_quarterly.csv",
            "gdp_yoy",
            "AKShare macro_china_gdp / Eastmoney",
            "Release dates supplemented by Jin10 when available.",
        ),
        lpr_calendar(data_dir),
        rrr_calendar(data_dir),
    ]
    calendar = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    calendar = calendar.drop_duplicates(["indicator", "period_start"], keep="first")
    calendar = calendar.sort_values(["release_date", "period_start", "indicator"], na_position="last")
    for column in ["period_start", "period_end", "release_date", "available_date"]:
        calendar[column] = pd.to_datetime(calendar[column], errors="coerce").dt.strftime("%Y-%m-%d")
    return calendar[OUTPUT_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a macro release calendar for existing datasets.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help=f"CSV data directory, default: {DEFAULT_DATA_DIR}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"CSV output path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    calendar = build_release_calendar(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    calendar.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(calendar)} rows to {args.output}")
    print(f"Indicators: {calendar['indicator'].nunique()}")
    print(calendar["date_quality"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
