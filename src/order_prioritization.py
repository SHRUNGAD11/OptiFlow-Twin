
import pandas as pd


def calculate_order_priorities(orders, current_time=None):
    """
    Calculate dynamic priority scores for warehouse orders.

    Higher scores indicate that an order should be processed earlier.
    """

    required_columns = {
        "order_id",
        "arrival_time",
        "priority",
        "pick_units",
    }

    missing = required_columns - set(orders.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    result = orders.copy()

    result["arrival_time"] = pd.to_datetime(
        result["arrival_time"],
        errors="raise"
    )

    if current_time is None:
        current_time = result["arrival_time"].max()
    else:
        current_time = pd.Timestamp(current_time)

    result["waiting_minutes"] = (
        (current_time - result["arrival_time"])
        .dt.total_seconds() / 60
    ).clip(lower=0)

    # Base priority
    priority_map = {
        "Express": 100,
        "Scheduled": 50,
    }

    result["base_priority"] = (
        result["priority"]
        .astype(str)
        .str.strip()
        .str.title()
        .map(priority_map)
        .fillna(25)
    )

    # Waiting-time bonus
    result["waiting_bonus"] = (
        result["waiting_minutes"] * 0.5
    ).clip(upper=60)

    # Small workload penalty
    result["workload_penalty"] = (
        pd.to_numeric(result["pick_units"], errors="coerce")
        .fillna(0)
        .clip(lower=0) * 0.25
    ).clip(upper=5)

    result["priority_score"] = (
        result["base_priority"]
        + result["waiting_bonus"]
        - result["workload_penalty"]
    )

    result["priority_rank"] = (
        result["priority_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    return result.sort_values(
        ["priority_score", "arrival_time", "order_id"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
