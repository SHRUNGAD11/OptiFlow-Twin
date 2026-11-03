import pandas as pd

def calculate_kpis(products, inventory, simulation, batches, sales) -> dict:
    total_stock = int(products["current_stock"].sum())
    total_demand = float(sales["quantity"].sum())
    stockout_count = int(inventory["stockout_risk"].sum())
    stockout_rate = stockout_count / max(len(products), 1) * 100
    orders = simulation["orders_processed"]
    # Synthetic data has no observed customer cancellation/backorder table; service level is estimated
    # as the share of SKUs whose on-hand stock covers the forecast horizon.
    service_level = 100.0 * (1 - stockout_count / max(len(products), 1))
    return {"total_stock":total_stock, "stockout_rate_pct":stockout_rate,
            "service_level_pct":service_level,
            "avg_fulfillment_minutes":simulation["avg_fulfillment_minutes"],
            "orders_processed":orders, "historical_units_sold":total_demand,
            "batch_units":int(batches["quantity"].sum())}
