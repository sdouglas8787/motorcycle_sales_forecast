"""Parse style, capacity-band and brand splits from the 2023+ MCIA PDFs.

The January 2023 format change introduced the current style taxonomy
(ADVENTURE, COMPETITION, ...), the current ICE capacity bands and a
"Best Selling Brands" top-10 table, none of which exist before 2023 -
so segment series start Jan 2023 even though the aggregate series
starts Jan 2020.

Outputs (data/processed/):
  segments_style.csv      one row per (month, style)   [motorcycles only,
                          plus Moped / Tricycle rollups]
  segments_capacity.csv   one row per (month, ICE band + Electric)
  segments_brand.csv      one row per (month, top-10 brand)
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
HEADER_RE = re.compile(r"Press Statistics\s+([A-Za-z]+)\s+(20\d\d)")

STYLE_ROWS = [
    "ADVENTURE", "COMPETITION", "CUSTOM", "MODERN CLASSIC", "NAKED",
    "ROAD SPORT", "SCOOTER", "TOURING", "UNSPECIFIED",
]
ICE_BANDS = ["0-50cc", "51-125cc", "126-500cc", "501-750cc",
             "751-1000cc", "1000cc+"]


def month_key(text: str):
    m = HEADER_RE.search(text)
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return int(m.group(2)), MONTHS[m.group(1).lower()]


def first_number(text: str):
    m = re.search(r"(\d{1,3}(?:,\d{3})*|\d+)\b", text)
    return int(m.group(1).replace(",", "")) if m else None


def plain_numbers(text: str) -> list[int]:
    return [int(t.replace(",", "")) for t in text.split()
            if re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", t)]


def parse_styles(text: str, year: int, month: int) -> list[dict]:
    """Motorcycle styles from the Market Overview page, plus rollups."""
    rows = []
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines)
                     if l.strip().startswith("MOTORCYCLES"))
    except StopIteration:
        return rows
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("TOTAL MOTORCYCLES"):
            break
        for style in STYLE_ROWS:
            if stripped.upper().startswith(style):
                val = first_number(stripped[len(style):])
                if val is not None:
                    rows.append({"year": year, "month": month,
                                 "segment": style.title(), "value": val})
                break
    for label, seg in [("TOTAL MOPEDS", "Moped"), ("TOTAL TRICYCLES",
                                                   "Tricycle")]:
        for line in lines:
            if line.strip().startswith(label):
                val = first_number(line.strip()[len(label):])
                if val is not None:
                    rows.append({"year": year, "month": month,
                                 "segment": seg, "value": val})
                break
    return rows


def parse_capacity(text: str, year: int, month: int) -> list[dict]:
    """A full row carries four numbers (MTH cur/prev, YTD cur/prev); some
    2023 PDFs contain a stray near-empty duplicate of the 51-125cc row,
    so among candidate lines per band the fullest one wins."""
    candidates: dict[str, list[int]] = {}
    for line in (l.strip() for l in text.splitlines()):
        for label, seg in ([(b, b) for b in ICE_BANDS]
                           + [("ELECTRIC", "Electric")]):
            if line.startswith(label + " "):
                nums = plain_numbers(line[len(label):])
                if len(nums) >= 2 and (
                    seg not in candidates
                    or len(nums) > len(candidates[seg])
                ):
                    candidates[seg] = nums
                break
    return [{"year": year, "month": month, "segment": seg,
             "value": nums[0]} for seg, nums in candidates.items()]


def parse_brands(text: str, year: int, month: int) -> list[dict]:
    rows = []
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines)
                     if "Best Selling Brands" in l)
    except StopIteration:
        return rows
    for line in lines[start:]:
        m = re.match(r"^([A-Za-z][A-Za-z .&'-]*?)\s+(\d{1,3}(?:,\d{3})*)$",
                     line.strip())
        if m and m.group(1).strip().lower() not in ("mth", "page"):
            rows.append({"year": year, "month": month,
                         "segment": m.group(1).strip(),
                         "value": int(m.group(2).replace(",", ""))})
    return rows


def main() -> None:
    styles, capacity, brands = [], [], []
    for path in sorted(RAW.glob("*.pdf")):
        with pdfplumber.open(path) as pdf:
            texts = [p.extract_text() or "" for p in pdf.pages]
        key = next((k for t in texts if (k := month_key(t))), None)
        if key is None or key < (2023, 1):
            continue
        year, month = key
        for text in texts:
            if "Market Overview" in text:
                styles += parse_styles(text, year, month)
            elif "Powertrain and Capacity" in text:
                capacity += parse_capacity(text, year, month)
            elif "Best Selling Brands" in text:
                brands += parse_brands(text, year, month)

    for name, rows in [("style", styles), ("capacity", capacity),
                       ("brand", brands)]:
        df = pd.DataFrame(rows).drop_duplicates(
            ["year", "month", "segment"]
        )
        df["date"] = pd.to_datetime(
            dict(year=df.year, month=df.month, day=1)
        )
        df = df.sort_values(["date", "segment"])
        df[["date", "segment", "value"]].to_csv(
            OUT / f"segments_{name}.csv", index=False
        )
        n_months = df.date.nunique()
        print(f"{name}: {n_months} months, "
              f"{df.segment.nunique()} segments, "
              f"{df.date.min():%Y-%m} - {df.date.max():%Y-%m}")


if __name__ == "__main__":
    main()
