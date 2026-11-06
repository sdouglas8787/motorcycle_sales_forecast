"""Score the published forecast against MCIA actuals as they arrive.

The forecast in outputs/forecast.csv was fixed when it was published and is
never revised. Each run joins whatever actuals now exist and rewrites
outputs/forecast_vs_actual.csv: the forecast's public scorecard. Run after
01 and 02 have pulled new months.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

fc = pd.read_csv(ROOT / "outputs" / "forecast.csv", parse_dates=["date"])
ac = pd.read_csv(ROOT / "data" / "processed" / "mcia_monthly.csv", parse_dates=["date"])
actual_col = ac.columns[1]                      # headline total registrations

m = fc.merge(ac[["date", actual_col]].rename(columns={actual_col: "actual"}),
             on="date", how="left")
m = m[m["actual"].notna()].copy()
if m.empty:
    raise SystemExit("No actuals overlap the forecast window yet.")

m["error"] = m["actual"] - m["forecast"]
m["ape_pct"] = (m["error"].abs() / m["actual"] * 100).round(1)
m["within_80"] = (m["actual"] >= m["lo80"]) & (m["actual"] <= m["hi80"])
m["sarimax_ape_pct"] = ((m["actual"] - m["sarimax"]).abs() / m["actual"] * 100).round(1)

out = m[["date", "forecast", "lo80", "hi80", "actual", "error", "ape_pct",
         "within_80", "sarimax", "sarimax_ape_pct"]]
out.to_csv(ROOT / "outputs" / "forecast_vs_actual.csv", index=False)

n = len(m)
print(out.to_string(index=False))
print(f"\n{n} month(s) scored | MAPE {m['ape_pct'].mean():.1f}% "
      f"(backtest said 10.3%) | SARIMAX MAPE {m['sarimax_ape_pct'].mean():.1f}% "
      f"| within 80% interval: {int(m['within_80'].sum())}/{n}")
same_sign = (m["error"] > 0).all() or (m["error"] < 0).all()
if same_sign and n >= 3:
    direction = "under" if (m["error"] > 0).all() else "over"
    print(f"Note: all {n} errors {direction}-forecast. Too few months to call "
          f"bias; worth watching, not yet correcting.")
