# A股相关宏观数据爬取

抓取工业增加值、制造业 PMI、GDP、货币供应量、社融及物价指标，并导出 CSV。

## 数据

- 数据源：`akshare.macro_china_gyzjz()`
- 指标：工业增加值同比增长、累计增长
- 当前可用区间：2008 年 2 月至 AKShare 数据源最新月份
- 月度缺口处理：生成连续月初日期序列，缺失月份使用前值填充，并用 `is_filled` 标记

### 制造业 PMI

- 数据源：`akshare.macro_china_pmi()`
- 完整区间：2006 年 1 月至最新月份；2005 年数据用于计算首年同比
- 输出：`manufacturing_pmi_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### GDP 同比

- 数据源：`akshare.macro_china_gdp()`
- 完整区间：2006 年第 1 季度至最新季度
- 输出：`gdp_yoy_quarterly.csv`
- 季度缺口处理：缺失季度使用前值填充，并用 `is_filled` 标记

### M1、M2 月度同比

- 数据源：`akshare.macro_china_supply_of_money()`
- 完整区间：1996 年 12 月至最新月份；更早数据仅按年披露，不纳入连续月频 CSV
- 输出：`money_supply_yoy_monthly.csv`
- 月度缺口处理：缺失月份的 M1、M2 同比使用前值填充，并用 `is_filled` 标记

### 社会融资规模增量

- 主接口：`akshare.macro_china_shrzgm()`
- 备用源：AKShare 的商务部接口不可用时，使用央行口径公开历史序列
- 完整区间：2002 年 1 月起
- 输出：`social_financing_monthly.csv`，单位为亿元人民币

### CPI、PPI 同比

- 数据源：金十历史接口与东方财富最新接口合并，兼顾早期覆盖和最新数据
- 完整区间：CPI 从 1986 年 1 月起，PPI 从 1995 年 7 月起
- 输出：`cpi_yoy_monthly.csv`、`ppi_yoy_monthly.csv`
- `release_date` 在金十历史区间为公布日期；东方财富补充区间未提供该字段，留空处理

### 房地产投资与商品房销售面积同比

- 数据源：`akshare.macro_china_nbs_nation()`；访问受限时使用 AKShare 内置指标映射 167/170
- 指标：房地产开发投资额累计同比、商品房销售面积累计同比
- 输出：`real_estate_development_investment_yoy_monthly.csv`、`commercial_housing_sales_area_yoy_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### 出口金额同比

- 数据源：`akshare.macro_china_hgjck()`
- 指标：当月出口额、当月出口额同比增长；出口额按海关接口原始数值保留，列名标注为千美元
- 输出：`export_amount_yoy_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### LPR

- 数据源：`akshare.macro_china_lpr()`
- 指标：1 年期 LPR、5 年期以上 LPR
- 输出：`lpr_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记；为保障字段完整性，从 1 年期和 5 年期均有数据的月份开始

### USD/CNY 官方中间价

- 数据源：`akshare.currency_boc_safe()`
- 指标：人民币兑美元官方中间价；原始美元列为 100 美元兑人民币，另换算为 1 美元兑人民币
- 输出：`usd_cny_mid_daily.csv`
- 默认区间：2019 年首个公布日至最新公布日期
- 日度缺口处理：生成连续自然日序列，周末和节假日等无公布日期使用前值填充，并用 `is_filled` 标记

### 固定资产投资同比

- 数据源：`akshare.macro_china_gdzctz()`
- 指标：固定资产投资自年初累计值、累计同比；累计同比由同一月份的上一年累计值计算得到
- 完整区间：2009 年 2 月至最新月份
- 输出：`fixed_asset_investment_yoy_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### 社会消费品零售总额同比

- 数据源：`akshare.macro_china_consumer_goods_retail()`
- 指标：社会消费品零售总额当月值、当月同比、累计值、累计同比
- 完整区间：2008 年 1 月至最新月份
- 输出：`retail_sales_yoy_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### 进口金额同比与贸易差额

