# 非 AKShare 来源的 A 股宏观十因子

本目录用于从 AKShare 以外的公开网站获取 10 个代表性中国宏观变量，输出近十年 CSV。数据来自 Trading Economics 公开图表接口。

## 因子与数据源

| CSV 文件 | 因子 | 数据源 |
| --- | --- | --- |
| `manufacturing_pmi_monthly.csv` | 中国官方制造业 PMI | Trading Economics: China NBS Manufacturing PMI |
| `industrial_value_added_yoy_monthly.csv` | 工业增加值同比 | Trading Economics: China Industrial Production |
| `social_financing_monthly.csv` | 社会融资规模 | Trading Economics: China Total Social Financing |
| `money_supply_m1_m2_yoy_monthly.csv` | M1 同比、M2 同比 | Trading Economics: China Money Supply M1/M2，脚本按同月上一年计算同比 |
| `lpr_monthly.csv` | 1 年期 LPR | Trading Economics: China Loan Prime Rate |
| `cpi_yoy_monthly.csv` | CPI 同比 | Trading Economics: China Inflation Rate |
| `ppi_yoy_monthly.csv` | PPI 同比 | Trading Economics: China Producer Prices Change |
| `fixed_asset_investment_yoy_monthly.csv` | 固定资产投资累计同比 | Trading Economics: China Fixed Asset Investment |
| `export_amount_yoy_monthly.csv` | 出口金额同比 | Trading Economics: China Exports，脚本按同月上一年计算同比 |
| `china_long_term_government_bond_yield_monthly.csv` | 中国 10 年期国债收益率 | Trading Economics: China 10Y Government Bond Yield |

## 运行方式

```powershell
python -m pip install -r requirements.txt
python fetch_non_akshare_top10_macro.py
```

默认输出目录：

```text
C:\Users\hyf\Desktop\工作\网站爬取宏观数据
```

指定开始日期和输出目录：

```powershell
python fetch_non_akshare_top10_macro.py --start 2016-07-01 --output-dir "C:\Users\hyf\Desktop\工作\网站爬取宏观数据"
```

## 字段说明

- `month`：所属月份，统一为月初日期。
- `is_filled`：该月是否由前值填充。月度缺口使用前向填充，避免量化合并时出现空洞。
- `source`：文字版数据来源。
- `source_url`：数据来源网页或 CSV 地址。
- `*_yoy_pct`：同比百分比。若原始网站直接提供同比，则直接保留；若网站提供水平值，则按同月上一年计算。

## 口径备注

- 本脚本不使用 AKShare，也不调用 AKShare 的任何接口。
- Trading Economics 的公开图表数据可能与国家统计局、央行、海关等官方最终修订值存在小幅差异，适合做因子原型和多源校验。
- M1/M2 和出口金额的同比为脚本计算值，不是网站直接公布字段。
- 近十年默认从当前月份向前推十年；在 2026 年 7 月 9 日运行时，默认开始月份为 2016 年 7 月。
