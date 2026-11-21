# Fashion retail markdowns and demand planning

**Business decision.** Should a category manager repeat a 35% spring promotion, and how many units should the team plan for next week? This independent business analytics case uses simulated physical-store purchases. It was designed around the responsibilities in Myntra’s Data Analytics Intern description.

## Reproduce on Windows

1. Download [Global Fashion Retail Sales by Ric. G. on Kaggle](https://www.kaggle.com/datasets/ricgomes/global-fashion-retail-stores-dataset), version 24. Extract the CSV files into a folder called data beside analyze.py.
2. Open PowerShell in this project folder and run the following commands. The pipeline streams the source and uses a temporary SQLite database. Allow at least 2 GB of free space after extracting the data.

~~~powershell
py -m pip install -r requirements.txt
py analyze.py data
~~~

3. Open findings.md for the decision memo. Open outputs/spring_campaign.csv and outputs/forecast_backtest.csv in Excel to trace the findings. All outputs are included. A new run rebuilds the CSVs.

## Analytical choices

- Scan the global transactions file and select the US stores via the store dimension. Validate USD on every included line. The product join uses a checked, unique product key.
- AOV equals the sum of discounted sale line amounts divided by distinct sale invoices. A multi-item basket counts once. The invoice total repeats across its lines.
- Use the signed line amount for returns. Return invoice and line identifiers can recur in the source. Retain raw return lines, flag repeated keys in return_quality.csv, and treat net sales and style rankings as provisional. Sales-only campaign comparisons and AOV exclude refund lines.
- Compare March 15–28, 2024 with March 1–14 for exactly the category/subcategory pairs listed in the spring campaign calendar. Both windows cover each weekday twice. Include all purchases of eligible products to avoid selecting only discounted lines. The full promotion lasted through March 31. The final three days are outside this matched comparison.
- Contribution proxy equals discounted sale revenue less quantity times catalog production cost. Assume the product cost is on a comparable USD basis for US transactions. Shipping, overhead, returns and marketing spend are excluded from campaign contribution. This cannot establish campaign ROI or a causal sales lift.
- Forecast observed sale units by category, using complete Monday–Sunday weeks. Compare last week’s units with a trailing four-week mean using an eight-week validation window. Lock the lower-error model per category, then perform eight rolling one-week-ahead tests. WAPE = sum of absolute errors / sum of actual units. The planning forecast starts after the last complete week and ignores any partial week already observed. Stockouts and unconstrained demand are unobserved.
- Footfall, site sessions, acquisition spend and acquisition channel are unavailable. The case therefore focuses on basket value, sales, markdown economics and planning.

## Files

| File | Question |
| --- | --- |
| sql/scorecard.sql | What were sales, refunds, net sales and average basket value? |
| sql/spring_campaign.sql | How did unit volume, revenue and estimated contribution change for eligible styles? |
| sql/markdowns.sql | Within a subcategory, how did unit economics vary across discount levels? |
| sql/style_ranking.sql | Which ten product IDs led each category by recorded net revenue? |
| sql/return_quality.sql | How frequently are return invoice-line keys reused? |
| analyze.py | How are joins validated and weekly forecasts tested? |

Source credit: Ric. G., Global Fashion Retail Sales, Kaggle, version 24. The source is synthetic. The package contains code and derived aggregate results. Source CSVs are downloaded separately.
