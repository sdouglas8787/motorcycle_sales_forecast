"""Fit and compare forecasting models for UK monthly motorcycle registrations.

Models, in order of complexity:
  1. Seasonal naive        same month last year (the baseline to beat)
  2. OLS                   log(sales) ~ trend + month dummies + weather +
                           event dummies
  3. SARIMAX               same regressors + seasonal ARIMA errors

Weather term: contemporaneous anomalies tested insignificant (see
05_weather_tests.py). The one term that survives is the PREVIOUS month's
temperature anomaly during riding season (Mar-Sep) - warm weather drives
purchases, registration follows a month later. Marginal (p~0.07) but
physically sensible, and the first forecast step uses known weather.

Backtest: rolling-origin one-step-ahead over the last BACKTEST_MONTHS
months. The final model forecasts HORIZON months ahead with future
anomalies at zero (climatology) plus warm/cool scenarios.

Outputs:
  data/processed/model_dataset.csv, backtest_results.csv,
  ols_coefficients.csv; outputs/forecast.csv
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

BACKTEST_MONTHS = 18
HORIZON = 12
TEMP_SCENARIO = 0.8  # ~1 sd of monthly tmean anomaly, degrees C

EVENTS = {
    "2020-04": "covid_lockdown", "2020-05": "covid_lockdown",
    "2021-01": "lockdown3", "2021-02": "lockdown3",
    "2024-12": "euro5plus_prebuy",
    "2025-01": "euro5plus_payback", "2025-02": "euro5plus_payback",
}
EVENT_NAMES = sorted(set(EVENTS.values()))
REGRESSORS = ["temp_signal"] + EVENT_NAMES

FORMULA = "log_total ~ t + C(month) + " + " + ".join(REGRESSORS)


def load_dataset() -> pd.DataFrame:
    sales = pd.read_csv(PROC / "mcia_monthly.csv", parse_dates=["date"])
    weather = pd.read_csv(PROC / "weather_monthly.csv", parse_dates=["date"])
    df = sales[["date", "total"]].merge(
        weather[["date", "tmean_anom"]], on="date", how="left"
    )
    df["log_total"] = np.log(df.total)
    df["t"] = np.arange(len(df))
    df["month"] = df.date.dt.month
    # Riding-season gate on last month's temperature anomaly
    season = df.month.between(3, 9).astype(float)
    df["temp_signal"] = (df.tmean_anom.shift(1) * season).fillna(0.0)
    ym = df.date.dt.strftime("%Y-%m")
    for name in EVENT_NAMES:
        df[name] = ym.map(
            lambda s, n=name: 1.0 if EVENTS.get(s) == n else 0.0
        )
    return df


def ols_forecast(train: pd.DataFrame, future: pd.DataFrame) -> np.ndarray:
    fit = smf.ols(FORMULA, data=train).fit()
    pred = fit.predict(future)
    return np.exp(pred + fit.mse_resid / 2).to_numpy()


def ols_forecast_ci(train: pd.DataFrame, future: pd.DataFrame):
    """OLS mean forecast plus 80% prediction interval, back-transformed."""
    fit = smf.ols(FORMULA, data=train).fit()
    pred = fit.get_prediction(future)
    frame = pred.summary_frame(alpha=0.2)
    mean = np.exp(frame["mean"] + fit.mse_resid / 2)
    return (mean.to_numpy(),
            np.exp(frame[["obs_ci_lower", "obs_ci_upper"]]).to_numpy())


def sarimax_forecast(train: pd.DataFrame, future: pd.DataFrame):
    model = sm.tsa.SARIMAX(
        train.log_total, exog=train[REGRESSORS],
        order=(1, 0, 0), seasonal_order=(1, 1, 0, 12), trend="c",
    )
    fit = model.fit(disp=False)
    fc = fit.get_forecast(len(future), exog=future[REGRESSORS])
    mean = np.exp(fc.predicted_mean + fc.var_pred_mean / 2)
    ci = np.exp(fc.conf_int(alpha=0.2))  # 80% interval
    return mean.to_numpy(), ci.to_numpy()


def backtest(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i in range(len(df) - BACKTEST_MONTHS, len(df)):
        train, future = df.iloc[:i], df.iloc[i:i + 1]
        rows.append({
            "date": future.date.iloc[0],
            "actual": future.total.iloc[0],
            "seasonal_naive": df.total.iloc[i - 12],
            "ols": ols_forecast(train, future)[0],
            "sarimax": sarimax_forecast(train, future)[0][0],
        })
    return pd.DataFrame(rows)


def build_future(df: pd.DataFrame, temp_anom: float = 0.0) -> pd.DataFrame:
    dates = pd.date_range(
        df.date.max() + pd.DateOffset(months=1), periods=HORIZON, freq="MS"
    )
    future = pd.DataFrame({"date": dates})
    future["t"] = np.arange(len(df), len(df) + HORIZON)
    future["month"] = future.date.dt.month
    season = future.month.between(3, 9).astype(float)
    future["temp_signal"] = temp_anom * season
    # First step: the previous month's weather is already observed.
    last_anom = df.tmean_anom.iloc[-1]
    if pd.notna(last_anom) and future.month.iloc[0] in range(3, 10):
        future.loc[future.index[0], "temp_signal"] = last_anom
    for name in EVENT_NAMES:
        future[name] = 0.0
    return future


def main() -> None:
    OUTPUTS.mkdir(exist_ok=True)
    df = load_dataset()
    df.to_csv(PROC / "model_dataset.csv", index=False)
    print(f"Dataset: {len(df)} months to {df.date.max():%b %Y}")

    fit = smf.ols(FORMULA, data=df).fit()
    coefs = pd.DataFrame({"coef": fit.params, "p_value": fit.pvalues}).round(4)
    coefs.to_csv(PROC / "ols_coefficients.csv")
    print(f"\nOLS R^2 adj = {fit.rsquared_adj:.3f}")
    print(coefs.loc[[c for c in coefs.index if "month" not in c]].to_string())

    bt = backtest(df)
    bt.to_csv(PROC / "backtest_results.csv", index=False)
    print(f"\nBacktest (1-step ahead, last {BACKTEST_MONTHS} months):")
    for col in ["seasonal_naive", "ols", "sarimax"]:
        err = bt[col] - bt.actual
        mape = (err.abs() / bt.actual).mean()
        print(f"  {col:15s} MAPE {mape:6.1%}   bias {err.mean():+8.0f}")

    # Final forecast from the backtest winner (OLS); SARIMAX kept for
    # reference alongside.
    future = build_future(df)
    mean, ci = ols_forecast_ci(df, future)
    warm = ols_forecast(df, build_future(df, TEMP_SCENARIO))
    cool = ols_forecast(df, build_future(df, -TEMP_SCENARIO))
    sarimax_mean, _ = sarimax_forecast(df, future)
    out = pd.DataFrame({
        "date": future.date, "forecast": mean.round(0),
        "lo80": ci[:, 0].round(0), "hi80": ci[:, 1].round(0),
        "warm_summer": warm.round(0), "cool_summer": cool.round(0),
        "sarimax": sarimax_mean.round(0),
    })
    out.to_csv(OUTPUTS / "forecast.csv", index=False)
    print("\n12-month forecast (climatology weather):")
    print(out.to_string(index=False))
    print(f"\nNext-12-month total: {mean.sum():,.0f}  "
          f"(warm {warm.sum():,.0f} / cool {cool.sum():,.0f})")


if __name__ == "__main__":
    main()
