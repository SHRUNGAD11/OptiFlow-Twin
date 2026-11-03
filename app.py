from pathlib import Path
import sys
import streamlit as st
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.data import ensure_data
from src.forecasting import compare_forecasters
from src.bundling import discover_bundles
from src.inventory import inventory_status, fefo_dispatch, replenishment_plan
from src.simulation import run_simulation
from src.kpis import calculate_kpis
from src.recommendations import generate_recommendations

st.set_page_config(page_title="OptiFlow Twin", page_icon="🏭", layout="wide")
st.title("🏭 OptiFlow Twin")
st.caption("AI-assisted digital warehouse twin | Forecast • Simulate • Analyze • Optimize")

ensure_data(ROOT / "data")
products = pd.read_csv(ROOT / "data" / "products.csv")
sales = pd.read_csv(ROOT / "data" / "sales.csv", parse_dates=["date"])
transactions = pd.read_csv(ROOT / "data" / "transactions.csv")
orders = pd.read_csv(ROOT / "data" / "orders.csv", parse_dates=["arrival_time"])
batches = pd.read_csv(ROOT / "data" / "batches.csv", parse_dates=["expiry_date"])

with st.sidebar:
    st.header("Twin controls")
    st.write("Dataset: synthetic warehouse records")
    demand_multiplier = st.slider("Demand scenario", 0.5, 2.0, 1.0, 0.1, format="%.1fx")
    workers = st.slider("Available picking/packing workers", 1, 20, 6)
    order_limit = st.slider("Orders to simulate", 50, 500, 200, 50)
    st.divider()
    st.caption("Change these controls to run warehouse what-if scenarios.")

tab_overview, tab_inventory, tab_forecast, tab_bundles, tab_sim, tab_recs, tab_data = st.tabs(
    ["Overview", "Inventory & FEFO", "Demand Forecast", "Product Bundles", "Simulation", "Recommendations", "Data"]
)

forecast_metrics, forecast = compare_forecasters(sales, products, test_days=14)
inv = inventory_status(products, forecast, demand_multiplier=demand_multiplier)
sim_orders = orders.head(order_limit).copy()
simulation = run_simulation(sim_orders, demand_multiplier=demand_multiplier, workers=workers)
kpis = calculate_kpis(products, inv, simulation, batches, sales)
bundles = discover_bundles(transactions)
recommendations = generate_recommendations(inv, forecast, batches, bundles)

with tab_overview:
    st.subheader("Warehouse performance at a glance")
    cols = st.columns(4)
    cols[0].metric("Total on-hand stock", f"{int(products['current_stock'].sum()):,} units")
    cols[1].metric("Stockout-risk SKUs", int(inv["stockout_risk"].sum()))
    cols[2].metric("Average fulfillment", f"{kpis['avg_fulfillment_minutes']:.1f} min")
    cols[3].metric("Service level", f"{kpis['service_level_pct']:.1f}%")
    cols = st.columns(4)
    cols[0].metric("Inventory SKUs", len(products))
    cols[1].metric("Orders simulated", simulation["orders_processed"])
    cols[2].metric("Average queue wait", f"{simulation['avg_wait_minutes']:.1f} min")
    cols[3].metric("Forecast horizon", "7 days")
    st.markdown("### Inventory by category")
    category_stock = products.groupby("category", as_index=False)["current_stock"].sum()
    st.plotly_chart(px.bar(category_stock, x="category", y="current_stock", title="Current stock by category"), use_container_width=True)
    st.markdown("### Digital twin operating model")
    st.info("Synthetic warehouse data → data processing → ARIMA forecast / Apriori associations / inventory logic → virtual warehouse → SimPy simulation → KPIs → recommendations.")
    st.caption("All displayed results are calculated from the included synthetic dataset and the scenario controls.")

with tab_inventory:
    st.subheader("Inventory health and FEFO")
    show_cols = ["sku", "product_name", "category", "current_stock", "forecast_7d", "days_of_cover", "safety_stock", "dynamic_reorder_point", "eoq", "stockout_risk"]
    st.dataframe(inv[show_cols].sort_values("days_of_cover"), use_container_width=True, hide_index=True)
    st.markdown("### Dynamic replenishment suggestions (ROP + EOQ)")
    st.caption("ROP = forecast daily demand × supplier lead time + safety stock. Prototype assumptions: ₹50 ordering cost and ₹2/unit/year holding cost; replace with business-specific costs.")
    st.dataframe(replenishment_plan(inv), use_container_width=True, hide_index=True)
    st.markdown("### FEFO dispatch simulator (expired batches excluded)")
    sku = st.selectbox("Choose a perishable SKU", products.loc[products["category"].isin(["Dairy", "Bakery", "Produce"]), "sku"].tolist())
    qty = st.number_input("Requested dispatch quantity", min_value=1, max_value=1000, value=25)
    if st.button("Simulate FEFO allocation"):
        allocation = fefo_dispatch(batches, sku, int(qty))
        st.dataframe(allocation, use_container_width=True, hide_index=True)
        if allocation["unfulfilled_quantity"].iloc[0] > 0:
            st.warning(f"Short by {int(allocation['unfulfilled_quantity'].iloc[0])} units.")
        else:
            st.success("Dispatch allocated from earliest-expiring batches first.")

