import pandas as pd


def generate_recommendations(
    inventory,
    forecast,
    batches,
    bundles
) -> pd.DataFrame:
    """
    Generate prioritized, SKU-specific warehouse recommendations.

    Recommendation types:
    1. Potential stockout
    2. Lead-time coverage risk
    3. Reorder point reached
    4. Near-expiry inventory
    5. Cross-sell opportunity

    Returns a DataFrame compatible with the existing dashboard.
    """

    items = []
    seen = set()

    def add_recommendation(
        severity,
        title,
        evidence,
        action,
        sku=None
    ):
        # Prevent duplicate alerts for the same SKU and issue
        key = (sku, title)

        if key in seen:
            return

        seen.add(key)

        items.append({
            "severity": severity,
            "title": title,
            "evidence": evidence,
            "action": action
        })

    # --------------------------------------------------
    # 1. INVENTORY AND STOCKOUT RECOMMENDATIONS
    # --------------------------------------------------

    for _, row in inventory.iterrows():

        sku = str(row.get("sku", "Unknown"))
        product = str(row.get("product_name", sku))

        stock = float(row.get("current_stock", 0) or 0)
        forecast_7d = float(row.get("forecast_7d", 0) or 0)

        lead_time = float(row.get("lead_time_days", 1) or 1)
        days_cover = row.get("days_of_cover", 0)

        reorder_point = float(
            row.get(
                "dynamic_reorder_point",
                row.get("reorder_point", 0)
            ) or 0
        )

        suggested_qty = int(
            row.get("suggested_order_quantity", 0) or 0
        )

        # Check stockout risk
        stockout = bool(
            row.get("stockout_risk", stock < forecast_7d)
        )

        reorder = bool(
            row.get(
                "reorder_suggested",
                row.get(
                    "reorder_required",
                    stock <= reorder_point
                )
            )
        )

        # Highest priority: stockout risk
        if stockout:
            add_recommendation(
                "High",
                "Potential stockout",
                (
                    f"{product} ({sku}): current stock is "
                    f"{stock:.0f} units, while seven-day forecast "
                    f"demand is {forecast_7d:.1f} units."
                ),
                (
                    f"Prioritize replenishment. Suggested order: "
                    f"{suggested_qty} units. Review supplier lead time."
                ),
                sku
            )

        # Lead-time coverage risk
        try:
            coverage_risk = (
                pd.notna(days_cover)
                and float(days_cover) < max(lead_time, 1)
            )
        except (TypeError, ValueError):
            coverage_risk = False

        if coverage_risk:
            add_recommendation(
                "High",
                "Lead-time coverage risk",
                (
                    f"{product} ({sku}): inventory covers "
                    f"{float(days_cover):.1f} days, but supplier "
                    f"lead time is {lead_time:.0f} days."
                ),
                (
                    "Expedite replenishment or allocate available "
                    "stock carefully."
                ),
                sku
            )

        # Reorder recommendation
        if reorder:
            add_recommendation(
                "Medium",
                "Reorder point reached",
                (
                    f"{product} ({sku}): current stock is "
                    f"{stock:.0f} units against a dynamic reorder "
                    f"point of {reorder_point:.0f} units."
                ),
                (
                    f"Create or review a replenishment order "
                    f"for approximately {suggested_qty} units."
                ),
                sku
            )

    # --------------------------------------------------
    # 2. NEAR-EXPIRY BATCH RECOMMENDATIONS
    # --------------------------------------------------

    if not batches.empty:

        near_expiry = batches.copy()

        near_expiry["expiry_date"] = pd.to_datetime(
            near_expiry["expiry_date"],
            errors="coerce"
        )

        near_expiry["quantity"] = pd.to_numeric(
            near_expiry["quantity"],
            errors="coerce"
        ).fillna(0)

        today = pd.Timestamp.today().normalize()

        near_expiry["days_remaining"] = (
            near_expiry["expiry_date"] - today
        ).dt.days

        expiring_batches = near_expiry[
            near_expiry["expiry_date"].notna()
            & (near_expiry["days_remaining"] >= 0)
            & (near_expiry["days_remaining"] <= 5)
            & (near_expiry["quantity"] > 0)
        ]

        for _, batch in expiring_batches.iterrows():

            sku = str(batch["sku"])
            batch_id = str(batch["batch_id"])
            remaining = int(batch["days_remaining"])
            quantity = float(batch["quantity"])

            add_recommendation(
                "Medium",
                "Near-expiry inventory",
                (
                    f"SKU {sku}, batch {batch_id}: "
                    f"{quantity:.0f} units expire in "
                    f"{remaining} days."
                ),
                (
                    "Prioritize this batch through FEFO. "
                    "Review promotion or stock-transfer options."
                ),
                f"{sku}-{batch_id}"
            )

    # --------------------------------------------------
    # 3. PRODUCT BUNDLE RECOMMENDATIONS
    # --------------------------------------------------

    if bundles is not None and not bundles.empty:

        top_bundles = bundles.head(5)

        for _, bundle in top_bundles.iterrows():

            antecedents = str(bundle["antecedents"])
            consequents = str(bundle["consequents"])

            confidence = float(bundle.get("confidence", 0))
            lift = float(bundle.get("lift", 0))

            add_recommendation(
                "Low",
                "Cross-sell opportunity",
                (
                    f"Customers purchasing {antecedents} "
                    f"are associated with {consequents}. "
                    f"Confidence: {confidence:.2%}; "
                    f"Lift: {lift:.2f}."
                ),
                (
                    "Consider testing a product bundle or "
                    "product-placement experiment."
                ),
                f"bundle-{antecedents}-{consequents}"
            )

    # --------------------------------------------------
    # 4. PRIORITIZE RECOMMENDATIONS
    # --------------------------------------------------

    result = pd.DataFrame(
        items,
        columns=[
            "severity",
            "title",
            "evidence",
            "action"
        ]
    )

    if result.empty:
        return result

    priority = {
        "High": 1,
        "Medium": 2,
        "Low": 3
    }

    result["_priority"] = result["severity"].map(priority)

    result = (
        result.sort_values("_priority")
        .drop(columns=["_priority"])
        .reset_index(drop=True)
    )

    return result