- 数据源：`akshare.macro_china_hgjck()`
- 指标：当月进口额、当月进口额同比、当月出口额、贸易差额；进出口金额按海关接口原始数值保留，列名标注为千美元
- 完整区间：2008 年 1 月至最新月份
- 输出：`import_amount_yoy_monthly.csv`、`trade_balance_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### 财政收入同比

- 数据源：`akshare.macro_china_czsr()`
- 指标：财政收入当月值、当月同比、累计值、累计同比；当前稳定 AKShare/东方财富接口未暴露财政支出
- 完整区间：2008 年 1 月至最新月份
- 输出：`fiscal_revenue_expenditure_yoy_monthly.csv`
- 月度缺口处理：缺失月份使用前值填充，并用 `is_filled` 标记

### SHIBOR

- 数据源：`akshare.macro_china_shibor_all()`
- 指标：隔夜、1 周、2 周、1 月、3 月、6 月、9 月、1 年 SHIBOR
- 完整区间：2017 年 3 月 17 日至最新日期
- 输出：`shibor_daily.csv`
- 日度缺口处理：生成连续自然日序列，周末和节假日等无公布日期使用前值填充，并用 `is_filled` 标记

### 中国国债收益率

- 数据源：`akshare.bond_china_yield()`
- 指标：中债国债收益率曲线 3 月、6 月、1 年、3 年、5 年、7 年、10 年、30 年收益率，以及 10 年-1 年期限利差
- 默认区间：2010 年 1 月 1 日至最新可用日期
- 输出：`china_treasury_yield_daily.csv`
- 日度缺口处理：生成连续自然日序列，周末和节假日等无公布日期使用前值填充，并用 `is_filled` 标记

### 盈利、就业、政策与电力因子

- 工业企业利润：Trading Economics 公共图表；输出 `industrial_enterprise_profit_yoy_monthly.csv`
- 城镇调查失业率：Trading Economics 公共图表；输出 `surveyed_unemployment_rate_monthly.csv`
- 存款准备金率：`akshare.macro_china_reserve_requirement_ratio()`；输出 `reserve_requirement_ratio.csv`
- 全社会用电量：`akshare.macro_china_society_electricity()`；输出 `electricity_consumption_yoy_monthly.csv`
- 发电量：Trading Economics 公共图表；输出 `electricity_output_yoy_monthly.csv`
- 衍生因子：同比 3 个月变化、3 个月均值、是否 3 个月改善、是否由负转正；RRR 另含过去 30/60/90 天是否降准、1 年变化等政策状态字段

### 经济日历

- 数据源：AKShare 金十类公布日接口、已有 CSV 中的 `publish_date`/`trade_date`/`release_date` 字段，以及 RRR 公布日
- 输出：`release_calendar.csv`
- 字段：`indicator`、`frequency`、`period`、`period_start`、`period_end`、`release_date`、`available_date`、`date_quality`、`source`、`notes`
- `date_quality=actual` 表示真实公布日；`date_quality=missing` 表示当前稳定来源未提供公布日，仅保留所属期用于未来函数审计

## 运行

```powershell
python -m pip install -r requirements.txt
python fetch_industrial_value.py
python fetch_manufacturing_pmi.py
python fetch_gdp_yoy.py
python fetch_money_supply_yoy.py
python fetch_social_financing.py
python fetch_cpi_yoy.py
python fetch_ppi_yoy.py
python fetch_real_estate_indicators.py
python fetch_export_yoy.py
python fetch_lpr.py
python fetch_usd_cny_mid.py
python fetch_fixed_asset_investment_yoy.py
python fetch_retail_sales_yoy.py
python fetch_import_and_trade_balance.py
python fetch_fiscal_revenue_expenditure_yoy.py
python fetch_shibor.py
python fetch_china_treasury_yield.py
python fetch_macro_factor_extensions.py
python fetch_release_calendar.py
```

默认输出：

```text
C:\Users\hyf\Desktop\宏观数据爬取\industrial_value_growth_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\manufacturing_pmi_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\gdp_yoy_quarterly.csv
C:\Users\hyf\Desktop\宏观数据爬取\money_supply_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\social_financing_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\cpi_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\ppi_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\real_estate_development_investment_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\commercial_housing_sales_area_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\export_amount_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\lpr_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\usd_cny_mid_daily.csv
C:\Users\hyf\Desktop\宏观数据爬取\fixed_asset_investment_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\retail_sales_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\import_amount_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\trade_balance_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\fiscal_revenue_expenditure_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\shibor_daily.csv
C:\Users\hyf\Desktop\宏观数据爬取\china_treasury_yield_daily.csv
C:\Users\hyf\Desktop\宏观数据爬取\industrial_enterprise_profit_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\surveyed_unemployment_rate_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\reserve_requirement_ratio.csv
C:\Users\hyf\Desktop\宏观数据爬取\electricity_consumption_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\electricity_output_yoy_monthly.csv
C:\Users\hyf\Desktop\宏观数据爬取\release_calendar.csv
```

可指定起始月份和输出路径：

```powershell
python fetch_industrial_value.py --start 2008-01-01 --output "C:\Users\hyf\Desktop\宏观数据爬取\industrial_value_growth_monthly.csv"
```
