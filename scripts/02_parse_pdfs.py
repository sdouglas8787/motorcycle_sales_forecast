"""Parse MCIA press-statistics PDFs into a monthly registrations series.

Each PDF's "Market Overview" page carries, for the reporting month and the
same month a year earlier: total registrations plus mopeds / motorcycles /
tricycles subtotals. The reporting month is read from the page header, not
the filename (filenames are inconsistent and one is missing its year).

Outputs:
  data/processed/mcia_monthly.csv   one row per month, with provenance
"""

import calendar
import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_pdfs"
OUT = ROOT / "data" / "processed"

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
HEADER_RE = re.compile(
    r"Press Statistics\s+([A-Za-z]+)\s+(20\d\d)", re.IGNORECASE
)
TOTAL_LABELS = {
    "TOTAL REGISTRATIONS": "total",
    "TOTAL MOTORCYCLES": "motorcycles",
    "TOTAL MOPEDS": "mopeds",
    "TOTAL TRICYCLES": "tricycles",
}


def plain_numbers(text: str) -> list[int]:
    """Numbers in order, skipping percentage/sign tokens."""
    out = []
    for tok in text.split():
        if "%" in tok or tok.startswith(("+", "-")):
            continue
        if re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", tok):
            out.append(int(tok.replace(",", "")))
    return out


def parse_pdf(path: Path) -> dict | None:
    with pdfplumber.open(path) as pdf:
        page_text = None
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "TOTAL REGISTRATIONS" in text:
                page_text = text
                break
    if page_text is None:
        return None

    header = HEADER_RE.search(page_text)
    if not header or header.group(1).lower() not in MONTHS:
        return None
    month = MONTHS[header.group(1).lower()]
    year = int(header.group(2))

    row = {"year": year, "month": month, "source_file": path.name}
    for line in page_text.splitlines():
        stripped = line.strip()
        for label, key in TOTAL_LABELS.items():
            if stripped.upper().startswith(label):
                nums = plain_numbers(stripped[len(label):])
                # First two plain numbers are current month and the same
                # month a year earlier (both PDF layouts agree on this).
                if len(nums) >= 2 and key not in row:
                    row[key], row[f"{key}_prev_year"] = nums[0], nums[1]
    return row if "total" in row else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(RAW.glob("*.pdf")):
        row = parse_pdf(path)
        if row is None:
            print(f"  FAILED to parse {path.name}")
        else:
            rows.append(row)

    df = pd.DataFrame(rows).sort_values(["year", "month"])
    dupes = df[df.duplicated(["year", "month"], keep=False)]
    if not dupes.empty:
        print("Duplicate months (keeping first):")
        print(dupes[["year", "month", "source_file", "total"]].to_string())
    df = df.drop_duplicates(["year", "month"], keep="first")

    # Cross-validate: this month's value vs next year's "previous year" figure.
    direct = df.set_index(["year", "month"])["total"]
    backref = {
        (y - 1, m): v
        for (y, m), v in df.set_index(["year", "month"])[
            "total_prev_year"
        ].items()
    }
    mismatches = 0
    for key, val in direct.items():
        if key in backref and backref[key] != val:
            diff = backref[key] - val
            print(f"  revision {key}: reported {val}, later {backref[key]} "
                  f"({diff:+d}, {diff / val:+.2%})")
            mismatches += 1
    print(f"Cross-validation: {mismatches} revisions out of "
          f"{sum(1 for k in direct.index if k in backref)} comparable months")

    # Fill months with no PDF using the back-reference from a year later.
    have = set(direct.index)
    for (y, m), v in sorted(backref.items()):
        if (y, m) not in have and (y, m) >= (2020, 1):
            rows_fill = {
                "year": y, "month": m, "total": v,
                "source_file": "backfilled from following year's PDF",
            }
            df = pd.concat([df, pd.DataFrame([rows_fill])])
            print(f"  backfilled {y}-{m:02d}: {v}")

    df["date"] = pd.to_datetime(
        df.year.astype(str) + "-" + df.month.astype(str).str.zfill(2) + "-01"
    )
    df = df.sort_values("date")
    cols = ["date", "total", "motorcycles", "mopeds", "tricycles",
            "total_prev_year", "source_file"]
    df[cols].to_csv(OUT / "mcia_monthly.csv", index=False)

    full = pd.date_range(df.date.min(), df.date.max(), freq="MS")
    missing = full.difference(df.date)
    print(f"\n{len(df)} months, {df.date.min():%b %Y} - {df.date.max():%b %Y}")
    print(f"Missing months: {[f'{d:%Y-%m}' for d in missing] or 'none'}")


if __name__ == "__main__":
    main()
