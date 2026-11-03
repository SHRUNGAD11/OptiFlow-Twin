import warnings
import numpy as np
import pandas as pd

def forecast_all_skus(sales: pd.DataFrame, products: pd.DataFrame, periods: int = 7) -> pd.DataFrame:
    """Fit ARIMA(1,1,1) per SKU; use recent-mean fallback if estimation fails."""
    rows = []
    sales = sales.copy()
    sales["date"] = pd.to_datetime(sales["date"])
    for sku in products["sku"]:
        series = (sales[sales["sku"] == sku].groupby("date")["quantity"].sum()
                  .asfreq("D", fill_value=0).astype(float))
        if len(series) < 15:
            forecast = np.repeat(float(series.tail(7).mean() if len(series) else 0), periods)
        else:
            try:
                from statsmodels.tsa.arima.model import ARIMA
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = ARIMA(series, order=(1, 1, 1)).fit()
                    forecast = np.asarray(model.forecast(steps=periods), dtype=float)
            except Exception:
                forecast = np.repeat(float(series.tail(7).mean()), periods)
        forecast = np.maximum(0, forecast)
        future_dates = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=periods, freq="D")
        rows.extend((sku, d, float(v)) for d, v in zip(future_dates, forecast))
    return pd.DataFrame(rows, columns=["sku","date","forecast_demand"])
