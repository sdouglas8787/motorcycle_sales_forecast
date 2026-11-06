"""Fetch Met Office UK monthly climate series and derive anomalies.

Downloads HadUK-Grid areal series (mean temperature, sunshine hours,
rainfall), computes 1991-2020 monthly normals, and writes one row per
month with actuals, normals and anomalies.

Outputs:
  data/processed/weather_monthly.csv
  data/processed/weather_normals.csv   (12 rows, used for future months)
"""

import io
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"

SERIES = {
    "tmean": "Tmean",     # degrees C, monthly mean
    "sunshine": "Sunshine",  # hours, monthly total
    "rainfall": "Rainfall",  # mm, monthly total
}
URL = ("https://www.metoffice.gov.uk/pub/data/weather/uk/climate/"
       "datasets/{name}/date/UK.txt")
NORMAL_YEARS = (1991, 2020)


def fetch_series(name: str, key: str) -> pd.DataFrame:
    resp = requests.get(URL.format(name=name), timeout=30)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if l.startswith("year"))
    df = pd.read_csv(
        io.StringIO("\n".join(lines[header_idx:])),
        sep=r"\s+", na_values=["---"],
    )
    months = df.columns[1:13]
    long = df.melt(id_vars="year", value_vars=months,
                   var_name="month_name", value_name=key)
    long["month"] = long.month_name.map(
        {m: i + 1 for i, m in enumerate(months)}
    )
    return long[["year", "month", key]].dropna()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    merged = None
    for key, name in SERIES.items():
        df = fetch_series(name, key)
        merged = df if merged is None else merged.merge(
            df, on=["year", "month"], how="outer"
        )

    lo, hi = NORMAL_YEARS
    base = merged[(merged.year >= lo) & (merged.year <= hi)]
    normals = base.groupby("month")[list(SERIES)].mean().round(2)
    normals.columns = [f"{c}_normal" for c in normals.columns]
    normals.to_csv(OUT / "weather_normals.csv")

    out = merged.merge(normals, on="month")
    for key in SERIES:
        out[f"{key}_anom"] = (out[key] - out[f"{key}_normal"]).round(2)
    out["date"] = pd.to_datetime(
        dict(year=out.year, month=out.month, day=1)
    )
    out = out.sort_values("date")
    out.to_csv(OUT / "weather_monthly.csv", index=False)
    print(f"{len(out)} months, {out.date.min():%Y-%m} - {out.date.max():%Y-%m}")
    print(normals)


if __name__ == "__main__":
    main()
