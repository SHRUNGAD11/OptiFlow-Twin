import pandas as pd
from src.inventory import inventory_status,fefo_dispatch
from src.forecasting import compare_forecasters

def test_inventory_metrics_and_stockout():
    p=pd.DataFrame([{"sku":"A","product_name":"Test","category":"Grocery","current_stock":10,"daily_demand":5,"reorder_point":20,"lead_time_days":3}])
    f=pd.DataFrame({"sku":["A"]*7,"forecast_demand":[4,5,6,5,7,6,5]})
    r=inventory_status(p,f)
    assert all(c in r for c in ["safety_stock","dynamic_reorder_point","eoq","suggested_order_quantity"])
    assert bool(r.loc[0,"stockout_risk"])

def test_fefo_skips_expired_and_sorts_expiry():
    b=pd.DataFrame([
      {"batch_id":"expired","sku":"A","quantity":100,"expiry_date":"2025-01-01"},
      {"batch_id":"later","sku":"A","quantity":10,"expiry_date":"2027-03-01"},
      {"batch_id":"earlier","sku":"A","quantity":8,"expiry_date":"2027-01-01"}])
    r=fefo_dispatch(b,"A",12,as_of="2026-11-03")
    assert list(r.batch_id)==["earlier","later"]
    assert list(r.dispatch_quantity)==[8,4]
    assert r.unfulfilled_quantity.iloc[0]==0

def test_fefo_shortfall():
    b=pd.DataFrame([{"batch_id":"b1","sku":"A","quantity":3,"expiry_date":"2027-01-01"}])
    assert fefo_dispatch(b,"A",8,as_of="2026-11-03").unfulfilled_quantity.iloc[0]==5

def test_forecast_comparison():
    dates=pd.date_range("2025-01-01",periods=65); rows=[]
    for sku,base in [("A",20),("B",12)]:
        for i,d in enumerate(dates): rows.append({"date":d,"sku":sku,"quantity":base+i%7})
    metrics,fc=compare_forecasters(pd.DataFrame(rows),pd.DataFrame({"sku":["A","B"]}),10)
    assert {"ARIMA","SARIMA","Random Forest"}.issubset(set(metrics.model))
    assert len(fc)==14
