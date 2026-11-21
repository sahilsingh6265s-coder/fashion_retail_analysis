"""Rebuild advanced comparisons from Kaggle Global Fashion Retail Sales v24."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def load(root):
    stores = pd.read_csv(root / 'stores.csv')
    us = stores.loc[stores.Country.eq('United States'), 'Store ID']
    products = pd.read_csv(root / 'products.csv', usecols=[
        'Product ID', 'Category', 'Sub Category', 'Production Cost'])
    frames = []
    for chunk in pd.read_csv(root / 'transactions.csv', chunksize=125000):
        part = chunk.loc[chunk['Store ID'].isin(us)]
        if len(part):
            assert part.Currency.eq('USD').all()
            frames.append(part)
    lines = pd.concat(frames, ignore_index=True)
    lines['day'] = pd.to_datetime(lines.Date).dt.normalize()
    lines = lines.merge(products, on='Product ID', how='left', validate='many_to_one')
    assert lines[['Category','Production Cost']].notna().all().all()
    lines['contribution'] = lines['Line Total'] - lines.Quantity * lines['Production Cost']
    return lines, pd.read_csv(root / 'discounts.csv', parse_dates=['Start','End'])


def compare(sales, calendar, out):
    start = pd.Timestamp('2024-03-15')
    group = ['Store ID','Category','Sub Category']
    eligible = calendar.loc[calendar.Start.eq(start) & calendar.Discont.eq(.35),
                            group[1:]].drop_duplicates()
    period = sales[sales.day.between(start-pd.Timedelta(days=56),start+pd.Timedelta(days=13))].copy()
    period['week'] = (period.day-start).dt.days // 7
    period = period.merge(eligible.assign(target=True), on=group[1:], how='left')
    units = period.pivot_table(index=group, columns='week', values='Quantity',
                               aggfunc='sum', fill_value=0).reindex(columns=range(-8,2),fill_value=0)
    targets = set(map(tuple,eligible.to_numpy()))
    has_discount = set(period.loc[period.Discount.gt(0)].groupby(group).groups)
    matches = []
    for key, series in units.iterrows():
        if key[1:] not in targets:
            continue
        # Controls must remain full-price across all ten weeks.
        pool = [k for k in units.index if k[:2]==key[:2] and k[1:] not in targets and k not in has_discount]
        pre = series.iloc[:8].to_numpy(float)
        if not pool or pre.min()<=0:
            continue
        candidates = units.loc[pool].iloc[:,:8]
        candidates = candidates.loc[candidates.min(axis=1)>0]
        if candidates.empty:
            continue
        trends = candidates.div(candidates.mean(axis=1),axis=0)
        distance = trends.sub(pre/pre.mean(),axis=1).pow(2).mean(axis=1).pow(.5)
        control = distance.idxmin()
        c = units.loc[control]
        # Reject poor pre-period shape matches; controls can be reused.
        gap = distance.loc[control]
        matches.append([*key,control[2],gap,gap<=.25,series.iloc[6:8].sum(),
                        series.iloc[8:].sum(),c.iloc[6:8].sum(),c.iloc[8:].sum()])
    m = pd.DataFrame(matches,columns=group+['control_subcategory','normalized_pretrend_rmse',
        'passes_0_25','target_before','target_during','control_before','control_during'])
    m['relative_change_vs_control'] = ((m.target_during/m.target_before) /
                                        (m.control_during/m.control_before).replace(0,np.nan)-1)
    m.to_csv(out/'comparison_groups.csv',index=False)
    scored = period[period.target.eq(True) & period.week.ge(-2)].copy()
    scored['period'] = np.where(scored.week.lt(0),'before','during')
    scored.groupby('period').agg(units=('Quantity','sum'),revenue=('Line Total','sum'),
                                 contribution=('contribution','sum')).to_csv(out/'campaign.csv')


def demand(sales, calendar, out):
    daily = sales.groupby(['Category','day']).Quantity.sum()
    rows = []
    for cat in sales.Category.unique():
        units = daily.loc[cat].asfreq('D',fill_value=0)
        weekly = units.resample('W-SUN').sum()
        weekly = weekly[(weekly.index-pd.Timedelta(days=6)>=units.index.min()) &
                        (weekly.index<=units.index.max())]
        days = pd.Series(0., index=units.index)
        for event in calendar[calendar.Category.eq(cat)].itertuples():
            days.loc[event.Start:event.End] = np.maximum(days.loc[event.Start:event.End],event.Discont)
        promo = days.resample('W-SUN').mean().reindex(weekly.index)
        # Calendar intensity is the maximum scheduled category discount each day.
        x = pd.concat([weekly.shift(),weekly.shift().rolling(4).mean(),promo],axis=1)
        x.columns = ['lag1','lag4mean','calendar']
        for i in range(len(weekly)-16,len(weekly)):
            train = x.iloc[4:i]
            params = np.linalg.lstsq(np.column_stack([np.ones(len(train)),train]),
                                     weekly.iloc[4:i],rcond=None)[0]
            pred = max(0,float(np.r_[1,x.iloc[i]] @ params))
            rows.append([cat,weekly.index[i],weekly.iloc[i],x.iloc[i,0],pred,promo.iloc[i],
                         'validation' if i<len(weekly)-8 else 'test'])
    b = pd.DataFrame(rows,columns=['category','week_end','actual','baseline','calendar_model',
                                   'planned_discount_intensity','split'])
    b.to_csv(out/'weekly_predictions.csv',index=False)
    scores = []
    for cat, block in b.groupby('category'):
        valid = block[block.split.eq('validation')]
        selected = min(['baseline','calendar_model'],key=lambda c:(valid[c]-valid.actual).abs().sum())
        test = block[block.split.eq('test')]
        for label,week in [('all',test),('promotion',test[test.planned_discount_intensity.gt(0)]),
                           ('regular',test[test.planned_discount_intensity.eq(0)])]:
            if week.empty:
                continue
            for model in ['baseline','calendar_model']:
                error = week[model]-week.actual
                scores.append([cat,label,len(week),model,model==selected,
                               100*error.abs().sum()/week.actual.sum(),error.mean()])
    pd.DataFrame(scores,columns=['category','weeks','n','model','selected_on_validation',
        'test_wape_pct','mean_overforecast_units']).to_csv(out/'model_comparison.csv',index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('data',type=Path)
    parser.add_argument('--out',type=Path,default=Path('outputs'))
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True,parents=True)
    lines, calendar = load(args.data)
    returns = lines[lines['Transaction Type'].eq('Return')]
    sales = lines[lines['Transaction Type'].eq('Sale')]
    assert not sales.duplicated(['Invoice ID','Line']).any()
    compare(sales,calendar,args.out)
    demand(sales,calendar,args.out)
    sales_amount = sales['Line Total'].sum()
    scenarios = {'all recorded':returns,'drop exact duplicate rows':returns.drop_duplicates(),
                 'first row per return key (stress test only)':returns.drop_duplicates(['Invoice ID','Line'])}
    pd.DataFrame([{'rule':k,'return_lines':len(v),'net_revenue':sales_amount+v['Line Total'].sum()}
                  for k,v in scenarios.items()]).to_csv(args.out/'return_sensitivity.csv',index=False)
    style = sales.groupby(['Store ID','Product ID','Category','Sub Category','Discount']).agg(
        units=('Quantity','sum'),revenue=('Line Total','sum'),contribution=('contribution','sum')).reset_index()
    bands = style.groupby(['Store ID','Product ID']).Discount.transform('nunique')
    style[bands>1].to_csv(args.out/'comparable_styles.csv',index=False)


if __name__=='__main__':
    main()
