from src.scenario_analysis import run_scenario_comparison


def test_scenario_comparison_runs():
    results = run_scenario_comparison(
        data_dir="data",
        order_limit=50
    )

    assert len(results) == 5
    assert "scenario" in results.columns
    assert "avg_fulfillment_minutes" in results.columns
    assert "dispatch_rate_pct" in results.columns


def test_scenario_results_are_valid():
    results = run_scenario_comparison(
        data_dir="data",
        order_limit=50
    )

    assert (results["orders_processed"] > 0).all()
    assert (results["orders_dispatched"] >= 0).all()
    assert (results["orders_cancelled"] >= 0).all()
    assert (results["dispatch_rate_pct"] >= 0).all()
    assert (results["dispatch_rate_pct"] <= 100).all()


def test_all_scenario_workers_are_released():
    results = run_scenario_comparison(
        data_dir="data",
        order_limit=50
    )

    assert (results["available_workers"] == results["workers"]).all()
