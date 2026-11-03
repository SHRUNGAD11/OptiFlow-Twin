
import pandas as pd

from src.warehouse_state import WarehouseState
from src.digital_twin_simulation import run_warehouse_simulation
from src.digital_twin_simulation_static_backup import (
    run_warehouse_simulation as run_static_simulation
)


def run_benchmark():

    order_lines = pd.read_csv("data/order_lines.csv")

    scenarios = [
        {
            "name": "Normal",
            "demand": 1.0,
            "workers": 6
        },
        {
            "name": "High Demand",
            "demand": 2.0,
            "workers": 3
        }
    ]

    results = []

    for scenario in scenarios:

        for scheduler_name, simulation_function in [
            ("Static", run_static_simulation),
            ("Dynamic", run_warehouse_simulation)
        ]:

            state = WarehouseState(
                data_dir="data",
                worker_count=6
            )

            result = simulation_function(
                state=state,
                order_lines=order_lines.copy(),
                demand_multiplier=scenario["demand"],
                workers=scenario["workers"],
                as_of="2026-11-03"
            )

            orders = result["order_results"]

            for order_type in ["Express", "Scheduled"]:

                subset = orders[
                    orders["priority"] == order_type
                ]

                results.append({
                    "scenario": scenario["name"],
                    "scheduler": scheduler_name,
                    "order_type": order_type,
                    "orders_processed": len(subset),
                    "average_wait": subset["wait_minutes"].mean(),
                    "average_fulfillment": subset[
                        "fulfillment_minutes"
                    ].mean(),
                    "dispatch_rate": (
                        (subset["status"] == "Dispatched").mean()
                        * 100
                        if not subset.empty else 0
                    )
                })

    comparison = pd.DataFrame(results)

    print("\nSCHEDULER PERFORMANCE COMPARISON\n")

    print(
        comparison.round(2).to_string(index=False)
    )

    comparison.to_csv(
        "data/scheduler_benchmark_results.csv",
        index=False
    )

    print("\nResults saved to data/scheduler_benchmark_results.csv")


if __name__ == "__main__":
    run_benchmark()
