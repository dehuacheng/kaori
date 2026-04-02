import io
import logging
import uuid
from datetime import date
from pathlib import Path

from PIL import Image
import pillow_heif

# Register HEIF/HEIC opener so Pillow can handle iPhone photos
pillow_heif.register_heif_opener()

from kaori.config import PHOTOS_DIR

logger = logging.getLogger(__name__)


def save_photo(image_bytes: bytes, extension: str = ".jpg") -> str:
    """Save photo bytes to disk, return relative path from PHOTOS_DIR.

    HEIC/HEIF images are converted to JPEG so browsers can display them.
    """
    today = date.today()
    subdir = PHOTOS_DIR / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
    subdir.mkdir(parents=True, exist_ok=True)

    # Convert HEIC/HEIF to JPEG for browser compatibility
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.format in ("HEIF", "HEIC"):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            image_bytes = buf.getvalue()
            extension = ".jpg"
            logger.debug("save_photo: converted HEIC to JPEG (%d bytes)", len(image_bytes))
    except Exception:
        pass  # If we can't detect format, save as-is

    filename = f"{uuid.uuid4().hex}{extension}"
    filepath = subdir / filename
    filepath.write_bytes(image_bytes)

    return str(filepath.relative_to(PHOTOS_DIR))


def get_resized_image_bytes(photo_path: str, max_pixels: int = 1024) -> bytes:
    """Read a photo and resize it for LLM analysis (max dimension capped).

    Returns JPEG bytes suitable for base64 encoding (<1MB typically).
    """
    abs_path = PHOTOS_DIR / photo_path
    img = Image.open(abs_path)
    img.thumbnail((max_pixels, max_pixels))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    result = buf.getvalue()
    logger.debug("get_resized_image_bytes: %s -> %dx%d, %d bytes",
                 photo_path, img.width, img.height, len(result))
    return result
