from pathlib import Path
import numpy as np
import pandas as pd

def generate_synthetic_data(output_dir: str | Path, seed: int = 42) -> None:
    """Create reproducible synthetic warehouse master, sales, order and batch data."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    product_rows = [
        ("SKU1001", "Whole Milk 1L", "Dairy", 420, 38, 70, 4, 7),
        ("SKU1002", "Greek Yogurt", "Dairy", 180, 22, 45, 5, 6),
        ("SKU1003", "Brown Bread", "Bakery", 260, 31, 60, 3, 5),
        ("SKU1004", "White Rice 5kg", "Grocery", 850, 18, 50, 30, 365),
        ("SKU1005", "Wheat Flour 5kg", "Grocery", 600, 16, 45, 25, 240),
        ("SKU1006", "Apples 1kg", "Produce", 150, 19, 40, 4, 12),
        ("SKU1007", "Bananas 1kg", "Produce", 125, 24, 45, 3, 7),
        ("SKU1008", "Eggs 12-pack", "Dairy", 300, 27, 55, 8, 21),
        ("SKU1009", "Coffee 200g", "Beverages", 210, 12, 35, 30, 180),
        ("SKU1010", "Orange Juice 1L", "Beverages", 190, 15, 40, 5, 20),
        ("SKU1011", "Pasta 500g", "Grocery", 500, 14, 40, 30, 300),
        ("SKU1012", "Tomato Sauce", "Grocery", 320, 13, 35, 30, 270),
    ]
    products = pd.DataFrame(product_rows, columns=["sku","product_name","category","current_stock","daily_demand","reorder_point","shelf_life_days","lead_time_days"])
    products.to_csv(out / "products.csv", index=False)

    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=90, freq="D")
    sales_rows = []
    for _, p in products.iterrows():
        base = float(p.daily_demand)
        for i, d in enumerate(dates):
            weekly = 1.0 + 0.16 * np.sin(2 * np.pi * i / 7)
            trend = 1.0 + 0.0015 * i
            qty = max(0, int(rng.poisson(base * weekly * trend)))
            sales_rows.append((d.date().isoformat(), p.sku, qty))
    pd.DataFrame(sales_rows, columns=["date","sku","quantity"]).to_csv(out / "sales.csv", index=False)

    baskets = [
        ["SKU1001","SKU1002","SKU1008"], ["SKU1003","SKU1009"], ["SKU1004","SKU1005"],
        ["SKU1006","SKU1007"], ["SKU1009","SKU1010"], ["SKU1011","SKU1012"],
        ["SKU1001","SKU1003"], ["SKU1004","SKU1011"], ["SKU1006","SKU1010"],
    ]
    tx_rows = []
    for i in range(1, 501):
        basket = baskets[(i - 1) % len(baskets)].copy()
        if rng.random() < 0.35:
            basket.append(str(rng.choice(products.sku)))
        for sku in sorted(set(basket)):
            tx_rows.append((f"TX{i:04d}", sku))
    pd.DataFrame(tx_rows, columns=["transaction_id","sku"]).to_csv(out / "transactions.csv", index=False)

    now = pd.Timestamp.now().floor("min")
    order_rows = []
    for i in range(1, 501):
        arrival = now + pd.Timedelta(minutes=int(i * 2))
        priority = "Express" if rng.random() < 0.25 else "Scheduled"
        order_rows.append((f"ORD{i:04d}", arrival.isoformat(), priority, int(rng.integers(1, 6)), int(rng.integers(1, 5))))
    pd.DataFrame(order_rows, columns=["order_id","arrival_time","priority","items","pick_units"]).to_csv(out / "orders.csv", index=False)

    batch_rows = []
    for _, p in products.iterrows():
        remaining = int(p.current_stock)
        for j, fraction in enumerate([0.25, 0.35, 0.40], start=1):
            qty = int(remaining * fraction)
            expiry = pd.Timestamp.today().normalize() + pd.Timedelta(days=int(rng.integers(2, max(4, int(p.shelf_life_days) + 1))))
            batch_rows.append((f"{p.sku}-B{j}", p.sku, qty, expiry.date().isoformat()))
    pd.DataFrame(batch_rows, columns=["batch_id","sku","quantity","expiry_date"]).to_csv(out / "batches.csv", index=False)

def ensure_data(output_dir: str | Path) -> None:
    out = Path(output_dir)
    required = ["products.csv","sales.csv","transactions.csv","orders.csv","batches.csv"]
    if not all((out / name).exists() for name in required):
        generate_synthetic_data(out)
