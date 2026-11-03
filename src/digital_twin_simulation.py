
import pandas as pd
import simpy

from src.warehouse_state import WarehouseState
from src.order_prioritization import calculate_order_priorities


def run_warehouse_simulation(
    state: WarehouseState,
    order_lines: pd.DataFrame = None,
    demand_multiplier: float = 1.0,
    workers: int = None,
    as_of=None
) -> dict:
    """
    Run an event-driven warehouse digital twin with dynamic
    order prioritization, worker allocation, FEFO picking,
    packing and dispatch.
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

    orders = orders[
        orders["status"] == "Pending"
    ].copy()

    if orders.empty:
        return {
            "orders_processed": 0,
            "orders_dispatched": 0,
            "orders_cancelled": 0,
            "avg_wait_minutes": 0.0,
            "avg_fulfillment_minutes": 0.0,
            "order_results": pd.DataFrame(),
            "warehouse_metrics": state.get_metrics(),
            "event_history": state.get_event_history()
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

    results = []
    pending_orders = []

    available_worker_ids = (
        state.workers[
            state.workers["status"] == "Available"
        ]["worker_id"]
        .head(workers)
        .tolist()
    )

    # Store wakes the dispatcher when an order arrives
    # or a worker becomes available.
    wake_store = simpy.Store(env)

    def check_inventory(lines):
        """Check all requested SKUs before deducting stock."""

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

            batch_stock = eligible_batches[
                "quantity"
            ].sum()

            if min(available_stock, batch_stock) < quantity:
                return False

        return True

    def process_order(order, worker_id, priority_score):

        order_id = order.order_id

        queue_wait = max(
            0.0,
            float(env.now - order.arrival_minute)
        )

        arrival_time = float(order.arrival_minute)

        state.assign_worker(worker_id, order_id)

        state._record_event(
            "ORDER_PICKING_STARTED",
            f"Picking started for {order_id}",
            {
                "order_id": order_id,
                "worker_id": worker_id,
                "priority_score": priority_score,
                "queue_wait_minutes": queue_wait
            }
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

        dispatch_time = float(env.now)

        results.append({
            "order_id": order_id,
            "priority": order.priority,
            "priority_score": priority_score,
            "worker_id": worker_id,
            "wait_minutes": queue_wait,
            "fulfillment_minutes": (
                dispatch_time - arrival_time
            ),
            "dispatch_time": dispatch_time,
            "status": final_status
        })

        # Release worker back to the available pool.
        available_worker_ids.append(worker_id)

        # Wake dispatcher to assign the next order.
        yield wake_store.put(1)

    def dynamic_dispatcher():
        """
        Dynamically select the highest-scoring pending order
        whenever a worker becomes available.
        """

        while True:

            yield wake_store.get()

            while pending_orders and available_worker_ids:

                current_time = (
                    base_time + pd.Timedelta(float(env.now), unit="min")
                )

                waiting_orders = pd.DataFrame([
                    {
                        "order_id": item["order"].order_id,
                        "arrival_time": item["sim_arrival_time"],
                        "priority": item["order"].priority,
                        "pick_units": item["order"].pick_units
                    }
                    for item in pending_orders
                ])

                scored_orders = calculate_order_priorities(
                    waiting_orders,
                    current_time=current_time
                )

                selected_id = scored_orders.iloc[0][
                    "order_id"
                ]

                selected_score = float(
                    scored_orders.iloc[0]["priority_score"]
                )

                selected_index = next(
                    i for i, item in enumerate(pending_orders)
                    if item["order"].order_id == selected_id
                )

                selected = pending_orders.pop(selected_index)

                worker_id = available_worker_ids.pop(0)

                env.process(
                    process_order(
                        selected["order"],
                        worker_id,
                        selected_score
                    )
                )

    def order_arrival_process(order):

        yield env.timeout(float(order.arrival_minute))

        sim_arrival_time = (
            base_time + pd.Timedelta(float(order.arrival_minute), unit="min")
        )

        pending_orders.append({
            "order": order,
            "sim_arrival_time": sim_arrival_time
        })

        state._record_event(
            "ORDER_ARRIVED",
            f"Order {order.order_id} arrived",
            {
                "order_id": order.order_id,
                "priority": order.priority
            }
        )

        yield wake_store.put(1)

    # Start the dispatcher.
    env.process(dynamic_dispatcher())

    # Schedule all order arrivals.
    for order in orders.itertuples(index=False):
        env.process(order_arrival_process(order))

    # Run the complete simulation.
    env.run()

    result_df = pd.DataFrame(results)

    dispatched = (
        int(
            (result_df["status"] == "Dispatched").sum()
        )
        if not result_df.empty else 0
    )

    cancelled = (
        int(
            (result_df["status"] == "Cancelled").sum()
        )
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
