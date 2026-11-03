import pandas as pd

def generate_recommendations(inventory, forecast, batches, bundles) -> pd.DataFrame:
    items = []
    for row in inventory.itertuples(index=False):
        if row.stockout_risk:
            items.append(("High","Potential stockout",f"{row.product_name}: forecast demand exceeds available stock.",
                          "Review replenishment quantity and supplier lead time."))
        elif row.reorder_suggested:
            items.append(("Medium","Reorder point reached",f"{row.product_name}: stock is below its reorder point.",
                          "Create or review a replenishment order."))
        if row.days_of_cover < max(float(row.lead_time_days), 1):
            items.append(("High","Lead-time coverage risk",f"{row.product_name}: days of cover is below supplier lead time.",
                          "Expedite replenishment or allocate available stock carefully."))
    near_expiry = batches.copy()
    near_expiry["expiry_date"] = pd.to_datetime(near_expiry["expiry_date"])
    days = (near_expiry["expiry_date"] - pd.Timestamp.today().normalize()).dt.days
    for batch, remaining in zip(near_expiry.itertuples(index=False), days):
        if 0 <= remaining <= 5 and int(batch.quantity) > 0:
            items.append(("Medium","Near-expiry inventory",f"{batch.sku}: batch {batch.batch_id} expires in {remaining} days.",
                          "Prioritize this batch through FEFO and review promotion or transfer options."))
    if not bundles.empty:
        top = bundles.iloc[0]
        items.append(("Low","Cross-sell opportunity",f"{top['antecedents']} is associated with {top['consequents']}.",
                      "Consider testing a bundle or product-placement experiment."))
    return pd.DataFrame(items, columns=["severity","title","evidence","action"])
