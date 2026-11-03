import numpy as np
import pandas as pd


def inventory_status(
    products,
    forecast,
    demand_multiplier=1.0,
    service_z=1.65,
    ordering_cost=50.0,
    annual_holding_cost_per_unit=2.0
):
    """
    Calculate inventory optimization metrics.

    Supports older product datasets without lead_time_days.
    """

    # Validate input columns
    required_product_columns = ["sku", "current_stock"]
    required_forecast_columns = ["sku", "forecast_demand"]

    for col in required_product_columns:
        if col not in products.columns:
            raise ValueError(f"Missing products column: {col}")

    for col in required_forecast_columns:
        if col not in forecast.columns:
            raise ValueError(f"Missing forecast column: {col}")

    # Aggregate forecast demand by SKU
    demand = (
        forecast.groupby("sku")["forecast_demand"]
        .agg(["sum", "mean", "std"])
        .reset_index()
    )

    demand = demand.rename(
        columns={
            "sum": "forecast_7d",
            "mean": "forecast_daily_mean",
            "std": "forecast_daily_std"
        }
    )

    # Merge product and forecast information
    out = products.merge(demand, on="sku", how="left")

    # Handle missing lead time
    if "lead_time_days" not in out.columns:
        out["lead_time_days"] = 1

    out["lead_time_days"] = (
        pd.to_numeric(out["lead_time_days"], errors="coerce")
        .fillna(1)
        .clip(lower=1)
    )

    # Handle missing forecast values
    out["forecast_7d"] = out["forecast_7d"].fillna(0)
    out["forecast_daily_mean"] = out["forecast_daily_mean"].fillna(
        out["daily_demand"]
        if "daily_demand" in out.columns
        else 0
    )
    out["forecast_daily_std"] = out["forecast_daily_std"].fillna(0)

    # Ensure numeric stock values
    out["current_stock"] = pd.to_numeric(
        out["current_stock"], errors="coerce"
    ).fillna(0)

    # Calculate effective daily demand
    out["effective_daily_demand"] = (
        out["forecast_daily_mean"] * demand_multiplier
    )

    # 1. Dynamic safety stock
    out["safety_stock"] = (
        service_z
        * out["forecast_daily_std"]
        * np.sqrt(out["lead_time_days"])
    ).round().astype(int)

    # 2. Dynamic reorder point
    out["dynamic_reorder_point"] = (
        out["effective_daily_demand"] * out["lead_time_days"]
        + out["safety_stock"]
    ).round().astype(int)

    # Retain legacy reorder point column for compatibility
    out["reorder_point_calculated"] = out["dynamic_reorder_point"]

    # 3. Economic Order Quantity (EOQ)
    annual_demand = out["effective_daily_demand"] * 365

    if annual_holding_cost_per_unit <= 0:
        raise ValueError("Annual holding cost must be greater than zero.")

    if ordering_cost < 0:
        raise ValueError("Ordering cost cannot be negative.")

    out["eoq"] = np.sqrt(
        (2 * annual_demand * ordering_cost)
        / annual_holding_cost_per_unit
    ).round().astype(int)

    # 4. Suggested order quantity
    out["suggested_order_quantity"] = (
        out["dynamic_reorder_point"] - out["current_stock"]
    ).clip(lower=0).round().astype(int)

    # 5. Days of inventory cover
    out["days_of_cover"] = (
        out["current_stock"]
        / out["effective_daily_demand"].replace(0, np.nan)
    )

    # 6. Stockout risk
    out["stockout_risk"] = (
        out["current_stock"] < out["forecast_7d"]
    )

    # 7. Reorder recommendation
    out["reorder_required"] = (
        out["current_stock"] <= out["dynamic_reorder_point"]
    )
    # Backward compatibility with recommendations.py
    out["reorder_suggested"] = out["reorder_required"]

    return out


def fefo_dispatch(batches, sku, required_qty, as_of=None):
    """
    FEFO: First Expiry, First Out.

    Args:
        batches: DataFrame containing batch_id, sku, quantity, expiry_date.
        sku: SKU to dispatch.
        required_qty: Required quantity.
        as_of: Reference date for checking expiry.

    Returns:
        DataFrame containing dispatched batches and
        unfulfilled_quantity.
    """

    if required_qty < 0:
        raise ValueError("Required quantity cannot be negative.")

    required_columns = ["batch_id", "sku", "quantity", "expiry_date"]

    for col in required_columns:
        if col not in batches.columns:
            raise ValueError(f"Missing batch column: {col}")

    if as_of is None:
        as_of = pd.Timestamp.today().normalize()
    else:
        as_of = pd.Timestamp(as_of).normalize()

    data = batches.copy()

    data["expiry_date"] = pd.to_datetime(
        data["expiry_date"], errors="coerce"
    )

    data["quantity"] = pd.to_numeric(
        data["quantity"], errors="coerce"
    ).fillna(0).clip(lower=0)

    # Select only the requested SKU
    eligible = data[
        (data["sku"] == sku)
        & data["expiry_date"].notna()
        & (data["expiry_date"] >= as_of)
        & (data["quantity"] > 0)
    ].copy()

    # FEFO sorting: earliest expiry first
    eligible = eligible.sort_values(
        "expiry_date", ascending=True
    )

    remaining = float(required_qty)
    dispatch_records = []

    for _, batch in eligible.iterrows():

        if remaining <= 0:
            break

        available = float(batch["quantity"])
        dispatched = min(available, remaining)

        if dispatched > 0:
            record = batch.to_dict()
            record["dispatch_quantity"] = dispatched

            dispatch_records.append(record)
            remaining -= dispatched

    result = pd.DataFrame(
        dispatch_records,
        columns=list(data.columns) + ["dispatch_quantity"]
    )

    # Include the unfulfilled quantity in the result
    result["unfulfilled_quantity"] = max(0, remaining)

    return result


def replenishment_plan(inventory):
    """
    Generate a replenishment plan using inventory optimization metrics.

    Args:
        inventory: DataFrame returned by inventory_status().

    Returns:
        DataFrame containing recommended replenishment quantities.
    """

    plan = inventory.copy()

    # Ensure required columns exist
    if "suggested_order_quantity" not in plan.columns:
        if "dynamic_reorder_point" in plan.columns:
            plan["suggested_order_quantity"] = (
                plan["dynamic_reorder_point"] - plan["current_stock"]
            ).clip(lower=0)
        else:
            plan["suggested_order_quantity"] = 0

    if "reorder_required" not in plan.columns:
        plan["reorder_required"] = (
            plan["suggested_order_quantity"] > 0
        )

    if "eoq" not in plan.columns:
        plan["eoq"] = 0

    # Recommended order quantity
    plan["recommended_order_quantity"] = plan[
        "suggested_order_quantity"
    ].fillna(0).clip(lower=0).round().astype(int)

    # Include only products requiring replenishment
    plan = plan[
        (plan["reorder_required"])
        & (plan["recommended_order_quantity"] > 0)
    ].copy()

    return plan

