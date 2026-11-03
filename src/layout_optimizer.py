
from pathlib import Path

import numpy as np
import pandas as pd


def _normalize(series):
    """Normalize values to a 0–1 range."""
    minimum = series.min()
    maximum = series.max()

    if maximum == minimum:
        return pd.Series(0.0, index=series.index)

    return (series - minimum) / (maximum - minimum)


def optimize_warehouse_layout(
    data_dir="data",
    rows=3,
    columns=4,
    dispatch_point=(0, 0),
):
    """
    Assign high-demand SKUs to warehouse slots
    closest to the dispatch point.

    Uses sales velocity and order-picking frequency.
    """

    data_path = Path(data_dir)

    products = pd.read_csv(data_path / "products.csv")
    sales = pd.read_csv(data_path / "sales.csv")
    order_lines = pd.read_csv(data_path / "order_lines.csv")

    sales["date"] = pd.to_datetime(sales["date"])

    # Historical sales velocity
    total_days = max(
        (sales["date"].max() - sales["date"].min()).days + 1,
        1,
    )

    sales_velocity = (
        sales.groupby("sku")["quantity"].sum() / total_days
    )

    # Order-picking frequency
    picking_frequency = order_lines.groupby("sku").agg(
        total_picks=("quantity", "sum"),
        order_frequency=("order_id", "nunique"),
    )

    # Combine product information and demand signals
    analysis = products.copy()

    analysis["sales_velocity"] = (
        analysis["sku"].map(sales_velocity).fillna(0)
    )

    analysis["total_picks"] = (
        analysis["sku"].map(picking_frequency["total_picks"]).fillna(0)
    )

    analysis["order_frequency"] = (
        analysis["sku"].map(
            picking_frequency["order_frequency"]
        ).fillna(0)
    )

    # Normalize demand signals
    analysis["sales_score"] = _normalize(
        analysis["sales_velocity"]
    )

    analysis["picking_score"] = _normalize(
        analysis["order_frequency"]
    )

    # Weighted demand score
    analysis["demand_score"] = (
        0.50 * analysis["sales_score"]
        + 0.50 * analysis["picking_score"]
    )

    # Generate warehouse slots
    slots = []

    for row in range(rows):
        for column in range(columns):
            distance = (
                abs(row - dispatch_point[0])
                + abs(column - dispatch_point[1])
            )

            slots.append({
                "row": row,
                "column": column,
                "slot": f"R{row + 1}-C{column + 1}",
                "distance": distance,
            })

    slots_df = pd.DataFrame(slots)

    if len(analysis) > len(slots_df):
        raise ValueError(
            "Warehouse grid has fewer slots than available SKUs."
        )

    # Assign highest-demand products to nearest slots
    analysis = analysis.sort_values(
        ["demand_score", "sales_velocity", "sku"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    slots_df = slots_df.sort_values(
        ["distance", "row", "column"]
    ).reset_index(drop=True)

    layout = pd.concat(
        [analysis, slots_df.iloc[:len(analysis)]],
        axis=1,
    )

    # Estimate weighted picking-distance score
    layout["weighted_distance"] = (
        layout["order_frequency"] * layout["distance"]
    )

    total_weighted_distance = layout["weighted_distance"].sum()

    total_picks = layout["order_frequency"].sum()

    average_picking_distance = (
        total_weighted_distance / total_picks
        if total_picks > 0
        else 0
    )

    # Classify warehouse zones
    layout["zone"] = pd.cut(
        layout["distance"],
        bins=[-1, 1, 2, float("inf")],
        labels=["A - Fast Access", "B - Medium Access", "C - Remote"],
    )

    return {
        "layout": layout.sort_values("demand_score", ascending=False),
        "average_picking_distance": average_picking_distance,
        "total_weighted_distance": total_weighted_distance,
        "total_skus": len(layout),
        "grid_slots": rows * columns,
    }


def compare_warehouse_layouts(data_dir="data", rows=3, columns=4):
    """
    Compare alphabetical baseline SKU placement
    against demand-based optimized placement.
    """

    result = optimize_warehouse_layout(
        data_dir=data_dir,
        rows=rows,
        columns=columns,
    )

    layout = result["layout"].copy()

    # Baseline: alphabetical SKU assignment
    baseline = layout.sort_values("sku").reset_index(drop=True)

    slots = []

    for row in range(rows):
        for column in range(columns):
            distance = row + column

            slots.append({
                "slot": f"R{row + 1}-C{column + 1}",
                "distance": distance,
            })

    baseline_slots = pd.DataFrame(slots)

    baseline["baseline_distance"] = (
        baseline_slots["distance"].iloc[:len(baseline)]
        .to_numpy()
    )

    baseline_score = (
        baseline["order_frequency"]
        * baseline["baseline_distance"]
    ).sum()

    total_picks = baseline["order_frequency"].sum()

    baseline_average = (
        baseline_score / total_picks
        if total_picks > 0 else 0
    )

    optimized_average = result["average_picking_distance"]

    improvement = (
        ((baseline_average - optimized_average) / baseline_average) * 100
        if baseline_average > 0 else 0
    )

    return {
        "baseline_distance": baseline_average,
        "optimized_distance": optimized_average,
        "improvement_pct": improvement,
        "layout": result["layout"],
    }


def classify_abc_products(layout):
    """Classify SKUs using cumulative picking contribution."""

    result = layout.copy()

    result = result.sort_values(
        ["order_frequency", "sku"],
        ascending=[False, True],
    ).reset_index(drop=True)

    total = result["order_frequency"].sum()

    if total == 0:
        result["cumulative_percentage"] = 0.0
        result["abc_class"] = "C"
        return result

    result["cumulative_percentage"] = (
        result["order_frequency"].cumsum() / total * 100
    )

    result["abc_class"] = "C"

    # Class A: cumulative contribution up to and including 80%
    # Class B: cumulative contribution up to and including 95%
    # Class C: remaining products
    previous_cumulative = (
        result["cumulative_percentage"]
        - result["order_frequency"] / total * 100
    )

    result.loc[
        previous_cumulative < 80,
        "abc_class"
    ] = "A"

    result.loc[
        (previous_cumulative >= 80)
        & (previous_cumulative < 95),
        "abc_class"
    ] = "B"

    return result


def optimize_abc_layout(data_dir="data", rows=3, columns=4):
    """Assign warehouse slots using ABC classification."""

    result = optimize_warehouse_layout(
        data_dir=data_dir,
        rows=rows,
        columns=columns,
    )

    classified = classify_abc_products(result["layout"])

    # A first, then B, then C.
    class_order = {"A": 0, "B": 1, "C": 2}

    classified["_class_order"] = (
        classified["abc_class"].map(class_order)
    )

    classified = classified.sort_values(
        ["_class_order", "order_frequency", "sku"],
        ascending=[True, False, True],
    ).reset_index(drop=True)

    slots = []

    for row in range(rows):
        for column in range(columns):
            slots.append({
                "slot": f"R{row + 1}-C{column + 1}",
                "row": row,
                "column": column,
                "distance": row + column,
            })

    slots_df = pd.DataFrame(slots).sort_values(
        ["distance", "row", "column"]
    ).reset_index(drop=True)

    if len(classified) > len(slots_df):
        raise ValueError("Insufficient warehouse slots.")

    classified = classified.drop(
      columns=["_class_order", "slot", "row", "column", "distance"],
      errors="ignore"
    ).reset_index(drop=True)

    assigned_slots = (
      slots_df.iloc[:len(classified)]
      .reset_index(drop=True)
    )

    classified = pd.concat(
      [classified, assigned_slots],
      axis=1,
    )

    total_picks = classified["order_frequency"].sum()

    average_distance = (
        classified["weighted_distance"].sum() / total_picks
        if total_picks > 0 else 0
    )

    return {
        "layout": classified,
        "average_picking_distance": average_distance,
        "total_skus": len(classified),
    }

def compare_slotting_strategies(data_dir="data", rows=3, columns=4):
    baseline = compare_warehouse_layouts(
        data_dir=data_dir,
        rows=rows,
        columns=columns,
    )

    demand = optimize_warehouse_layout(
        data_dir=data_dir,
        rows=rows,
        columns=columns,
    )

    abc = optimize_abc_layout(
        data_dir=data_dir,
        rows=rows,
        columns=columns,
    )

    results = pd.DataFrame([
        {
            "strategy": "Alphabetical Baseline",
            "average_distance": baseline["baseline_distance"],
        },
        {
            "strategy": "Demand-Based",
            "average_distance": demand["average_picking_distance"],
        },
        {
            "strategy": "ABC-Based",
            "average_distance": abc["average_picking_distance"],
        },
    ])

    return results
