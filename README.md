# OptiFlow Twin

An end-to-end, synthetic-data digital warehouse twin built with Python, Streamlit, ARIMA, Apriori and SimPy.

## Features

- Synthetic warehouse data generation (products, 90-day sales, transactions, orders and expiry batches).
- Data processing with Pandas and NumPy.
- Seven-day SKU demand forecasts using ARIMA(1,1,1), with a moving-average fallback if model fitting fails.
- Apriori frequent-itemset mining and association rules for potential product bundles.
- Inventory health, days-of-cover and reorder suggestions.
- FEFO (First Expiry, First Out) batch allocation.
- SimPy discrete-event model for order arrivals, express/scheduled priority, picking, packing and dispatch.
- What-if controls for demand multiplier and worker capacity.
- KPI dashboard and rule-based recommendations.

> This project uses synthetic data. It is a demonstrator, not a live warehouse integration. Forecasts and simulation results are estimates, not guarantees.

## 1. Requirements

- Python 3.10–3.12 recommended
- VS Code
- Python extension for VS Code
- Internet connection for the first dependency installation

## 2. Run in VS Code (Windows)

1. Extract `OptiFlow_Twin.zip`.
2. Open VS Code → **File → Open Folder** → select the `OptiFlow_Twin` folder.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this once in that terminal:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

6. Install packages:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

7. Start the dashboard:

   ```powershell
   python -m streamlit run app.py
   ```

8. Streamlit will print a local URL, normally `http://localhost:8501`. Open it in your browser.

## 3. Run on macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## 4. Project structure

```text
OptiFlow_Twin/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── products.csv
│   ├── sales.csv
│   ├── transactions.csv
│   ├── orders.csv
│   └── batches.csv
├── src/
│   ├── __init__.py
│   ├── data.py
│   ├── forecasting.py
│   ├── bundling.py
│   ├── inventory.py
│   ├── simulation.py
│   ├── kpis.py
│   └── recommendations.py
└── tests/
    └── test_core.py
```

## 5. How the modules work

1. **Data:** `src/data.py` creates reproducible synthetic warehouse data.
2. **Forecasting:** `src/forecasting.py` fits an ARIMA time-series model per SKU.
3. **Bundling:** `src/bundling.py` converts order baskets into a one-hot matrix and mines association rules.
4. **Inventory:** `src/inventory.py` calculates days of cover, reorder status and FEFO dispatch allocations.
5. **Simulation:** `src/simulation.py` uses SimPy resources to model priority picking and packing queues.
6. **KPIs:** `src/kpis.py` calculates metrics from the generated data and simulation.
7. **Recommendations:** `src/recommendations.py` converts risk signals into decision-support messages.
8. **Dashboard:** `app.py` connects the modules and displays interactive tables, charts and scenario controls.

## 6. Dataset schemas

- `products.csv`: `sku, product_name, category, current_stock, daily_demand, reorder_point, shelf_life_days, lead_time_days`
- `sales.csv`: `date, sku, quantity`
- `transactions.csv`: `transaction_id, sku`
- `orders.csv`: `order_id, arrival_time, priority, items, pick_units`
- `batches.csv`: `batch_id, sku, quantity, expiry_date`

The app creates these files automatically if one or more are missing from `data/`.

## 7. Important modelling notes

- ARIMA is a statistical forecasting method; it is not a deep-learning model.
- Apriori identifies association patterns, not causal relationships.
- SimPy models a simplified warehouse workflow. It does not connect to real scanners, WMS software or IoT sensors.
- The service-level KPI in this prototype is an inventory-coverage proxy: the percentage of SKUs whose stock covers the forecast horizon. It is not measured customer order fill rate.
- Wastage is not presented as an observed result because the synthetic dataset does not include actual disposal records.
- The demand slider scales forecast demand and compresses simulated order arrival intervals to model a busier warehouse.

## 8. Resume description (use after you have run and validated it)

**OptiFlow Twin | Python, Streamlit, ARIMA, Apriori, SimPy, Pandas, NumPy**

- Developed a synthetic-data digital warehouse twin to analyze inventory health, forecast SKU-level demand and evaluate warehouse operating scenarios.
- Implemented ARIMA-based demand forecasting, Apriori association-rule mining, FEFO inventory allocation and SimPy discrete-event order-flow simulation.
- Built an interactive Streamlit dashboard to compare demand and workforce scenarios, monitor operational KPIs and generate rule-based replenishment and expiry recommendations.

Only claim performance improvements or accuracy percentages if you measure and validate them with a documented experiment.
