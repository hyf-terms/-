# A股宏观数据爬取：工业增加值

从 AKShare 抓取东方财富宏观数据中的工业增加值增长月度数据，并导出 CSV。

## 数据

- 数据源：`akshare.macro_china_gyzjz()`
- 指标：工业增加值同比增长、累计增长
- 当前可用区间：2008 年 2 月至 AKShare 数据源最新月份
- 月度缺口处理：生成连续月初日期序列，缺失月份使用前值填充，并用 `is_filled` 标记

## 运行

```powershell
python -m pip install -r requirements.txt
python fetch_industrial_value.py
```

默认输出：

```text
C:\Users\hyf\Desktop\宏观数据爬取\industrial_value_growth_monthly.csv
```

可指定起始月份和输出路径：

```powershell
python fetch_industrial_value.py --start 2008-01-01 --output "C:\Users\hyf\Desktop\宏观数据爬取\industrial_value_growth_monthly.csv"
```
