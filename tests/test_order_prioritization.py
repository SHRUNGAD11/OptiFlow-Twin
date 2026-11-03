
import pandas as pd

from src.order_prioritization import calculate_order_priorities


def sample_orders():
    return pd.DataFrame([
        {
            "order_id": "ORD001",
            "arrival_time": "2026-11-03T10:00:00",
            "priority": "Express",
            "items": 2,
            "pick_units": 2,
        },
        {
            "order_id": "ORD002",
            "arrival_time": "2026-11-03T10:10:00",
            "priority": "Scheduled",
            "items": 1,
            "pick_units": 1,
        },
        {
            "order_id": "ORD003",
            "arrival_time": "2026-11-03T10:20:00",
            "priority": "Scheduled",
            "items": 3,
            "pick_units": 4,
        },
    ])


def test_priority_columns_are_created():
    result = calculate_order_priorities(
        sample_orders(),
        current_time="2026-11-03T10:30:00",
    )

    assert "priority_score" in result.columns
    assert "priority_rank" in result.columns
    assert "waiting_minutes" in result.columns


def test_express_order_gets_higher_base_priority():
    result = calculate_order_priorities(
        sample_orders(),
        current_time="2026-11-03T10:30:00",
    )

    express = result[result["priority"] == "Express"].iloc[0]
    scheduled = result[result["priority"] == "Scheduled"].iloc[0]

    assert express["priority_score"] > scheduled["priority_score"]


def test_waiting_bonus_is_capped():
    result = calculate_order_priorities(
        sample_orders(),
        current_time="2026-11-04T10:00:00",
    )

    assert (result["waiting_bonus"] <= 60).all()
    assert (result["waiting_bonus"] == 60).any()


def test_priority_ranks_are_unique():
    result = calculate_order_priorities(
        sample_orders(),
        current_time="2026-11-03T10:30:00",
    )

    assert result["priority_rank"].is_unique


def test_waiting_time_is_non_negative():
    result = calculate_order_priorities(
        sample_orders(),
        current_time="2026-11-03T10:05:00",
    )

    assert (result["waiting_minutes"] >= 0).all()
