"""Does weather predict UK monthly motorcycle registrations?

Specification tests behind the weather term used in 04_model.py. Each
candidate adds weather to the base model (trend + month dummies + event
dummies) and is judged on adjusted R^2 / AIC and coefficient p-values.

Findings (79 months, Jan 2020 - Jul 2026):
  - Contemporaneous monthly anomalies (temperature, sunshine, rainfall):
    all insignificant; temperature even sign-flips, confounded by 2025
    being warm and sunny while the market was depressed post-Euro-5+.
  - In-season (Mar-Sep) interactions of the same: no better.
  - LAGGED temperature anomaly in riding season is the one survivor:
    +1C warmer than normal -> roughly +4% registrations the following
    month (p ~ 0.07). Consistent with purchase -> registration lag.
"""

import warnings

import pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

model = __import__("04_model")

BASE = ("log_total ~ t + C(month) + covid_lockdown + euro5plus_prebuy "
        "+ euro5plus_payback + lockdown3")

CANDIDATES = {
    "no weather": "",
    "contemporaneous, all": (
        " + tmean_anom + sunshine_anom + rainfall_anom"),
    "in-season, all": (
        " + tmean_anom:season + sunshine_anom:season + rainfall_anom:season"),
    "lag-1 temp + sunshine": " + tmean_anom_lag1 + sunshine_anom_lag1",
    "lag-1 in-season (chosen)": (
        " + tmean_anom_lag1:season + sunshine_anom_lag1:season"),
}


def main() -> None:
    df = model.load_dataset()
    weather = pd.read_csv(
        model.PROC / "weather_monthly.csv", parse_dates=["date"]
    )
    df = df.merge(
        weather[["date", "sunshine_anom", "rainfall_anom"]], on="date"
    )
    df["season"] = df.month.between(3, 9).astype(float)
    for c in ["tmean_anom", "sunshine_anom", "rainfall_anom"]:
        df[f"{c}_lag1"] = df[c].shift(1)
    df = df.dropna(subset=["tmean_anom_lag1"])

    for label, extra in CANDIDATES.items():
        fit = smf.ols(BASE + extra, data=df).fit()
        print(f"\n=== {label}: adj R^2 {fit.rsquared_adj:.4f}, "
              f"AIC {fit.aic:.1f}")
        terms = [i for i in fit.params.index if "anom" in i]
        for term in terms:
            print(f"    {term:28s} {fit.params[term]:+.4f} "
                  f"(p={fit.pvalues[term]:.3f})")


if __name__ == "__main__":
    main()
