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
from src.warehouse_state import WarehouseState
from src.digital_twin_simulation import run_warehouse_simulation
from src.scenario_analysis import run_scenario_comparison
from src.order_prioritization import calculate_order_priorities

from src.layout_optimizer import (
    optimize_warehouse_layout,
    optimize_abc_layout,
    compare_slotting_strategies,
)

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

(
    tab_overview,
    tab_inventory,
    tab_forecast,
    tab_bundles,
    tab_sim,
    tab_recs,
    tab_data,
    tab_digital_twin,
    tab_scenario_lab,
    tab_layout,
    tab_priority
) = st.tabs([
    "Overview",
    "Inventory & FEFO",
    "Demand Forecast",
    "Product Bundles",
    "Simulation",
    "Recommendations",
    "Data",
    "Warehouse Digital Twin",
    "Scenario Lab",
    "Warehouse Layout",
    "Intelligent Order Prioritization"
])

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


# ==========================================================
# PHASE 2: INTERACTIVE WAREHOUSE DIGITAL TWIN
# ==========================================================

with tab_digital_twin:

    st.subheader("Interactive Warehouse Digital Twin")

    st.write(
        "Run an event-driven simulation of warehouse operations "
        "using inventory, orders, FEFO and worker allocation."
    )

    st.info(
        "Each simulation starts with a fresh warehouse state. "
        "The original CSV datasets are not modified."
    )

    st.markdown("### Simulation configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        twin_demand = st.slider(
            "Demand multiplier",
            0.5, 2.0, 1.0, 0.1,
            key="twin_demand"
        )

    with col2:
        twin_workers = st.slider(
            "Warehouse workers",
            1, 20, 6,
            key="twin_workers"
        )

    with col3:
        twin_order_limit = st.slider(
            "Number of orders",
            50, 500, 200, 50,
            key="twin_order_limit"
        )

    st.divider()

    if st.button(
        "Run Warehouse Digital Twin",
        type="primary",
        use_container_width=True
    ):

        with st.spinner("Simulating warehouse operations..."):

            # Create a fresh warehouse state
            twin_state = WarehouseState(
                data_dir=str(ROOT / "data"),
                worker_count=twin_workers
            )

            # Restrict simulation to selected orders
            twin_state.orders = (
                twin_state.orders.head(twin_order_limit).copy()
            )

            # Load synthetic order-to-SKU mapping
            order_lines = pd.read_csv(
                ROOT / "data" / "order_lines.csv"
            )

            selected_ids = twin_state.orders["order_id"]

            order_lines = order_lines[
                order_lines["order_id"].isin(selected_ids)
            ].copy()

            # Save initial inventory for comparison
            initial_inventory = twin_state.products.copy()

            # Run integrated simulation
            twin_result = run_warehouse_simulation(
                state=twin_state,
                order_lines=order_lines,
                demand_multiplier=twin_demand,
                workers=twin_workers
            )

            # Store results across Streamlit reruns
            st.session_state["digital_twin_run"] = {
                "result": twin_result,
                "state": twin_state,
                "initial_inventory": initial_inventory,
                "demand": twin_demand,
                "workers": twin_workers,
                "order_limit": twin_order_limit
            }

            st.success("Warehouse simulation completed!")

    # Display the latest simulation result
    saved_run = st.session_state.get("digital_twin_run")

    if saved_run is None:

        st.warning(
            "Configure the simulation and click "
            "'Run Warehouse Digital Twin' to begin."
        )

    else:

        result = saved_run["result"]
        twin_state = saved_run["state"]
        initial_inventory = saved_run["initial_inventory"]

        st.markdown("### Simulation results")

        st.caption(
            f"Last run: {saved_run['demand']:.1f}x demand | "
            f"{saved_run['workers']} workers | "
            f"{saved_run['order_limit']} orders"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Orders processed",
            result["orders_processed"]
        )

        c2.metric(
            "Orders dispatched",
            result["orders_dispatched"]
        )

        c3.metric(
            "Orders cancelled",
            result["orders_cancelled"]
        )

        c4.metric(
            "Average fulfillment",
            f"{result['avg_fulfillment_minutes']:.2f} min"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Average queue wait",
            f"{result['avg_wait_minutes']:.2f} min"
        )

        c2.metric(
            "Total warehouse events",
            len(result["event_history"])
        )

        c3.metric(
            "Available workers after run",
            int(
                (twin_state.workers["status"] == "Available").sum()
            )
        )

        st.divider()

        # --------------------------------------------------
        # ORDER PROCESSING
        # --------------------------------------------------

        st.markdown("### Order processing results")

        order_results = result["order_results"]

        if not order_results.empty:

            st.plotly_chart(
                px.histogram(
                    order_results,
                    x="fulfillment_minutes",
                    color="status",
                    title="Order fulfillment time distribution",
                    nbins=25
                ),
                use_container_width=True
            )

            st.dataframe(
                order_results,
                use_container_width=True,
                hide_index=True
            )

            st.markdown("### Worker workload")

            worker_workload = (
                order_results.groupby("worker_id")
                .size()
                .reset_index(name="orders_assigned")
            )

            st.plotly_chart(
                px.bar(
                    worker_workload,
                    x="worker_id",
                    y="orders_assigned",
                    title="Orders processed per worker"
                ),
                use_container_width=True
            )

        # --------------------------------------------------
        # INVENTORY CHANGES
        # --------------------------------------------------

        st.markdown("### Inventory changes after simulation")

        inventory_comparison = initial_inventory[
            ["sku", "product_name", "current_stock"]
        ].merge(
            twin_state.products[
                ["sku", "current_stock"]
            ],
            on="sku",
            suffixes=("_before", "_after")
        )

        inventory_comparison["units_dispatched"] = (
            inventory_comparison["current_stock_before"]
            - inventory_comparison["current_stock_after"]
        )

        st.dataframe(
            inventory_comparison.sort_values(
                "units_dispatched",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True
        )

        # --------------------------------------------------
        # WAREHOUSE EVENT HISTORY
        # --------------------------------------------------

        st.markdown("### Warehouse event history")

        events = result["event_history"]

        if not events.empty:

            st.dataframe(
                events[
                    [
                        "event_id",
                        "event_type",
                        "description",
                        "timestamp"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

        # --------------------------------------------------
        # FINAL WAREHOUSE STATE
        # --------------------------------------------------

        st.markdown("### Final warehouse state")

        final_metrics = twin_state.get_metrics()

        metric_df = pd.DataFrame(
            list(final_metrics.items()),
            columns=["Metric", "Value"]
        )

        st.dataframe(
            metric_df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "This is a discrete-event software simulation using "
            "synthetic warehouse data, not a live physical warehouse connection."
        )

with tab_scenario_lab:
    st.subheader("Warehouse Scenario Experimentation Lab")

    st.write(
        "Compare warehouse performance under different demand "
        "and workforce conditions."
    )

    st.info(
        "Each scenario starts with a fresh warehouse state, "
        "so results can be compared fairly."
    )

    scenario_order_limit = st.slider(
        "Number of orders to simulate",
        min_value=50,
        max_value=500,
        value=200,
        step=50,
        key="scenario_order_limit"
    )

    if st.button(
        "Run All Warehouse Scenarios",
        type="primary",
        use_container_width=True
    ):
        with st.spinner("Running warehouse scenarios..."):
            scenario_results = run_scenario_comparison(
                data_dir=str(ROOT / "data"),
                order_limit=scenario_order_limit
            )

            st.session_state["scenario_results"] = scenario_results

        st.success("Scenario comparison completed!")

    if "scenario_results" in st.session_state:
        results = st.session_state["scenario_results"]

        st.subheader("Scenario Comparison Results")
        st.dataframe(results, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Average Fulfillment Time")
            fig = px.bar(
                results,
                x="scenario",
                y="avg_fulfillment_minutes",
                color="scenario",
                title="Fulfillment Time by Scenario"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Average Queue Waiting Time")
            fig = px.bar(
                results,
                x="scenario",
                y="avg_wait_minutes",
                color="scenario",
                title="Queue Waiting Time by Scenario"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Order Dispatch Rate")
        fig = px.bar(
            results,
            x="scenario",
            y="dispatch_rate_pct",
            color="scenario",
            title="Dispatch Rate by Scenario"
        )
        st.plotly_chart(fig, use_container_width=True)

        best = results.sort_values(
            ["avg_fulfillment_minutes", "avg_wait_minutes"]
        ).iloc[0]

        st.success(
            f"Lowest average fulfillment time: {best['scenario']} "
            f"({best['avg_fulfillment_minutes']:.2f} minutes)"
        )

    else:
        st.warning("Run the scenarios to view the comparison.")


with tab_layout:
    st.subheader("AI-Powered Warehouse Layout Optimization")

    st.write(
        "Visualize SKU placement based on demand velocity "
        "and order-picking frequency."
    )

    strategy = st.selectbox(
        "Select slotting strategy",
        ["Demand-Based", "ABC-Based"],
        key="layout_strategy"
    )

    if strategy == "Demand-Based":
        result = optimize_warehouse_layout(
            data_dir=str(ROOT / "data"),
            rows=3,
            columns=4
        )
        layout = result["layout"].copy()
    else:
        result = optimize_abc_layout(
            data_dir=str(ROOT / "data"),
            rows=3,
            columns=4
        )
        layout = result["layout"].copy()

    comparison = compare_slotting_strategies(
        data_dir=str(ROOT / "data"),
        rows=3,
        columns=4
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Total SKUs", result["total_skus"])
    col2.metric(
        "Average Picking Distance",
        f"{result['average_picking_distance']:.3f}"
    )

    baseline_distance = comparison.loc[
        comparison["strategy"] == "Alphabetical Baseline",
        "average_distance"
    ].iloc[0]

    improvement = (
        (baseline_distance - result["average_picking_distance"])
        / baseline_distance * 100
        if baseline_distance > 0 else 0
    )

    col3.metric(
        "Improvement vs Baseline",
        f"{improvement:.2f}%"
    )

    st.divider()

    st.subheader("Warehouse Storage Grid")

    for row_number in range(3):
        columns_ui = st.columns(4)

        for column_number in range(4):
            slot_name = (
                f"R{row_number + 1}-C{column_number + 1}"
            )

            slot_data = layout[
                layout["slot"] == slot_name
            ]

            with columns_ui[column_number]:
                if not slot_data.empty:
                    product = slot_data.iloc[0]

                    abc_label = (
                        product["abc_class"]
                        if "abc_class" in product.index
                        else "N/A"
                    )

                    st.markdown(
                        f"""
                        **{slot_name}**

                        {product['product_name']}

                        SKU: {product['sku']}

                        ABC: {abc_label}

                        Picks: {int(product['order_frequency'])}

                        Distance: {int(product['distance'])}
                        """
                    )
                    st.success("Occupied")
                else:
                    st.info(f"{slot_name}\n\nEmpty")

    st.divider()

    st.subheader("SKU Placement Details")

    display_columns = [
        "sku",
        "product_name",
        "category",
        "demand_score",
        "order_frequency",
        "slot",
        "distance",
    ]

    if "abc_class" in layout.columns:
        display_columns.append("abc_class")

    st.dataframe(
        layout[display_columns],
        use_container_width=True
    )

    st.divider()

    st.subheader("Slotting Strategy Comparison")

    comparison_chart = px.bar(
        comparison,
        x="strategy",
        y="average_distance",
        color="strategy",
        title="Weighted Average Picking Distance",
        labels={
            "strategy": "Slotting Strategy",
            "average_distance": "Average Picking Distance",
        }
    )

    st.plotly_chart(
        comparison_chart,
        use_container_width=True
    )


# ==========================================================
# PHASE 3.3: INTELLIGENT ORDER PRIORITIZATION
# ==========================================================

with tab_priority:

    st.subheader("Intelligent Order Prioritization")

    st.caption(
        "Dynamic order scheduling using business priority, "
        "waiting time and workload."
    )

    if st.button("Run Priority-Based Simulation"):

        priority_state = WarehouseState(data_dir="data")

        priority_result = run_warehouse_simulation(
            state=priority_state,
            order_lines=pd.read_csv(
                ROOT / "data" / "order_lines.csv"
            ),
            demand_multiplier=demand_multiplier,
            workers=workers,
            as_of=pd.Timestamp.now().normalize()
        )

        priority_orders = priority_result["order_results"]

        if not priority_orders.empty:

            st.session_state["priority_orders"] = priority_orders
            st.session_state["priority_result"] = priority_result

    if "priority_orders" in st.session_state:

        priority_orders = st.session_state["priority_orders"]
        priority_result = st.session_state["priority_result"]

        st.divider()

        st.subheader("Priority Scheduling KPIs")

        col1, col2, col3, col4 = st.columns(4)

        total_orders = len(priority_orders)

        dispatch_rate = (
            priority_result["orders_dispatched"]
            / total_orders * 100
            if total_orders else 0
        )

        col1.metric("Orders Processed", total_orders)

        col2.metric(
            "Orders Dispatched",
            priority_result["orders_dispatched"]
        )

        col3.metric(
            "Dispatch Rate",
            f"{dispatch_rate:.1f}%"
        )

        col4.metric(
            "Average Waiting Time",
            f"{priority_result['avg_wait_minutes']:.2f} min"
        )

        st.divider()

        st.subheader("Priority Score Distribution")

        priority_chart = px.histogram(
            priority_orders,
            x="priority_score",
            color="priority",
            nbins=20,
            title="Distribution of Dynamic Priority Scores",
            labels={
                "priority_score": "Priority Score",
                "count": "Number of Orders"
            }
        )

        st.plotly_chart(
            priority_chart,
            use_container_width=True
        )

        st.divider()

        st.subheader("Express vs Scheduled Orders")

        priority_comparison = (
            priority_orders.groupby("priority")
            .agg(
                total_orders=("order_id", "count"),
                average_score=("priority_score", "mean"),
                average_wait=("wait_minutes", "mean"),
                dispatched=(
                    "status",
                    lambda x: (x == "Dispatched").sum()
                )
            )
            .reset_index()
        )

        col1, col2 = st.columns(2)

        with col1:

            comparison_chart = px.bar(
                priority_comparison,
                x="priority",
                y="average_score",
                color="priority",
                title="Average Priority Score",
                labels={
                    "priority": "Order Type",
                    "average_score": "Average Score"
                }
            )

            st.plotly_chart(
                comparison_chart,
                use_container_width=True
            )

        with col2:

            waiting_chart = px.bar(
                priority_comparison,
                x="priority",
                y="average_wait",
                color="priority",
                title="Average Waiting Time",
                labels={
                    "priority": "Order Type",
                    "average_wait": "Waiting Time (minutes)"
                }
            )

            st.plotly_chart(
                waiting_chart,
                use_container_width=True
            )

        st.dataframe(
            priority_comparison,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Top Priority Orders")

        top_orders = priority_orders.sort_values(
            "priority_score",
            ascending=False
        ).head(20)

        st.dataframe(
            top_orders[
                [
                    "order_id",
                    "priority",
                    "priority_score",
                    "worker_id",
                    "wait_minutes",
                    "fulfillment_minutes",
                    "status"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Waiting Time vs Priority Score")

        waiting_scatter = px.scatter(
            priority_orders,
            x="wait_minutes",
            y="priority_score",
            color="priority",
            hover_data=["order_id", "worker_id", "status"],
            title="Order Waiting Time and Priority Relationship"
        )

        st.plotly_chart(
            waiting_scatter,
            use_container_width=True
        )

        st.subheader("Workload Analysis")

        workload_chart = px.box(
            priority_orders,
            x="priority",
            y="fulfillment_minutes",
            color="priority",
            title="Fulfillment Time by Order Type"
        )

        st.plotly_chart(
            workload_chart,
            use_container_width=True
        )

        st.divider()

        st.subheader("Complete Order Priority Ranking")

        ranked_orders = priority_orders.sort_values(
            "priority_score",
            ascending=False
        ).reset_index(drop=True)

        ranked_orders.insert(
            0,
            "display_rank",
            range(1, len(ranked_orders) + 1)
        )

        st.dataframe(
            ranked_orders,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Click 'Run Priority-Based Simulation' "
            "to generate dynamic order priority results."
        )
