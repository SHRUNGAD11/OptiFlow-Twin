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

- Python 3.10â€“3.12 recommended
- VS Code
- Python extension for VS Code
- Internet connection for the first dependency installation

## 2. Run in VS Code (Windows)

1. Extract `OptiFlow_Twin.zip`.
2. Open VS Code â†’ **File â†’ Open Folder** â†’ select the `OptiFlow_Twin` folder.
3. Open **Terminal â†’ New Terminal**.
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
â”œâ”€â”€ app.py
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ README.md
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ products.csv
â”‚   â”œâ”€â”€ sales.csv
â”‚   â”œâ”€â”€ transactions.csv
â”‚   â”œâ”€â”€ orders.csv
â”‚   â””â”€â”€ batches.csv
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ data.py
â”‚   â”œâ”€â”€ forecasting.py
â”‚   â”œâ”€â”€ bundling.py
â”‚   â”œâ”€â”€ inventory.py
â”‚   â”œâ”€â”€ simulation.py
â”‚   â”œâ”€â”€ kpis.py
â”‚   â””â”€â”€ recommendations.py
â””â”€â”€ tests/
    â””â”€â”€ test_core.py
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


## Phase 1 upgrade: forecasting evaluation and inventory optimization

- Compare ARIMA(1,1,1), weekly SARIMA and Random Forest with lag/rolling features.
- Use a chronological 14-day holdout; report MAE, RMSE, MAPE (excluding zero actuals) and sMAPE.
- Refit the lowest-holdout-MAE model on all history for the seven-day SKU forecast.
- Calculate safety stock, dynamic reorder point (ROP) and EOQ.
- FEFO now excludes expired batches and reports any unfulfilled dispatch quantity.

Prototype assumptions for EOQ are INR 50/order ordering cost and INR 2/unit/year holding cost. Replace these with validated business costs before real procurement use. Synthetic data is demonstrative; do not claim model accuracy or operational savings without measured experiments.

Run tests:
```powershell
pytest -v
```

---

## Phase 2: Interactive Warehouse Digital Twin

- Implemented a stateful warehouse engine to track inventory, orders, workers and operational events.
- Integrated SimPy-based discrete-event simulation with FEFO inventory dispatch.
- Implemented worker assignment, order processing, packing and dispatch workflows.
- Developed a Scenario Lab to evaluate normal demand, peak demand and workforce shortage conditions.
- Added warehouse event history and operational performance metrics.

## Phase 3: AI-Powered Warehouse Optimization

### 3.1 Warehouse Layout Optimization

- Developed demand-based warehouse slotting using historical sales velocity and order frequency.
- Implemented ABC classification to categorize products based on cumulative picking frequency.
- Optimized product placement using Manhattan distance from the dispatch point.
- Compared alphabetical baseline, demand-based and ABC-based slotting strategies.

Measured results on the current synthetic dataset:

| Strategy | Average weighted picking distance |
|---|---:|
| Alphabetical baseline | 2.5242 |
| Demand-based | 2.4529 |
| ABC-based | 2.4529 |

The demand-based strategy reduced weighted picking distance by approximately 2.83% against the alphabetical benchmark.

### 3.2 Intelligent Order Prioritization

- Developed a dynamic order-priority scoring engine.
- Assigns higher base priority to Express orders.
- Incorporates waiting-time aging to reduce starvation of Scheduled orders.
- Includes a workload penalty based on order picking units.
- Dynamically recalculates pending-order scores when dispatch decisions are made.
- Records priority scores in simulation results.

Priority score components:
- Base priority: Express = 100, Scheduled = 50.
- Waiting-time bonus: 0.5 points per waiting minute, capped at 60.
- Workload penalty: 0.25 points per picking unit, capped at 5.

### 3.3 Streamlit Dashboard Integration

Added dedicated dashboard functionality for:
- Intelligent order-priority score distribution.
- Express versus Scheduled order comparison.
- Top-priority order ranking.
- Waiting-time analysis.
- Fulfillment-time analysis.
- Complete order-priority results.

### 3.4 Scheduler Benchmarking

Compared static Express-first scheduling with dynamic priority scheduling using identical synthetic warehouse data.

High-demand scenario:
- 500 orders.
- 2x demand multiplier.
- 3 available workers.

| Metric | Static | Dynamic |
|---|---:|---:|
| Express average wait | 2.94 min | 18.12 min |
| Scheduled average wait | 482.38 min | 448.36 min |
| Express dispatch rate | 100% | 100% |
| Scheduled dispatch rate | 98.95% | 98.95% |

Dynamic scheduling reduced Scheduled-order average waiting time by approximately 7.05%, while increasing Express-order waiting time.

This demonstrates a trade-off between order urgency and scheduling fairness rather than a universal improvement in fulfillment performance.

### Testing and Validation

- Added automated tests for warehouse state management, FEFO dispatch and inventory validation.
- Added tests for dynamic priority scoring and waiting-time aging.
- Added integration tests for priority scores in simulation results.
- Validated worker release after high-demand simulations.
- Compared static and dynamic scheduling using a reproducible benchmark script.

Current test suite: 29 tests passed.

Run tests:

```powershell
pytest -v
```

Run scheduler benchmark:

```powershell
python -m src.benchmark_schedulers
```

Run dashboard:

```powershell
python -m streamlit run app.py
```

**Modelling limitations:** Results are based on synthetic warehouse data and simplified simulation assumptions. The layout optimizer uses a heuristic placement method, and the scheduler benchmark does not establish real-world operational savings.
