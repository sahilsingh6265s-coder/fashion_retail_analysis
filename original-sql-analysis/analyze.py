"""Build the US store scorecard from Global Fashion Retail Sales, Kaggle v24."""
import argparse
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / 'outputs'
COLUMNS = {'Invoice ID': 'invoice', 'Line': 'line', 'Product ID': 'product',
           'Date': 'day', 'Quantity': 'units', 'Discount': 'discount',
           'Line Total': 'amount', 'Transaction Type': 'kind', 'Store ID': 'store'}


def ingest(db, folder):
    products = pd.read_csv(folder / 'products.csv', usecols=[
        'Product ID', 'Category', 'Sub Category', 'Description EN', 'Production Cost'])
    products = products.rename(columns={'Product ID': 'product', 'Category': 'category',
        'Sub Category': 'subcategory', 'Description EN': 'style', 'Production Cost': 'cost'})
    assert products['product'].is_unique
    products.to_sql('products', db, index=False)
    calendar = pd.read_csv(folder / 'discounts.csv')
    calendar.rename(columns={'Sub Category': 'subcategory'}).to_sql('calendar', db, index=False)
    stores = pd.read_csv(folder / 'stores.csv')
    us = stores.loc[stores.Country.eq('United States'), 'Store ID']
    rows = 0
    for chunk in pd.read_csv(folder / 'transactions.csv', chunksize=150000,
                             usecols=[*COLUMNS, 'Currency']):
        rows += len(chunk)
        subset = chunk.loc[chunk['Store ID'].isin(us)].copy()
        if subset.empty:
            continue
        assert subset.Currency.eq('USD').all()
        subset = subset.rename(columns=COLUMNS)[list(COLUMNS.values())]
        subset['day'] = subset.day.str[:10]
        assert subset.notna().all().all()
        subset.to_sql('lines', db, if_exists='append', index=False)
    db.execute("create unique index sale_key on lines(invoice,line) where kind='Sale'")
    db.execute('create unique index product_key on products(product)')
    db.execute('create view sales as select l.*, p.category, p.subcategory, p.style, p.cost '
               'from lines l left join products p using(product)')
    for condition in ['category is null', 'cost is null or cost < 0', 'units <= 0',
                      "kind not in ('Sale','Return')", "kind='Sale' and amount<0",
                      "kind='Return' and amount>0", 'discount not between 0 and 1']:
        if db.execute('select 1 from sales where ' + condition + ' limit 1').fetchone():
            raise ValueError('Unexpected source values: ' + condition)
    pd.DataFrame([{'global_lines_scanned': rows, 'us_stores': len(us)}]).to_csv(
        OUT / 'scope.csv', index=False)


def forecast(db):
    daily = pd.read_sql_query("""select day, category, sum(units) as units from sales
        where kind='Sale' group by day,category""", db)
    daily['day'] = pd.to_datetime(daily.day)
    wide = daily.pivot(index='day', columns='category', values='units').asfreq('D').fillna(0)
    weekly = wide.resample('W-SUN').sum()
    weekly = weekly.loc[(weekly.index - pd.Timedelta(days=6) >= wide.index.min())
                        & (weekly.index <= wide.index.max())]
    predictions, plans = [], []
    for category, units in weekly.items():
        trial = pd.DataFrame({'actual': units, 'last_week': units.shift(),
                              'four_week_mean': units.shift().rolling(4).mean()})
        valid = trial.iloc[-16:-8]
        errors = valid.drop(columns='actual').sub(valid.actual, axis=0).abs().sum()
        winner = errors.idxmin()
        test = trial.tail(8).copy()
        test['category'], test['selected_model'] = category, winner
        predictions.append(test.rename_axis('week_ending').reset_index())
        next_units = units.iloc[-1] if winner == 'last_week' else units.tail(4).mean()
        plans.append(dict(category=category, model=winner, next_week_ending=(
            units.index[-1] + pd.Timedelta(days=7)).date(), forecast_units=round(next_units),
            holdout_wape_pct=100 * (test[winner]-test.actual).abs().sum()/test.actual.sum(),
            baseline_wape_pct=100 * (test.last_week-test.actual).abs().sum()/test.actual.sum()))
    pd.concat(predictions).to_csv(OUT/'forecast_backtest.csv', index=False)
    pd.DataFrame(plans).to_csv(OUT/'forecast_summary.csv', index=False)


def run(folder):
    OUT.mkdir(exist_ok=True)
    with TemporaryDirectory() as tmp, sqlite3.connect(Path(tmp)/'analysis.db') as db:
        ingest(db, folder)
        for query in sorted((BASE/'sql').glob('*.sql')):
            result = pd.read_sql_query(query.read_text(), db)
            result.to_csv(OUT/(query.stem+'.csv'), index=False)
        forecast(db)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path, help='Folder containing extracted Kaggle CSVs')
    run(parser.parse_args().folder)
