import numpy as np
import pandas as pd

def inventory_status(products: pd.DataFrame, forecast: pd.DataFrame, demand_multiplier: float = 1.0) -> pd.DataFrame:
    demand = forecast.groupby("sku")["forecast_demand"].sum().rename("forecast_7d")
    result = products.merge(demand, on="sku", how="left")
    result["forecast_7d"] = result["forecast_7d"].fillna(result["daily_demand"] * 7) * demand_multiplier
    result["effective_daily_demand"] = result["forecast_7d"] / 7
    result["days_of_cover"] = np.where(result["effective_daily_demand"] > 0,
                                       result["current_stock"] / result["effective_daily_demand"], np.inf)
    result["stockout_risk"] = result["forecast_7d"] > result["current_stock"]
    result["reorder_suggested"] = result["current_stock"] < result["reorder_point"]
    return result

def fefo_dispatch(batches: pd.DataFrame, sku: str, requested_quantity: int) -> pd.DataFrame:
    """Allocate dispatch quantity from earliest-expiring eligible batches first."""
    data = batches[batches["sku"] == sku].copy()
    data["expiry_date"] = pd.to_datetime(data["expiry_date"])
    data = data.sort_values("expiry_date")
    remaining = int(requested_quantity)
    allocations = []
    for _, batch in data.iterrows():
        allocated = min(int(batch["quantity"]), remaining)
        if allocated > 0:
            allocations.append({"batch_id": batch["batch_id"], "expiry_date": batch["expiry_date"].date(),
                                "available_quantity": int(batch["quantity"]), "dispatch_quantity": allocated})
            remaining -= allocated
        if remaining == 0:
            break
    result = pd.DataFrame(allocations, columns=["batch_id","expiry_date","available_quantity","dispatch_quantity"])
    if result.empty:
        result = pd.DataFrame([{"batch_id":"No eligible stock","expiry_date":pd.NaT,"available_quantity":0,"dispatch_quantity":0}])
    result["unfulfilled_quantity"] = remaining
    return result

def replenishment_plan(inventory: pd.DataFrame) -> pd.DataFrame:
    data = inventory.copy()
    data["suggested_order_quantity"] = (data["reorder_point"] * 2 - data["current_stock"]).clip(lower=0).astype(int)
    data = data[data["suggested_order_quantity"] > 0]
    return data[["sku","product_name","current_stock","reorder_point","suggested_order_quantity","lead_time_days"]]
