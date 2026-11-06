"""Split the aggregate forecast by style, engine-size group and brand.

Top-down approach: the aggregate model (04_model.py) carries the trend,
seasonality and events from the full 79-month history; each segment is
then forecast as a SHARE of the market from the 42 months of segment
data (Jan 2023+, when the current MCIA taxonomy begins) and multiplied
through the aggregate forecast. Shares are modelled with
share ~ trend + month dummies, clipped at zero and renormalised so the
splits always add back to the aggregate.

Brands: MCIA publishes a top-10 table only, so a brand outside the top
ten in a month is censored, not zero. Brands present in nearly every
month are kept as named series (gaps share-interpolated); the rest fold
into "Other" = total - named.

Size groups are defined in SIZE_GROUPS - rename or re-cut them there.
The underlying MCIA ICE bands are 0-50/51-125/126-500/501-750/751-1000/
1000+cc, so group boundaries must fall on those cut points. Electric is
reported by kW, not cc, and is kept as its own group.

Outputs: outputs/forecast_by_style.csv, forecast_by_size.csv,
forecast_by_brand.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

SIZE_GROUPS = {
    "Small (up to 125cc)": ["0-50cc", "51-125cc"],
    "Medium (126-500cc)": ["126-500cc"],
    "Large (over 500cc)": ["501-750cc", "751-1000cc", "1000cc+"],
    "Electric": ["Electric"],
}

# Keep a brand as a named series when it appears in the top-10 table in
# at least this share of months; everything else folds into "Other".
BRAND_PRESENCE_MIN = 0.9


def load_shares(name: str) -> pd.DataFrame:
    """Months x segments share-of-market matrix, gaps interpolated."""
    seg = pd.read_csv(PROC / f"segments_{name}.csv", parse_dates=["date"])
    agg = pd.read_csv(
        PROC / "mcia_monthly.csv", parse_dates=["date"]
    ).set_index("date").total

    wide = seg.pivot(index="date", columns="segment", values="value")
    if name == "capacity":
        grouped = pd.DataFrame({
            g: wide[cols].sum(axis=1) for g, cols in SIZE_GROUPS.items()
        })
        wide = grouped
    if name == "brand":
        presence = wide.notna().mean()
        named = presence[presence >= BRAND_PRESENCE_MIN].index.tolist()
        wide = wide[named]

    full = pd.date_range(wide.index.min(), wide.index.max(), freq="MS")
    shares = wide.reindex(full).div(agg.reindex(full), axis=0)
    shares = shares.interpolate(limit_direction="both")
    other = 1.0 - shares.sum(axis=1)
    if name == "brand" or other.abs().max() > 0.005:
        shares["Other"] = other
    shares.index.name = "date"
    return shares


def forecast_shares(shares: pd.DataFrame, dates: pd.DatetimeIndex):
    """Per-segment OLS on trend + month dummies, then renormalise."""
    hist = shares.reset_index()
    hist["t"] = np.arange(len(hist))
    future = pd.DataFrame({"date": dates})
    future["t"] = np.arange(len(hist), len(hist) + len(dates))
    for df in (hist, future):
        df["month"] = df.date.dt.month

    pred = {}
    for seg in shares.columns:
        hist["y"] = hist[seg]
        fit = smf.ols("y ~ t + C(month)", data=hist).fit()
        pred[seg] = fit.predict(future).clip(lower=0.0).to_numpy()
    out = pd.DataFrame(pred, index=dates)
    return out.div(out.sum(axis=1), axis=0)


def main() -> None:
    fc = pd.read_csv(OUTPUTS / "forecast.csv", parse_dates=["date"])
    dates = pd.DatetimeIndex(fc.date)
    total = fc.set_index("date").forecast

    for name, label in [("style", "style"), ("capacity", "size"),
                        ("brand", "brand")]:
        shares = load_shares(name)
        future_shares = forecast_shares(shares, dates)
        result = future_shares.mul(total, axis=0).round(0)

        long = (result.rename_axis("date")
                .reset_index()
                .melt(id_vars="date", var_name="segment",
                      value_name="forecast"))
        long["share"] = (future_shares.rename_axis("date").reset_index()
                         .melt(id_vars="date")["value"].round(4))
        path = OUTPUTS / f"forecast_by_{label}.csv"
        long.sort_values(["date", "segment"]).to_csv(path, index=False)

        yr = result.sum()
        print(f"\n=== {label}: next-12-month forecast "
              f"(total {yr.sum():,.0f})")
        for seg, v in yr.sort_values(ascending=False).items():
            print(f"  {seg:22s} {v:9,.0f}  ({v / yr.sum():.1%})")


if __name__ == "__main__":
    main()
