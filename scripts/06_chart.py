"""Render the headline chart: actuals, forecast and 80% interval.

Outputs outputs/forecast_chart.png (used by the README).
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BLUE = "#2a78d6"
SURFACE = "#fcfcfb"


def main() -> None:
    actual = pd.read_csv(
        ROOT / "data" / "processed" / "mcia_monthly.csv", parse_dates=["date"]
    )
    fc = pd.read_csv(ROOT / "outputs" / "forecast.csv", parse_dates=["date"])

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    fig.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    ax.plot(actual.date, actual.total, color=BLUE, lw=1.6, label="Actual")
    # join the forecast to the last actual point
    join = pd.concat([
        actual[["date", "total"]].tail(1).rename(columns={"total": "forecast"}),
        fc[["date", "forecast"]],
    ])
    ax.plot(join.date, join.forecast, color=BLUE, lw=1.6, ls=(0, (4, 3)),
            label="Forecast")
    ax.fill_between(fc.date, fc.lo80, fc.hi80, color=BLUE, alpha=0.10,
                    lw=0, label="80% interval")

    for x, y, text, dy in [
        ("2020-04-01", 1623, "COVID lockdown", -14),
        ("2024-12-01", 11206, "Euro 5+ pre-registration", 10),
    ]:
        d = pd.Timestamp(x)
        ax.scatter([d], [y], s=18, color=BLUE, zorder=3,
                   edgecolors=SURFACE, linewidths=1.5)
        ax.annotate(text, (d, y), xytext=(0, dy),
                    textcoords="offset points", ha="center",
                    fontsize=8, color=MUTED)

    ax.set_title("UK new motorcycle registrations, monthly",
                 color=INK, fontsize=12, loc="left", pad=12)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper right", fontsize=8.5,
              labelcolor=INK)

    fig.tight_layout()
    out = ROOT / "outputs" / "forecast_chart.png"
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
