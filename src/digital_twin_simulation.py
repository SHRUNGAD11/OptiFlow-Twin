
import pandas as pd
import simpy

from src.warehouse_state import WarehouseState


def run_warehouse_simulation(
    state: WarehouseState,
    order_lines: pd.DataFrame = None,
    demand_multiplier: float = 1.0,
    workers: int = None,
    as_of=None
) -> dict:
    """
    Run an event-driven warehouse digital twin.

    Simulates order arrival, worker allocation, FEFO picking,
    packing and dispatch using the shared WarehouseState.
    """

    if demand_multiplier <= 0:
        raise ValueError("Demand multiplier must be positive.")

    if workers is None:
        workers = len(state.workers)

    workers = min(int(workers), len(state.workers))

    if workers < 1:
        raise ValueError("At least one worker is required.")

    if order_lines is None:
        order_lines = pd.read_csv("data/order_lines.csv")

    required_columns = {"order_id", "sku", "quantity"}

    if not required_columns.issubset(order_lines.columns):
        raise ValueError(
            f"Order lines must contain: {required_columns}"
        )

    orders = state.orders.copy()

    if "status" not in orders.columns:
        orders["status"] = "Pending"

    orders = orders[orders["status"] == "Pending"].copy()

    if orders.empty:
        return {
            "orders_processed": 0,
            "orders_dispatched": 0,
            "orders_cancelled": 0,
            "avg_wait_minutes": 0.0,
            "avg_fulfillment_minutes": 0.0,
            "order_results": pd.DataFrame()
        }

    orders["arrival_time"] = pd.to_datetime(
        orders["arrival_time"]
    )

    base_time = orders["arrival_time"].min()

    orders["arrival_minute"] = (
        orders["arrival_time"] - base_time
    ).dt.total_seconds() / 60.0

    orders["arrival_minute"] /= demand_multiplier

    if as_of is None:
        as_of = pd.Timestamp.now().normalize()
    else:
        as_of = pd.Timestamp(as_of).normalize()

    env = simpy.Environment()

    worker_resource = simpy.PriorityResource(
        env,
        capacity=workers
    )

    results = []

    def check_inventory(lines):
        """Check all requested SKUs before deducting any stock."""

        for line in lines.itertuples(index=False):
            sku = line.sku
            quantity = float(line.quantity)

            if quantity <= 0:
                return False

            available_stock = state.get_stock(sku)

            eligible_batches = state.batches[
                (state.batches["sku"] == sku)
                & (state.batches["quantity"] > 0)
                & (state.batches["expiry_date"].notna())
                & (state.batches["expiry_date"] >= as_of)
            ]

            batch_stock = eligible_batches["quantity"].sum()

            if min(available_stock, batch_stock) < quantity:
                return False

        return True

    def process_order(order):

        order_id = order.order_id

        yield env.timeout(float(order.arrival_minute))

        arrival_time = env.now
        priority = (
            0 if str(order.priority).lower() == "express" else 1
        )

        queue_start = env.now

        with worker_resource.request(priority=priority) as request:
            yield request

            wait_time = env.now - queue_start

            available_workers = state.workers[
                state.workers["status"] == "Available"
            ]

            if available_workers.empty:
                raise RuntimeError("No available warehouse worker.")

            worker_id = available_workers.iloc[0]["worker_id"]

            state.assign_worker(worker_id, order_id)

            state._record_event(
                "ORDER_PICKING_STARTED",
                f"Picking started for {order_id}",
                {"order_id": order_id, "worker_id": worker_id}
            )

            lines = order_lines[
                order_lines["order_id"] == order_id
            ]

            pick_duration = (
                2.0 + float(order.pick_units) * 0.8
            )

            yield env.timeout(pick_duration)

            inventory_available = check_inventory(lines)

            if inventory_available:

                for line in lines.itertuples(index=False):
                    state.dispatch_fefo(
                        sku=line.sku,
                        required_quantity=float(line.quantity),
                        as_of=as_of
                    )

                state._record_event(
                    "ORDER_PICKING_COMPLETED",
                    f"Picking completed for {order_id}",
                    {"order_id": order_id}
                )

                packing_duration = (
                    2.0 + float(order.items) * 0.5
                )

                yield env.timeout(packing_duration)

                state._record_event(
                    "ORDER_PACKED",
                    f"Order {order_id} packed",
                    {"order_id": order_id}
                )

                state.complete_worker_task(worker_id)

                state.update_order_status(
                    order_id,
                    "Dispatched"
                )

                final_status = "Dispatched"

            else:
                state._record_event(
                    "ORDER_INSUFFICIENT_INVENTORY",
                    f"Insufficient inventory for {order_id}",
                    {"order_id": order_id}
                )

                state.complete_worker_task(worker_id)

                state.update_order_status(
                    order_id,
                    "Cancelled"
                )

                final_status = "Cancelled"

            dispatch_time = env.now

            results.append({
                "order_id": order_id,
                "priority": order.priority,
                "worker_id": worker_id,
                "wait_minutes": wait_time,
                "fulfillment_minutes": dispatch_time - arrival_time,
                "dispatch_time": dispatch_time,
                "status": final_status
            })

    for order in orders.itertuples(index=False):
        env.process(process_order(order))

    env.run()

    result_df = pd.DataFrame(results)

    dispatched = (
        int((result_df["status"] == "Dispatched").sum())
        if not result_df.empty else 0
    )

    cancelled = (
        int((result_df["status"] == "Cancelled").sum())
        if not result_df.empty else 0
    )

    return {
        "orders_processed": len(result_df),
        "orders_dispatched": dispatched,
        "orders_cancelled": cancelled,
        "avg_wait_minutes": (
            float(result_df["wait_minutes"].mean())
            if not result_df.empty else 0.0
        ),
        "avg_fulfillment_minutes": (
            float(result_df["fulfillment_minutes"].mean())
            if not result_df.empty else 0.0
        ),
        "order_results": result_df,
        "warehouse_metrics": state.get_metrics(),
        "event_history": state.get_event_history()
    }
