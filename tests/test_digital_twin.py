
import pandas as pd

from src.warehouse_state import WarehouseState
from src.digital_twin_simulation import run_warehouse_simulation


def test_digital_twin_simulation_runs():
    state = WarehouseState(data_dir="data", worker_count=6)

    order_lines = pd.read_csv("data/order_lines.csv")

    result = run_warehouse_simulation(
        state=state,
        order_lines=order_lines,
        demand_multiplier=1.0,
        workers=6,
        as_of="2026-11-03"
    )

    assert result["orders_processed"] > 0
    assert result["orders_dispatched"] + result["orders_cancelled"] == (
        result["orders_processed"]
    )

    assert not result["order_results"].empty


def test_workers_are_released():
    state = WarehouseState(data_dir="data", worker_count=6)

    order_lines = pd.read_csv("data/order_lines.csv")

    run_warehouse_simulation(
        state=state,
        order_lines=order_lines,
        as_of="2026-11-03"
    )

    workers = state.get_workers()

    assert (workers["status"] == "Available").all()


def test_simulation_records_events():
    state = WarehouseState(data_dir="data", worker_count=6)

    order_lines = pd.read_csv("data/order_lines.csv")

    result = run_warehouse_simulation(
        state=state,
        order_lines=order_lines,
        as_of="2026-11-03"
    )

    assert len(result["event_history"]) > 1


def test_inventory_never_becomes_negative():
    state = WarehouseState(data_dir="data", worker_count=6)

    order_lines = pd.read_csv("data/order_lines.csv")

    run_warehouse_simulation(
        state=state,
        order_lines=order_lines,
        as_of="2026-11-03"
    )

    assert (state.products["current_stock"] >= 0).all()
    assert (state.batches["quantity"] >= 0).all()
