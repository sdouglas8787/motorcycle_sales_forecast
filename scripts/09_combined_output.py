"""One tidy file: history + forecast, every dimension, ready to filter.

outputs/forecast_combined.csv columns:
  date        month start
  dimension   total | style | size | brand
  segment     e.g. Total, Adventure, Large (over 500cc), Honda
  value_type  actual    - as published by MCIA
              estimated - filled where MCIA published nothing: the
                          missing Oct-2024 PDF, and months where a brand
                          fell outside the top-10 table (censored)
              forecast  - model output, Aug 2026 onward
  value       registrations
  share       share of that month's total market (blank for 'total')
  lo80/hi80   80% interval (aggregate forecast rows only)

Note: the three splits are independent marginals - MCIA's free PDFs
carry no brand x style x size cross-tab (that needs paid MCRIS data).
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
segfc = __import__("08_segment_forecast")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

COLS = ["date", "dimension", "segment", "value_type", "value",
        "share", "lo80", "hi80"]


def main() -> None:
    agg = pd.read_csv(PROC / "mcia_monthly.csv", parse_dates=["date"])
    fc = pd.read_csv(OUTPUTS / "forecast.csv", parse_dates=["date"])
    rows = []

    for r in agg.itertuples():
        rows.append(dict(
            date=r.date, dimension="total", segment="Total",
            value_type=("estimated" if "backfilled" in r.source_file
                        else "actual"),
            value=r.total))
    for r in fc.itertuples():
        rows.append(dict(
            date=r.date, dimension="total", segment="Total",
            value_type="forecast", value=r.forecast,
            lo80=r.lo80, hi80=r.hi80))

    total = agg.set_index("date").total
    for name, label in [("style", "style"), ("capacity", "size"),
                        ("brand", "brand")]:
        # Raw observations mark which cells were actually published.
        raw = pd.read_csv(PROC / f"segments_{name}.csv",
                          parse_dates=["date"])
        raw_wide = raw.pivot(index="date", columns="segment",
                             values="value")
        if name == "capacity":
            observed = pd.DataFrame({
                g: raw_wide[cols].notna().all(axis=1)
                for g, cols in segfc.SIZE_GROUPS.items()
            })
        else:
            observed = raw_wide.notna()

        shares = segfc.load_shares(name)  # gaps interpolated
        for date, row in shares.iterrows():
            for seg, share in row.items():
                obs = (seg in observed.columns
                       and date in observed.index
                       and bool(observed.loc[date, seg]))
                rows.append(dict(
                    date=date, dimension=label, segment=seg,
                    value_type="actual" if obs else "estimated",
                    value=round(share * total.loc[date]),
                    share=round(share, 4)))

        seg_fc = pd.read_csv(OUTPUTS / f"forecast_by_{label}.csv",
                             parse_dates=["date"])
        for r in seg_fc.itertuples():
            rows.append(dict(
                date=r.date, dimension=label, segment=r.segment,
                value_type="forecast", value=r.forecast, share=r.share))

    out = pd.DataFrame(rows).reindex(columns=COLS)
    out = out.sort_values(["dimension", "segment", "date"])
    out.to_csv(OUTPUTS / "forecast_combined.csv", index=False)
    print(f"{len(out)} rows -> outputs/forecast_combined.csv")
    print(out.groupby(["dimension", "value_type"]).size().to_string())


if __name__ == "__main__":
    main()
