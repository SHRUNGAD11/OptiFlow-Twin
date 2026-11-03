import pandas as pd
from src.inventory import fefo_dispatch, inventory_status

def test_fefo_dispatch_uses_earliest_expiry_first():
    batches = pd.DataFrame([
        {"batch_id":"late","sku":"A","quantity":10,"expiry_date":"2027-02-01"},
        {"batch_id":"early","sku":"A","quantity":8,"expiry_date":"2027-01-01"},
    ])
    result = fefo_dispatch(batches, "A", 12)
    assert result.iloc[0]["batch_id"] == "early"
    assert result.iloc[0]["dispatch_quantity"] == 8
    assert result.iloc[1]["dispatch_quantity"] == 4

def test_inventory_flags_forecast_stockout():
    products = pd.DataFrame([{"sku":"A","current_stock":20,"daily_demand":5,"reorder_point":10}])
    forecast = pd.DataFrame({"sku":["A"]*7,"forecast_demand":[5]*7})
    result = inventory_status(products, forecast)
    assert bool(result.iloc[0]["stockout_risk"]) is True
