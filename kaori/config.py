import logging
import logging.handlers
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"

# Test mode: uses separate DB and photos dir so real data is never touched
TEST_MODE = os.environ.get("KAORI_TEST_MODE", "").lower() in ("1", "true", "yes")

if TEST_MODE:
    DB_PATH = DATA_DIR / "kaori_test.db"
    PHOTOS_DIR = DATA_DIR / "photos_test"
    STATEMENTS_DIR = DATA_DIR / "statements_test"
else:
    DB_PATH = DATA_DIR / "kaori.db"
    PHOTOS_DIR = DATA_DIR / "photos"
    STATEMENTS_DIR = DATA_DIR / "statements"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
PHOTOS_DIR.mkdir(exist_ok=True)
STATEMENTS_DIR.mkdir(exist_ok=True)

# Auth (single-user, Tailscale-gated)
API_TOKEN = os.environ.get("KAORI_TOKEN", "dev-token")

# LLM mode: "claude_cli", "claude_api", or "codex_cli"
LLM_MODE = os.environ.get("KAORI_LLM_MODE", "claude_cli")

# User defaults (per-kg rates, used when profile not yet configured)
DEFAULT_PROTEIN_PER_KG = 1.6
DEFAULT_CARBS_PER_KG = 3.0


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging():
    """Configure file + console logging for the Kaori app."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "kaori.log"

    root = logging.getLogger("kaori")
    root.setLevel(logging.DEBUG)

    # Rotating file handler: 5 MB max, keep 3 backups
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # Console handler: WARNING+ only (avoid cluttering uvicorn output)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    root.addHandler(ch)
