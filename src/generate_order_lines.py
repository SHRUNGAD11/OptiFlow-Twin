
from pathlib import Path
import random
import pandas as pd


def generate_order_lines(data_dir="data", seed=42):
    data_path = Path(data_dir)

    orders = pd.read_csv(data_path / "orders.csv")
    products = pd.read_csv(data_path / "products.csv")

    rng = random.Random(seed)

    available_skus = products["sku"].dropna().astype(str).tolist()

    if not available_skus:
        raise ValueError("No product SKUs found.")

    records = []

    for order in orders.itertuples(index=False):
        item_count = int(order.items)

        if item_count < 0:
            raise ValueError(
                f"Invalid item count for {order.order_id}"
            )

        if item_count > len(available_skus):
            raise ValueError(
                f"Order {order.order_id} requires more distinct "
                "SKUs than are available."
            )

        selected_skus = rng.sample(
            available_skus,
            item_count
        )

        for sku in selected_skus:
            records.append({
                "order_id": order.order_id,
                "sku": sku,
                "quantity": 1
            })

    order_lines = pd.DataFrame(
        records,
        columns=["order_id", "sku", "quantity"]
    )

    output_path = data_path / "order_lines.csv"
    order_lines.to_csv(output_path, index=False)

    print("Order-line dataset generated successfully.")
    print(f"Output: {output_path}")
    print(f"Total orders: {orders['order_id'].nunique()}")
    print(f"Total order lines: {len(order_lines)}")
    print(f"Unique SKUs: {order_lines['sku'].nunique()}")

    print("\nSample records:")
    print(order_lines.head(10).to_string(index=False))

    return order_lines


if __name__ == "__main__":
    generate_order_lines()
