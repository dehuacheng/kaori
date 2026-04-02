#!/usr/bin/env python3
"""Compress existing photos in PHOTOS_DIR to max 1600px, JPEG quality 85.

Overwrites originals in-place. Respects KAORI_TEST_MODE.

Usage:
    python scripts/compress_photos.py            # compress for real
    python scripts/compress_photos.py --dry-run   # report only, no changes
"""

import argparse
import io
import sys
from pathlib import Path

from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

# Import PHOTOS_DIR so we respect KAORI_TEST_MODE automatically
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kaori.config import PHOTOS_DIR

MAX_DIMENSION = 1600
JPEG_QUALITY = 85


def compress_photo(path: Path, dry_run: bool) -> tuple[int, int]:
    """Compress a single photo. Returns (original_size, new_size)."""
    original_size = path.stat().st_size
    img = Image.open(path)
    w, h = img.size

    if max(w, h) <= MAX_DIMENSION and path.suffix.lower() in (".jpg", ".jpeg"):
        # Already small enough and already JPEG — check if re-saving helps
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        new_size = buf.tell()
        if new_size >= original_size:
            return original_size, original_size  # skip, already optimal

        if not dry_run:
            path.write_bytes(buf.getvalue())
        return original_size, new_size

    img = img.convert("RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    new_size = buf.tell()

    if not dry_run:
        # If extension was not .jpg, rename
        if path.suffix.lower() not in (".jpg", ".jpeg"):
            new_path = path.with_suffix(".jpg")
            path.unlink()
            path = new_path
        path.write_bytes(buf.getvalue())

    return original_size, new_size


def main():
    parser = argparse.ArgumentParser(description="Compress existing kaori photos")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    args = parser.parse_args()

    print(f"Photos dir: {PHOTOS_DIR}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'COMPRESS'}")
    print()

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    photos = [p for p in PHOTOS_DIR.rglob("*") if p.suffix.lower() in extensions]

    if not photos:
        print("No photos found.")
        return

    total_original = 0
    total_new = 0
    compressed = 0
    skipped = 0

    for path in sorted(photos):
        try:
            orig, new = compress_photo(path, args.dry_run)
            total_original += orig
            total_new += new
            rel = path.relative_to(PHOTOS_DIR)
            if orig == new:
                skipped += 1
                print(f"  SKIP  {rel}  ({orig / 1024:.0f} KB — already optimal)")
            else:
                compressed += 1
                pct = (1 - new / orig) * 100
                print(f"  {'WOULD' if args.dry_run else 'OK'}    {rel}  "
                      f"{orig / 1024:.0f} KB → {new / 1024:.0f} KB  ({pct:.0f}% reduction)")
        except Exception as e:
            print(f"  ERROR {path.relative_to(PHOTOS_DIR)}: {e}")

    print()
    print(f"Total: {len(photos)} photos, {compressed} compressed, {skipped} skipped")
    print(f"Size:  {total_original / 1024 / 1024:.1f} MB → {total_new / 1024 / 1024:.1f} MB  "
          f"(saved {(total_original - total_new) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
