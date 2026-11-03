import warnings
import numpy as np
import pandas as pd

def _series_for_sku(sales, sku):
    d=sales[sales.sku==sku].copy()
    d["date"]=pd.to_datetime(d.date)
    return d.groupby("date").quantity.sum().asfreq("D",fill_value=0).astype(float)

def _predict(model, train, steps):
    if model=="ARIMA":
        from statsmodels.tsa.arima.model import ARIMA
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.asarray(ARIMA(train,order=(1,1,1)).fit().forecast(steps))
    if model=="SARIMA":
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m=SARIMAX(train,order=(1,1,1),seasonal_order=(1,0,1,7),
                      enforce_stationarity=False,enforce_invertibility=False).fit(disp=False)
            return np.asarray(m.forecast(steps))
    if model=="Random Forest":
        from sklearn.ensemble import RandomForestRegressor
        f=pd.DataFrame({"y":train.values})
        for lag in (1,2,3,7,14): f[f"lag_{lag}"]=f.y.shift(lag)
        f["rolling_7"]=f.y.shift(1).rolling(7).mean()
        f=f.dropna(); features=[c for c in f if c!="y"]
        if len(f)<10: return np.repeat(float(train.tail(7).mean()),steps)
        m=RandomForestRegressor(n_estimators=200,random_state=42,min_samples_leaf=2,n_jobs=-1)
        m.fit(f[features],f.y); history=list(train.values.astype(float)); out=[]
        for _ in range(steps):
            x=[history[-lag] if len(history)>=lag else float(np.mean(history)) for lag in (1,2,3,7,14)]
            x.append(float(np.mean(history[-7:])))
            y=max(0.0,float(m.predict(pd.DataFrame([x],columns=features))[0]))
            out.append(y); history.append(y)
        return np.asarray(out)
    raise ValueError(f"Unknown model: {model}")

def _metrics(actual,pred):
    a=np.asarray(actual,dtype=float); p=np.maximum(0,np.asarray(pred,dtype=float)); e=a-p
    nz=a!=0
    return {"MAE":float(np.mean(np.abs(e))),"RMSE":float(np.sqrt(np.mean(e**2))),
            "MAPE":float(np.mean(np.abs(e[nz]/a[nz]))*100) if nz.any() else np.nan,
            "sMAPE":float(np.mean(2*np.abs(e)/(np.abs(a)+np.abs(p)+1e-8))*100)}

def compare_forecasters(sales,products,test_days=14):
    """Chronological holdout comparison; returns metrics and seven-day best-model forecasts."""
    scores=[]; forecasts=[]
    for sku in products.sku:
        series=_series_for_sku(sales,sku)
        if len(series)<=test_days+20: continue
        train,test=series.iloc[:-test_days],series.iloc[-test_days:]
        for model in ("ARIMA","SARIMA","Random Forest"):
            try: scores.append({"sku":sku,"model":model,**_metrics(test.values,_predict(model,train,len(test)))})
            except Exception as exc:
                scores.append({"sku":sku,"model":model,"MAE":np.nan,"RMSE":np.nan,"MAPE":np.nan,"sMAPE":np.nan,"error":str(exc)[:160]})
        candidates=[r for r in scores if r["sku"]==sku and np.isfinite(r["MAE"])]
        selected=min(candidates,key=lambda x:x["MAE"])["model"] if candidates else "7-day mean fallback"
        try: pred=_predict(selected,series,7) if selected!="7-day mean fallback" else np.repeat(series.tail(7).mean(),7)
        except Exception: pred=np.repeat(series.tail(7).mean(),7); selected="7-day mean fallback"
        dates=pd.date_range(series.index.max()+pd.Timedelta(days=1),periods=7)
        forecasts.extend({"sku":sku,"date":d,"forecast_demand":float(max(0,v)),"model":selected} for d,v in zip(dates,pred))
    return pd.DataFrame(scores),pd.DataFrame(forecasts)

def forecast_all_skus(sales,products,periods=7):
    rows=[]
    for sku in products.sku:
        s=_series_for_sku(sales,sku)
        try: pred=np.maximum(0,_predict("ARIMA",s,periods))
        except Exception: pred=np.repeat(float(s.tail(7).mean()),periods)
        dates=pd.date_range(s.index.max()+pd.Timedelta(days=1),periods=periods)
        rows.extend({"sku":sku,"date":d,"forecast_demand":float(v)} for d,v in zip(dates,pred))
    return pd.DataFrame(rows)
