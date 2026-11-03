
import pytest
from src.warehouse_state import WarehouseState


@pytest.fixture
def warehouse():
    return WarehouseState(data_dir="data", worker_count=6)


def test_warehouse_initialization(warehouse):
    assert not warehouse.products.empty
    assert not warehouse.orders.empty
    assert len(warehouse.workers) == 6


def test_inventory_read(warehouse):
    inventory = warehouse.get_inventory()
    assert not inventory.empty
    assert warehouse.get_stock(inventory.iloc[0]["sku"]) >= 0


def test_stock_receiving(warehouse):
    sku = warehouse.products.iloc[0]["sku"]
    old_stock = warehouse.get_stock(sku)

    warehouse.receive_stock(
        sku=sku,
        quantity=20,
        batch_id="TEST-BATCH-001",
        expiry_date="2027-12-31"
    )

    assert warehouse.get_stock(sku) == old_stock + 20


def test_fefo_dispatch(warehouse):
    sku = warehouse.products.iloc[0]["sku"]

    result = warehouse.dispatch_fefo(
        sku=sku,
        required_quantity=5,
        as_of="2026-11-03"
    )

    assert result["dispatch_quantity"].sum() <= 5
    assert warehouse.get_stock(sku) >= 0


def test_worker_assignment(warehouse):
    worker_id = warehouse.workers.iloc[0]["worker_id"]
    order_id = warehouse.orders.iloc[0]["order_id"]

    warehouse.assign_worker(worker_id, order_id)

    worker = warehouse.get_workers()
    assigned = worker[worker["worker_id"] == worker_id].iloc[0]

    assert assigned["status"] == "Busy"


def test_worker_task_completion(warehouse):
    worker_id = warehouse.workers.iloc[0]["worker_id"]
    order_id = warehouse.orders.iloc[0]["order_id"]

    warehouse.assign_worker(worker_id, order_id)
    warehouse.complete_worker_task(worker_id)

    worker = warehouse.get_workers()
    completed = worker[worker["worker_id"] == worker_id].iloc[0]

    assert completed["status"] == "Available"


def test_event_history(warehouse):
    warehouse.receive_stock(
        sku=warehouse.products.iloc[0]["sku"],
        quantity=10,
        batch_id="EVENT-TEST-001",
        expiry_date="2027-12-31"
    )

    events = warehouse.get_event_history()
    assert len(events) >= 2


def test_warehouse_metrics(warehouse):
    metrics = warehouse.get_metrics()

    assert metrics["total_skus"] > 0
    assert metrics["total_orders"] > 0
    assert metrics["total_workers"] == 6