with tab_forecast:
    st.subheader("Seven-day demand forecast")
    chosen = st.selectbox("Select product", products["sku"].tolist(), format_func=lambda x: f"{x} — {products.loc[products.sku == x, 'product_name'].iloc[0]}")
    row = forecast[forecast["sku"] == chosen]
    st.dataframe(row[["date", "forecast_demand"]], use_container_width=True, hide_index=True)
    hist = sales[sales["sku"] == chosen].groupby("date", as_index=False)["quantity"].sum()
    chart_hist = hist.rename(columns={"quantity": "demand"}).tail(45)
    chart_fc = row.rename(columns={"forecast_demand": "demand"})[["date", "demand"]]
    chart_hist["type"] = "Historical"
    chart_fc["type"] = "Forecast"
    st.plotly_chart(px.line(pd.concat([chart_hist, chart_fc]), x="date", y="demand", color="type", markers=True, title="Historical demand and forecast"), use_container_width=True)
    st.markdown("### Chronological holdout model comparison")
    sku_metrics = forecast_metrics[forecast_metrics["sku"] == chosen] if not forecast_metrics.empty else forecast_metrics
    if not sku_metrics.empty:
        st.dataframe(sku_metrics[["model", "MAE", "RMSE", "MAPE", "sMAPE"]].sort_values("MAE"), use_container_width=True, hide_index=True)
        best = sku_metrics.dropna(subset=["MAE"]).sort_values("MAE").head(1)
        if not best.empty:
            st.success(f"Lowest holdout MAE for {chosen}: {best.iloc[0]['model']} ({best.iloc[0]['MAE']:.2f})")
    st.caption("Chronological 14-day holdout; MAPE excludes zero-actual days. Lowest-MAE model is refit on full history for the seven-day forecast.")

with tab_bundles:
    st.subheader("Frequently purchased-together products")
    if bundles.empty:
        st.warning("No association rules met the current support/confidence thresholds.")
    else:
        st.dataframe(bundles.head(30), use_container_width=True, hide_index=True)
    st.caption("Apriori identifies frequent itemsets; confidence and lift help rank candidate cross-sell bundles. Association does not prove causation.")

with tab_sim:
    st.subheader("Discrete-event warehouse simulation")
    c1, c2, c3 = st.columns(3)
    c1.metric("Orders processed", simulation["orders_processed"])
    c2.metric("Mean fulfillment", f"{simulation['avg_fulfillment_minutes']:.1f} min")
    c3.metric("Mean queue wait", f"{simulation['avg_wait_minutes']:.1f} min")
    st.write(f"Scenario: **{demand_multiplier:.1f}× demand**, **{workers} workers**.")
    st.plotly_chart(px.histogram(simulation["order_results"], x="fulfillment_minutes", color="priority", nbins=25, title="Order fulfillment-time distribution"), use_container_width=True)
    st.dataframe(simulation["order_results"].head(30), use_container_width=True, hide_index=True)
    st.caption("The simulation models order arrival, priority queueing, picking, packing and dispatch. It is a simplified operational model, not a live connection to a physical warehouse.")

with tab_recs:
    st.subheader("Decision-support recommendations")
    if recommendations.empty:
        st.success("No rule-based alerts were triggered for the selected scenario.")
    else:
        for _, r in recommendations.iterrows():
            if r["severity"] == "High":
                st.error(f"**{r['title']}** — {r['action']}")
            elif r["severity"] == "Medium":
                st.warning(f"**{r['title']}** — {r['action']}")
            else:
                st.info(f"**{r['title']}** — {r['action']}")
    st.caption("Recommendations are rule-based decision support. A warehouse manager should validate actions before execution.")

with tab_data:
    st.subheader("Dataset preview")
    st.write("Products")
    st.dataframe(products.head(20), use_container_width=True, hide_index=True)
    st.write("Daily sales")
    st.dataframe(sales.head(20), use_container_width=True, hide_index=True)
    st.write("Orders")
    st.dataframe(orders.head(20), use_container_width=True, hide_index=True)
    st.write("Expiry batches")
    st.dataframe(batches.head(20), use_container_width=True, hide_index=True)
    st.download_button("Download products.csv", products.to_csv(index=False), "products.csv", "text/csv")
    st.download_button("Download sales.csv", sales.to_csv(index=False), "sales.csv", "text/csv")
