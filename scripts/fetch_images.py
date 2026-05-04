#!/usr/bin/env python
"""Source placeholder images for every BrandImage slot.

Uses picsum.photos with a unique seed per slot, so every image is a
different real photograph (high-quality, varied subjects). These are
PLACEHOLDERS — they are not African-business-themed. Use them only to
ship the layout looking polished, then swap in proper Unsplash photos
using the search URLs in `frontend/public/images/IMAGES_NEEDED.md`.

Why not Unsplash directly?
  - Unsplash Source API is dead (returns 503 across all variants).
  - The official Unsplash API needs an API key.
  - Picsum is the only zero-config source that returns a UNIQUE photo
    per seed, which we need for layout testing.

Idempotent — files that already exist are skipped, so the moment you
swap in a real Unsplash photo, this script will leave it alone.

Usage:
    python scripts/fetch_images.py            # only fetch missing files
    python scripts/fetch_images.py --force    # re-download everything
    python scripts/fetch_images.py --quiet    # only print errors
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_IMAGES = ROOT / "frontend" / "public" / "images"

# (relative_path, width, height) — seed is derived from the path so each
# slot gets a unique-but-stable photo.
SLOTS: list[tuple[str, int, int]] = [
    # About
    ("about/hero.jpg",                 1200, 1000),
    ("about/founder.jpg",               640,  800),
    # Careers
    ("careers/hero.jpg",               1200, 1000),
    # Partners — Business
    ("partners/business/hero.jpg",     1200,  900),
    ("partners/business/sidebar.jpg",   800,  600),
    ("partners/business/faq.jpg",       900, 1100),
    # Partners — Strategic
    ("partners/strategic/hero.jpg",    1200,  900),
    ("partners/strategic/sidebar.jpg",  800,  600),
    ("partners/strategic/faq.jpg",      900, 1100),
    # Partners — Investor
    ("partners/investor/hero.jpg",     1200,  900),
    ("partners/investor/sidebar.jpg",   800,  600),
    ("partners/investor/faq.jpg",       900, 1100),
    # Partners — Service
    ("partners/service/hero.jpg",      1200,  900),
    ("partners/service/sidebar.jpg",    800,  600),
    ("partners/service/faq.jpg",        900, 1100),
    # Ecosystem (per product)
    ("ecosystem/quatapay/hero.jpg",    1200,  900),
    ("ecosystem/abaqwa/hero.jpg",      1200,  900),
    ("ecosystem/quatafood/hero.jpg",   1200,  900),
    ("ecosystem/88basket/hero.jpg",    1200,  900),
    ("ecosystem/88brickz/hero.jpg",    1200,  900),
    ("ecosystem/o3mall/hero.jpg",      1200,  900),
    ("ecosystem/qmediq/hero.jpg",      1200,  900),
]

UA = "Mozilla/5.0 (QUATA-Digital image fetcher)"


def slot_seed(rel: str) -> str:
    # Stable, readable seed — same path → same photo. Re-running won't
    # randomly change the visuals. Tweak the prefix if you want a
    # full re-roll on the seeds.
    return "quata-v2-" + rel.replace("/", "-").replace(".jpg", "")


def fetch_one(url: str, dest: Path, tries: int = 3) -> tuple[bool, str]:
    last_err = ""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status != 200:
                    last_err = f"HTTP {r.status}"
                    continue
                ct = r.headers.get("Content-Type", "")
                if "image" not in ct.lower():
                    last_err = f"non-image (Content-Type={ct})"
                    continue
                data = r.read()
                if len(data) < 1024:
                    last_err = f"too small ({len(data)} bytes)"
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                return True, f"{len(data)//1024} KB"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * attempt)
    return False, last_err or "unknown error"


def fetch_all(slots: Iterable[tuple[str, int, int]], force: bool, quiet: bool) -> int:
    failures = 0
    for rel, w, h in slots:
        dest = PUBLIC_IMAGES / rel
        if dest.exists() and not force:
            if not quiet:
                print(f"  skip   {rel} (exists)")
            continue
        seed = slot_seed(rel)
        url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
        ok, info = fetch_one(url, dest)
        marker = "ok    " if ok else "FAIL  "
        print(f"  {marker} {rel}  ({info})")
        if not ok:
            failures += 1
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--quiet", action="store_true", help="Only print failures")
    args = parser.parse_args()

    PUBLIC_IMAGES.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(SLOTS)} placeholder images into {PUBLIC_IMAGES}…")
    print("(These are stopgap photos. See IMAGES_NEEDED.md to swap in real Unsplash images.)\n")
    failures = fetch_all(SLOTS, args.force, args.quiet)
    if failures:
        print(f"\n{failures} image(s) failed. Re-run to retry.")
        sys.exit(1)
    print("\nAll images present. Refresh the site.")


if __name__ == "__main__":
    main()
