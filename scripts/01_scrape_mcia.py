"""Crawl MCIA press-statistics listings and download the monthly files.

MCIA organises press statistics under year category pages
(https://mcia.co.uk/downloads/15 -> one page per year). Each year page
holds a mix of direct file links (/downloads/download/<id>) and per-month
sub-folder pages (/downloads/<id>), which in turn hold the file links.

Files are saved to data/raw_pdfs/ under their original names. Where a
month is published as both .pdf and .xlsx, both are kept; the parser
prefers xlsx.
"""

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://mcia.co.uk"
PRESS_STATS_ROOT = f"{BASE}/downloads/15"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw_pdfs"

session = requests.Session()
session.headers.update(HEADERS)


def get_soup(url: str) -> BeautifulSoup:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def file_links(soup: BeautifulSoup) -> dict[str, str]:
    """Map file name -> download URL for direct file links on a page."""
    out = {}
    for a in soup.select('a[href*="/downloads/download/"]'):
        title = a.get("title", "") or a.get_text(strip=True)
        name = re.sub(r"^(Download|Open)\s+", "", title).strip()
        if name:
            out[name] = a["href"]
    return out


def subfolder_links(soup: BeautifulSoup) -> dict[str, str]:
    """Map folder title -> URL for per-month sub-folder pages."""
    out = {}
    for a in soup.select('a[href*="/downloads/"]'):
        href = a["href"]
        if "/downloads/download/" in href:
            continue
        m = re.match(r"^Open\s+(.*)$", a.get("title", "") or "")
        if m:
            out[m.group(1).strip()] = href
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    root = get_soup(PRESS_STATS_ROOT)

    year_pages = {
        title: url
        for title, url in subfolder_links(root).items()
        if re.fullmatch(r"20\d\d", title)
    }
    print(f"Year pages: {sorted(year_pages)}")

    all_files: dict[str, str] = {}
    for year in sorted(year_pages):
        soup = get_soup(year_pages[year])
        all_files.update(file_links(soup))
        for sub_title, sub_url in subfolder_links(soup).items():
            if re.fullmatch(r"20\d\d", sub_title):
                continue  # sibling year links repeated in nav
            sub = get_soup(sub_url)
            all_files.update(file_links(sub))
            time.sleep(0.3)
        time.sleep(0.3)

    stats = {
        name: url
        for name, url in all_files.items()
        if "press" in name.lower() and "statistic" in name.lower()
    }
    print(f"Found {len(stats)} press-statistics files")

    for name, url in sorted(stats.items()):
        dest = OUT_DIR / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  skip (exists) {name}")
            continue
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  saved {name} ({len(resp.content):,} bytes)")
        time.sleep(0.3)


if __name__ == "__main__":
    sys.exit(main())
