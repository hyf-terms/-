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
```

可指定起始月份和输出路径：

```powershell
python fetch_industrial_value.py --start 2008-01-01 --output "C:\Users\hyf\Desktop\宏观数据爬取\industrial_value_growth_monthly.csv"
```
