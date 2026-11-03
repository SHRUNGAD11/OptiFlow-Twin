import pandas as pd

def run_simulation(orders: pd.DataFrame, demand_multiplier: float = 1.0, workers: int = 6) -> dict:
    """SimPy model of order arrival, priority queueing, picking, packing and dispatch."""
    import simpy
    if orders.empty:
        empty = pd.DataFrame(columns=["order_id","priority","wait_minutes","fulfillment_minutes","dispatch_time"])
        return {"orders_processed":0,"avg_wait_minutes":0.0,"avg_fulfillment_minutes":0.0,"order_results":empty}
    data = orders.copy().head(500)
    data["arrival_time"] = pd.to_datetime(data["arrival_time"])
    base = data["arrival_time"].min()
    data["arrival_minute"] = (data["arrival_time"] - base).dt.total_seconds() / 60.0
    # Demand multiplier compresses arrivals: higher demand means more arrivals per simulated minute.
    data["arrival_minute"] = data["arrival_minute"] / max(float(demand_multiplier), 0.1)
    env = simpy.Environment()
    pickers = simpy.PriorityResource(env, capacity=max(1, int(workers)))
    packers = simpy.Resource(env, capacity=max(1, int(workers // 2) or 1))
    results = []

    def process_order(row):
        yield env.timeout(float(row.arrival_minute))
        arrived = env.now
        priority = 0 if str(row.priority).lower() == "express" else 1
        queue_start = env.now
        with pickers.request(priority=priority) as req:
            yield req
            wait = env.now - queue_start
            pick_duration = 2.0 + float(row.pick_units) * 0.8
            yield env.timeout(pick_duration)
        with packers.request() as req:
            yield req
            yield env.timeout(2.0 + float(row.items) * 0.5)
        dispatched = env.now
        results.append({"order_id":row.order_id, "priority":row.priority, "wait_minutes":wait,
                        "fulfillment_minutes":dispatched-arrived, "dispatch_time":dispatched})

    for row in data.itertuples(index=False):
        env.process(process_order(row))
    env.run()
    result_df = pd.DataFrame(results).sort_values("dispatch_time")
    return {"orders_processed":len(result_df),
            "avg_wait_minutes":float(result_df["wait_minutes"].mean()) if len(result_df) else 0.0,
            "avg_fulfillment_minutes":float(result_df["fulfillment_minutes"].mean()) if len(result_df) else 0.0,
            "order_results":result_df}
