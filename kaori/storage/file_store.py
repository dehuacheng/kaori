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

    All images are converted to JPEG, resized to max 1600px, and compressed
    (quality=85) to keep file sizes reasonable for serving.
    """
    today = date.today()
    subdir = PHOTOS_DIR / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
    subdir.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()
        extension = ".jpg"
        logger.debug("save_photo: compressed to %dx%d, %d bytes",
                     img.width, img.height, len(image_bytes))
    except Exception:
        logger.warning("save_photo: could not compress image, saving as-is")

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
