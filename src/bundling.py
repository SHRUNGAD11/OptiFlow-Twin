import pandas as pd

def discover_bundles(transactions: pd.DataFrame, min_support: float = 0.04, min_confidence: float = 0.25) -> pd.DataFrame:
    """Discover co-purchased SKU rules using mlxtend Apriori."""
    if transactions.empty:
        return pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])
    try:
        from mlxtend.preprocessing import TransactionEncoder
        from mlxtend.frequent_patterns import apriori, association_rules
        baskets = transactions.groupby("transaction_id")["sku"].apply(list).tolist()
        encoder = TransactionEncoder()
        encoded = encoder.fit(baskets).transform(baskets)
        basket_df = pd.DataFrame(encoded, columns=encoder.columns_)
        itemsets = apriori(basket_df, min_support=min_support, use_colnames=True)
        if itemsets.empty:
            return pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])
        rules = association_rules(itemsets, metric="confidence", min_threshold=min_confidence)
        if rules.empty:
            return pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])
        rules["antecedents"] = rules["antecedents"].apply(lambda x: ", ".join(sorted(x)))
        rules["consequents"] = rules["consequents"].apply(lambda x: ", ".join(sorted(x)))
        return rules[["antecedents","consequents","support","confidence","lift"]].sort_values(["lift","confidence"], ascending=False)
    except Exception:
        return pd.DataFrame(columns=["antecedents","consequents","support","confidence","lift"])
