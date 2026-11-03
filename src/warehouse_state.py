
from pathlib import Path
from datetime import datetime
import pandas as pd


class WarehouseState:
    """
    Central state engine for the OptiFlow Twin warehouse.

    Manages:
    - Product inventory
    - Batch inventory and FEFO dispatch
    - Customer orders
    - Warehouse workers
    - Operational event history
    """

    def __init__(self, data_dir="data", worker_count=6):

        self.data_dir = Path(data_dir)

        # Load existing project datasets
        self.products = pd.read_csv(
            self.data_dir / "products.csv"
        )

        self.batches = pd.read_csv(
            self.data_dir / "batches.csv"
        )

        self.orders = pd.read_csv(
            self.data_dir / "orders.csv"
        )

        self.sales = pd.read_csv(
            self.data_dir / "sales.csv"
        )

        self.transactions = pd.read_csv(
            self.data_dir / "transactions.csv"
        )

        # Normalize data types
        self.products["current_stock"] = pd.to_numeric(
            self.products["current_stock"], errors="coerce"
        ).fillna(0)

        self.batches["quantity"] = pd.to_numeric(
            self.batches["quantity"], errors="coerce"
        ).fillna(0)

        self.batches["expiry_date"] = pd.to_datetime(
            self.batches["expiry_date"], errors="coerce"
        )

        # Initialize warehouse workers
        self.workers = pd.DataFrame({
            "worker_id": [
                f"W{i:03d}" for i in range(1, worker_count + 1)
            ],
            "status": ["Available"] * worker_count,
            "current_order": [None] * worker_count
        })

        # Operational event history
        self.events = []

        self._record_event(
            "WAREHOUSE_INITIALIZED",
            "Warehouse state engine initialized",
            {
                "products": len(self.products),
                "batches": len(self.batches),
                "orders": len(self.orders),
                "workers": worker_count
            }
        )

        self.validate_state()

    # --------------------------------------------------
    # EVENT MANAGEMENT
    # --------------------------------------------------

    def _record_event(self, event_type, description, details=None):

        event = {
            "event_id": f"EVT{len(self.events) + 1:06d}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "event_type": event_type,
            "description": description,
            "details": details or {}
        }

        self.events.append(event)

        return event

    def get_event_history(self):

        return pd.DataFrame(self.events)

    # --------------------------------------------------
    # INVENTORY MANAGEMENT
    # --------------------------------------------------

    def get_inventory(self, sku=None):

        if sku is None:
            return self.products.copy()

        result = self.products[
            self.products["sku"] == sku
        ]

        return result.copy()

    def get_stock(self, sku):

        product = self.products[
            self.products["sku"] == sku
        ]

        if product.empty:
            raise ValueError(f"Unknown SKU: {sku}")

        return float(product.iloc[0]["current_stock"])

    def receive_stock(
        self,
        sku,
        quantity,
        batch_id,
        expiry_date
    ):

        if quantity <= 0:
            raise ValueError("Quantity must be positive.")

        if batch_id in self.batches["batch_id"].astype(str).values:
            raise ValueError(f"Batch already exists: {batch_id}")

        product = self.products[
            self.products["sku"] == sku
        ]

        if product.empty:
            raise ValueError(f"Unknown SKU: {sku}")

        expiry = pd.Timestamp(expiry_date)

        if pd.isna(expiry):
            raise ValueError("Invalid expiry date.")

        self.batches.loc[len(self.batches)] = {
            "batch_id": batch_id,
            "sku": sku,
            "quantity": quantity,
            "expiry_date": expiry
        }

        self.products.loc[
            self.products["sku"] == sku,
            "current_stock"
        ] += quantity

        self._record_event(
            "STOCK_RECEIVED",
            f"Received {quantity} units of {sku}",
            {
                "sku": sku,
                "quantity": quantity,
                "batch_id": batch_id,
                "expiry_date": str(expiry.date())
            }
        )

        self.validate_state()

        return self.get_stock(sku)

    # --------------------------------------------------
    # FEFO INVENTORY DISPATCH
    # --------------------------------------------------

    def dispatch_fefo(self, sku, required_quantity, as_of=None):

        if required_quantity < 0:
            raise ValueError("Quantity cannot be negative.")

        if as_of is None:
            as_of = pd.Timestamp.now().normalize()
        else:
            as_of = pd.Timestamp(as_of).normalize()

        if sku not in self.products["sku"].values:
            raise ValueError(f"Unknown SKU: {sku}")

        eligible = self.batches[
            (self.batches["sku"] == sku)
            & (self.batches["quantity"] > 0)
            & (self.batches["expiry_date"].notna())
            & (self.batches["expiry_date"] >= as_of)
        ].copy()

        eligible = eligible.sort_values(
            "expiry_date",
            ascending=True
        )

        remaining = float(required_quantity)
        dispatch_records = []

        for index, batch in eligible.iterrows():

            if remaining <= 0:
                break

            available = float(batch["quantity"])

            dispatched = min(available, remaining)

            if dispatched > 0:

                self.batches.at[
                    index, "quantity"
                ] -= dispatched

                dispatch_records.append({
                    "batch_id": batch["batch_id"],
                    "sku": sku,
                    "expiry_date": batch["expiry_date"],
                    "dispatch_quantity": dispatched
                })

                remaining -= dispatched

        dispatched_total = (
            required_quantity - remaining
        )

        # Update product-level stock
        self.products.loc[
            self.products["sku"] == sku,
            "current_stock"
        ] -= dispatched_total

        result = pd.DataFrame(
            dispatch_records,
            columns=[
                "batch_id",
                "sku",
                "expiry_date",
                "dispatch_quantity"
            ]
        )

        result["unfulfilled_quantity"] = remaining

        self._record_event(
            "FEFO_DISPATCH",
            f"Dispatched {dispatched_total} units of {sku}",
            {
                "sku": sku,
                "requested": required_quantity,
                "dispatched": dispatched_total,
                "unfulfilled": remaining
            }
        )

        self.validate_state()

        return result

    # --------------------------------------------------
    # ORDER MANAGEMENT
    # --------------------------------------------------

    def get_orders(self, status=None):

        orders = self.orders.copy()

        if "status" not in orders.columns:
            orders["status"] = "Pending"

        if status is not None:
            orders = orders[
                orders["status"] == status
            ]

        return orders.copy()

    def update_order_status(self, order_id, status):

        valid_statuses = [
            "Pending",
            "Processing",
            "Packed",
            "Dispatched",
            "Cancelled"
        ]

        if status not in valid_statuses:
            raise ValueError(
                f"Invalid order status: {status}"
            )

        matches = self.orders[
            self.orders["order_id"] == order_id
        ]

        if matches.empty:
            raise ValueError(
                f"Order not found: {order_id}"
            )

        if "status" not in self.orders.columns:
            self.orders["status"] = "Pending"

        old_status = self.orders.loc[
            self.orders["order_id"] == order_id,
            "status"
        ].iloc[0]

        self.orders.loc[
            self.orders["order_id"] == order_id,
            "status"
        ] = status

        self._record_event(
            "ORDER_STATUS_UPDATED",
            f"Order {order_id}: {old_status} -> {status}",
            {
                "order_id": order_id,
                "old_status": old_status,
                "new_status": status
            }
        )

        return status

    # --------------------------------------------------
    # WORKER MANAGEMENT
    # --------------------------------------------------

    def get_workers(self):

        return self.workers.copy()

    def assign_worker(self, worker_id, order_id):

        worker = self.workers[
            self.workers["worker_id"] == worker_id
        ]

        if worker.empty:
            raise ValueError(
                f"Worker not found: {worker_id}"
            )

        if worker.iloc[0]["status"] != "Available":
            raise ValueError(
                f"Worker {worker_id} is not available."
            )

        order = self.orders[
            self.orders["order_id"] == order_id
        ]

        if order.empty:
            raise ValueError(
                f"Order not found: {order_id}"
            )

        if "status" not in self.orders.columns:
            self.orders["status"] = "Pending"

        order_status = self.orders.loc[
            self.orders["order_id"] == order_id,
            "status"
        ].iloc[0]

        if order_status != "Pending":
            raise ValueError(
                f"Order {order_id} is not pending."
            )

        self.workers.loc[
            self.workers["worker_id"] == worker_id,
            "status"
        ] = "Busy"

        self.workers.loc[
            self.workers["worker_id"] == worker_id,
            "current_order"
        ] = order_id

        self.update_order_status(
            order_id, "Processing"
        )

        self._record_event(
            "WORKER_ASSIGNED",
            f"Worker {worker_id} assigned to {order_id}",
            {
                "worker_id": worker_id,
                "order_id": order_id
            }
        )

    def complete_worker_task(self, worker_id):

        worker = self.workers[
            self.workers["worker_id"] == worker_id
        ]

        if worker.empty:
            raise ValueError(
                f"Worker not found: {worker_id}"
            )

        if worker.iloc[0]["status"] != "Busy":
            raise ValueError(
                f"Worker {worker_id} has no active task."
            )

        order_id = worker.iloc[0]["current_order"]

        self.workers.loc[
            self.workers["worker_id"] == worker_id,
            "status"
        ] = "Available"

        self.workers.loc[
            self.workers["worker_id"] == worker_id,
            "current_order"
        ] = None

        self.update_order_status(
            order_id, "Packed"
        )

        self._record_event(
            "WORKER_TASK_COMPLETED",
            f"Worker {worker_id} completed {order_id}",
            {
                "worker_id": worker_id,
                "order_id": order_id
            }
        )

    # --------------------------------------------------
    # WAREHOUSE METRICS
    # --------------------------------------------------

    def get_metrics(self):

        total_stock = self.products[
            "current_stock"
        ].sum()

        total_orders = len(self.orders)

        pending_orders = len(
            self.get_orders("Pending")
        )

        busy_workers = len(
            self.workers[
                self.workers["status"] == "Busy"
            ]
        )

        available_workers = len(
            self.workers[
                self.workers["status"] == "Available"
            ]
        )

        return {
            "total_skus": len(self.products),
            "total_stock": int(total_stock),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_workers": len(self.workers),
            "busy_workers": busy_workers,
            "available_workers": available_workers,
            "total_events": len(self.events)
        }

    # --------------------------------------------------
    # STATE VALIDATION
    # --------------------------------------------------

    def validate_state(self):

        if (self.products["current_stock"] < 0).any():
            raise ValueError(
                "Inventory stock cannot be negative."
            )

        if (self.batches["quantity"] < 0).any():
            raise ValueError(
                "Batch quantity cannot be negative."
            )

        if self.products["sku"].duplicated().any():
            raise ValueError(
                "Duplicate product SKU detected."
            )

        return True

    # --------------------------------------------------
    # COMPLETE STATE SNAPSHOT
    # --------------------------------------------------

    def get_snapshot(self):

        return {
            "inventory": self.products.copy(),
            "batches": self.batches.copy(),
            "orders": self.orders.copy(),
            "workers": self.workers.copy(),
            "events": self.get_event_history(),
            "metrics": self.get_metrics()
        }
