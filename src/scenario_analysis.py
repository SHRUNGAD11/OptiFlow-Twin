from pathlib import Path

import pandas as pd

from src.warehouse_state import WarehouseState
from src.digital_twin_simulation import run_warehouse_simulation


DEFAULT_SCENARIOS = [
    {
        "scenario": "Normal Operations",
        "demand_multiplier": 1.0,
        "workers": 6
    },
    {
        "scenario": "High Demand",
        "demand_multiplier": 1.5,
        "workers": 6
    },
    {
        "scenario": "Peak Demand",
        "demand_multiplier": 2.0,
        "workers": 6
    },
    {
        "scenario": "Workforce Shortage",
        "demand_multiplier": 1.0,
        "workers": 3
    },
    {
        "scenario": "Peak Demand + Shortage",
        "demand_multiplier": 1.5,
        "workers": 3
    }
]


def run_scenario_comparison(
    data_dir="data",
    order_limit=200,
    scenarios=None
):
    """
    Run independent warehouse simulations and compare results.

    Every scenario starts with a fresh warehouse state.
    """

    data_path = Path(data_dir)

    if order_limit < 1:
        raise ValueError("Order limit must be positive.")

    orders = pd.read_csv(data_path / "orders.csv")
    order_lines = pd.read_csv(data_path / "order_lines.csv")

    selected_orders = orders.head(order_limit).copy()

    selected_ids = selected_orders["order_id"]

    selected_lines = order_lines[
        order_lines["order_id"].isin(selected_ids)
    ].copy()

    if scenarios is None:
        scenarios = DEFAULT_SCENARIOS

    results = []

    for config in scenarios:

        worker_count = int(config["workers"])
        demand = float(config["demand_multiplier"])

        if worker_count < 1:
            raise ValueError("Worker count must be positive.")

        if demand <= 0:
            raise ValueError("Demand multiplier must be positive.")

        state = WarehouseState(
            data_dir=str(data_path),
            worker_count=worker_count
        )

        state.orders = selected_orders.copy()

        simulation = run_warehouse_simulation(
            state=state,
            order_lines=selected_lines,
            demand_multiplier=demand,
            workers=worker_count
        )

        processed = simulation["orders_processed"]
        dispatched = simulation["orders_dispatched"]

        dispatch_rate = (
            dispatched / processed * 100
            if processed else 0.0
        )

        final_metrics = state.get_metrics()

        results.append({
            "scenario": config["scenario"],
            "demand_multiplier": demand,
            "workers": worker_count,
            "orders_processed": processed,
            "orders_dispatched": dispatched,
            "orders_cancelled": simulation["orders_cancelled"],
            "dispatch_rate_pct": round(dispatch_rate, 2),
            "avg_wait_minutes": round(
                simulation["avg_wait_minutes"], 2
            ),
            "avg_fulfillment_minutes": round(
                simulation["avg_fulfillment_minutes"], 2
            ),
            "available_workers": final_metrics["available_workers"],
            "total_events": final_metrics["total_events"]
        })

    return pd.DataFrame(results)
