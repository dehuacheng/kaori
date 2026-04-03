import aiosqlite

from kaori.config import DB_PATH

SCHEMA = """
-- Raw meal data: exactly what the user provided
CREATE TABLE IF NOT EXISTS meals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    meal_type   TEXT    CHECK(meal_type IN ('breakfast','lunch','dinner','snack')),
    description TEXT,
    photo_path  TEXT,
    notes       TEXT,
    created_at  TEXT    DEFAULT (datetime('now')),
    updated_at  TEXT    DEFAULT (datetime('now'))
);

-- LLM-generated analysis results (one-to-many: supports re-analysis)
CREATE TABLE IF NOT EXISTS meal_analyses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id       INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    status        TEXT    NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('pending','analyzing','done','failed')),
    llm_backend   TEXT,
    model         TEXT,
    description   TEXT,
    items_json    TEXT,
    calories      INTEGER,
    protein_g     REAL,
    carbs_g       REAL,
    fat_g         REAL,
    confidence    TEXT    CHECK(confidence IN ('high','medium','low')),
    raw_response  TEXT,
    error_message TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    completed_at  TEXT
);

-- User manual overrides (takes precedence over LLM analysis)
CREATE TABLE IF NOT EXISTS meal_overrides (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id     INTEGER NOT NULL UNIQUE REFERENCES meals(id) ON DELETE CASCADE,
    description TEXT,
    calories    INTEGER,
    protein_g   REAL,
    carbs_g     REAL,
    fat_g       REAL,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Weight / body measurements
CREATE TABLE IF NOT EXISTS body_measurements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    weight_kg   REAL,
    notes       TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- User profile / personal info (single-user)
-- Targets are computed dynamically from per-kg rates + BMR; not stored as static numbers.
CREATE TABLE IF NOT EXISTS user_profile (
    id                    INTEGER PRIMARY KEY DEFAULT 1,
    display_name          TEXT    DEFAULT 'User',
    height_cm             REAL,
    gender                TEXT    CHECK(gender IN ('male','female','other')),
    birth_date            TEXT,
    protein_per_kg        REAL    DEFAULT 1.6,
    carbs_per_kg          REAL    DEFAULT 3.0,
    calorie_adjustment_pct REAL   DEFAULT 0,
    llm_mode              TEXT    DEFAULT 'claude_cli'
                                  CHECK(llm_mode IN ('claude_cli','claude_api','codex_cli')),
    notes                 TEXT,
    unit_body_weight      TEXT    DEFAULT 'kg' CHECK(unit_body_weight IN ('kg','lb')),
    unit_height           TEXT    DEFAULT 'cm' CHECK(unit_height IN ('cm','in')),
    unit_exercise_weight  TEXT    DEFAULT 'kg' CHECK(unit_exercise_weight IN ('kg','lb')),
    updated_at            TEXT
);

-- Versioned LLM-generated meal habit summaries (append-only, rollback-safe)
CREATE TABLE IF NOT EXISTS meal_habit_summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version      INTEGER NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1,
    summary_text TEXT    NOT NULL,
    cutoff_date  TEXT    NOT NULL,
    meal_count   INTEGER NOT NULL,
    llm_backend  TEXT,
    model        TEXT,
    raw_response TEXT,
    created_at   TEXT    DEFAULT (datetime('now'))
);

-- Exercise type catalog (standard + user-created)
CREATE TABLE IF NOT EXISTS exercise_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    category    TEXT,
    photo_path  TEXT,
    notes       TEXT,
    is_standard INTEGER NOT NULL DEFAULT 0,
    is_enabled  INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'done'
                        CHECK(status IN ('pending','done','failed')),
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Workout sessions (Apple Health compatible)
CREATE TABLE IF NOT EXISTS workouts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT    NOT NULL,
    notes            TEXT,
    activity_type    TEXT    DEFAULT 'traditionalStrengthTraining',
    duration_minutes REAL,
    calories_burned  REAL,
    summary          TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);

-- Exercises within a workout
CREATE TABLE IF NOT EXISTS workout_exercises (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id       INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_type_id INTEGER NOT NULL REFERENCES exercise_types(id),
    order_index      INTEGER NOT NULL DEFAULT 0,
    notes            TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);

-- Individual sets within an exercise
CREATE TABLE IF NOT EXISTS exercise_sets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercises(id) ON DELETE CASCADE,
    set_number          INTEGER NOT NULL,
    reps                INTEGER,
    weight_kg           REAL,
    duration_seconds    INTEGER,
    notes               TEXT
);

-- LLM-generated workout analyses (one-to-many per workout, append-only)
CREATE TABLE IF NOT EXISTS workout_analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id          INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    is_active           INTEGER NOT NULL DEFAULT 1,
    -- Metrics
    total_sets          INTEGER,
    total_reps          INTEGER,
    total_volume_kg     REAL,
    estimated_calories  REAL,
    intensity           TEXT,
    muscle_groups_json  TEXT,
    -- Trainer analysis
    summary             TEXT,
    trainer_notes       TEXT,
    progress_notes      TEXT,
    recommendations     TEXT,
    -- Audit trail
    llm_backend         TEXT,
    model               TEXT,
    raw_response        TEXT,
    error_message       TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- Timer presets (consumed by iOS client)
CREATE TABLE IF NOT EXISTS timer_presets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    rest_seconds INTEGER NOT NULL DEFAULT 60,
    work_seconds INTEGER NOT NULL DEFAULT 0,
    sets         INTEGER NOT NULL DEFAULT 3,
    notes        TEXT,
    created_at   TEXT    DEFAULT (datetime('now'))
);

-- LLM-generated daily/weekly summaries (cached, retriggerable)
CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT    NOT NULL CHECK(type IN ('daily', 'weekly')),
    date         TEXT    NOT NULL,
    summary_text TEXT    NOT NULL,
    llm_backend  TEXT,
    model        TEXT,
    raw_response TEXT,
    created_at   TEXT    DEFAULT (datetime('now'))
);

-- Financial accounts (general: brokerage, credit card, bank)
CREATE TABLE IF NOT EXISTS financial_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK(account_type IN ('brokerage','credit_card','bank')),
    institution     TEXT NOT NULL,
    sync_method     TEXT NOT NULL DEFAULT 'manual' CHECK(sync_method IN ('api','plaid','manual')),
    api_credentials TEXT,
    last_synced_at  TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Brokerage holdings (for account_type='brokerage')
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL REFERENCES financial_accounts(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    shares      REAL NOT NULL,
    cost_basis  REAL,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- LLM-extracted data from screenshots/PDFs (append-only)
CREATE TABLE IF NOT EXISTS financial_import_analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES financial_accounts(id) ON DELETE CASCADE,
    import_type     TEXT NOT NULL CHECK(import_type IN ('screenshot','pdf')),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','analyzing','done','failed')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    file_path       TEXT,
    extracted_json  TEXT,
    llm_backend     TEXT,
    model           TEXT,
    raw_response    TEXT,
    error_message   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);

-- Daily portfolio snapshots (for brokerage accounts)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    account_id  INTEGER REFERENCES financial_accounts(id) ON DELETE CASCADE,
    total_value     REAL NOT NULL,
    total_cost      REAL,
    day_change      REAL,
    day_change_pct  REAL,
    holdings_json   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Stock price cache
CREATE TABLE IF NOT EXISTS stock_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    price           REAL NOT NULL,
    previous_close  REAL,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    source          TEXT DEFAULT 'yfinance'
);

CREATE INDEX IF NOT EXISTS idx_financial_accounts_type ON financial_accounts(account_type);
CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_account ON portfolio_holdings(account_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_snapshots_unique ON portfolio_snapshots(date, account_id);
CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_summaries_type_date ON summaries(type, date DESC);
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);
CREATE INDEX IF NOT EXISTS idx_meal_analyses_meal_id ON meal_analyses(meal_id);
CREATE INDEX IF NOT EXISTS idx_meal_analyses_status ON meal_analyses(status);
CREATE INDEX IF NOT EXISTS idx_body_date ON body_measurements(date);
CREATE INDEX IF NOT EXISTS idx_habit_summary_active ON meal_habit_summaries(is_active, version DESC);
CREATE INDEX IF NOT EXISTS idx_exercise_types_category ON exercise_types(category);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);
CREATE INDEX IF NOT EXISTS idx_workout_exercises_workout ON workout_exercises(workout_id);
CREATE INDEX IF NOT EXISTS idx_exercise_sets_exercise ON exercise_sets(workout_exercise_id);
CREATE INDEX IF NOT EXISTS idx_workout_analyses_workout ON workout_analyses(workout_id, is_active);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


_PROFILE_MIGRATIONS = [
    ("height_cm", "REAL"),
    ("gender", "TEXT"),
    ("birth_date", "TEXT"),
    ("protein_per_kg", "REAL DEFAULT 1.6"),
    ("carbs_per_kg", "REAL DEFAULT 3.0"),
    ("calorie_adjustment_pct", "REAL DEFAULT 0"),
    ("notes", "TEXT"),
    ("unit_body_weight", "TEXT DEFAULT 'kg'"),
    ("unit_height", "TEXT DEFAULT 'cm'"),
    ("unit_exercise_weight", "TEXT DEFAULT 'kg'"),
]


async def _migrate_profile(db: aiosqlite.Connection):
    """Add any missing columns to user_profile for existing databases."""
    cursor = await db.execute("PRAGMA table_info(user_profile)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _PROFILE_MIGRATIONS:
        if col not in existing:
            await db.execute(f"ALTER TABLE user_profile ADD COLUMN {col} {col_type}")


async def _migrate_meal_analyses(db: aiosqlite.Connection):
    """Add is_active column and backfill so the latest analysis per meal is active."""
    cursor = await db.execute("PRAGMA table_info(meal_analyses)")
    existing = {row[1] for row in await cursor.fetchall()}
    if "is_active" not in existing:
        await db.execute(
            "ALTER TABLE meal_analyses ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0"
        )
        # Backfill: mark the latest analysis per meal as active
        await db.execute(
            "UPDATE meal_analyses SET is_active = 1 "
            "WHERE id IN (SELECT MAX(id) FROM meal_analyses GROUP BY meal_id)"
        )
    # Ensure index exists (safe to run every time)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_meal_analyses_active "
        "ON meal_analyses(meal_id, is_active)"
    )


async def _migrate_body_measurements(db: aiosqlite.Connection):
    """Drop unique constraint on date if it exists (allow multiple entries per day)."""
    cursor = await db.execute("PRAGMA index_list(body_measurements)")
    for row in await cursor.fetchall():
        idx_name = row[1]
        unique = row[2]
        if unique:
            ci = await db.execute(f"PRAGMA index_info({idx_name})")
            cols = [r[2] for r in await ci.fetchall()]
            if cols == ["date"]:
                await db.execute(f"DROP INDEX IF EXISTS {idx_name}")


async def _migrate_exercise_types(db: aiosqlite.Connection):
    """Add is_enabled and status columns to exercise_types for existing databases."""
    cursor = await db.execute("PRAGMA table_info(exercise_types)")
    existing = {row[1] for row in await cursor.fetchall()}
    if "is_enabled" not in existing:
        await db.execute(
            "ALTER TABLE exercise_types ADD COLUMN is_enabled INTEGER NOT NULL DEFAULT 0"
        )
    if "status" not in existing:
        await db.execute(
            "ALTER TABLE exercise_types ADD COLUMN status TEXT NOT NULL DEFAULT 'done'"
        )


_WORKOUT_MIGRATIONS = [
    ("activity_type", "TEXT DEFAULT 'traditionalStrengthTraining'"),
    ("duration_minutes", "REAL"),
    ("calories_burned", "REAL"),
    ("summary", "TEXT"),
]


async def _migrate_workouts(db: aiosqlite.Connection):
    """Add Apple Health compatible columns to workouts for existing databases."""
    cursor = await db.execute("PRAGMA table_info(workouts)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _WORKOUT_MIGRATIONS:
        if col not in existing:
            await db.execute(f"ALTER TABLE workouts ADD COLUMN {col} {col_type}")


async def _migrate_llm_mode_check(db: aiosqlite.Connection):
    """Widen the llm_mode CHECK constraint to include 'codex_cli' for existing DBs."""
    cursor = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_profile'"
    )
    row = await cursor.fetchone()
    if not row:
        return
    create_sql = row[0]
    if "'codex_cli'" in create_sql:
        return  # already updated

    # Recreate table with updated CHECK (safe — single-row table)
    await db.execute("""
        CREATE TABLE _user_profile_new (
            id                     INTEGER PRIMARY KEY DEFAULT 1,
            display_name           TEXT    DEFAULT 'User',
            height_cm              REAL,
            gender                 TEXT    CHECK(gender IN ('male','female','other')),
            birth_date             TEXT,
            protein_per_kg         REAL    DEFAULT 1.6,
            carbs_per_kg           REAL    DEFAULT 3.0,
            calorie_adjustment_pct REAL    DEFAULT 0,
            llm_mode               TEXT    DEFAULT 'claude_cli'
                                          CHECK(llm_mode IN ('claude_cli','claude_api','codex_cli')),
            notes                  TEXT,
            unit_body_weight       TEXT    DEFAULT 'kg' CHECK(unit_body_weight IN ('kg','lb')),
            unit_height            TEXT    DEFAULT 'cm' CHECK(unit_height IN ('cm','in')),
            unit_exercise_weight   TEXT    DEFAULT 'kg' CHECK(unit_exercise_weight IN ('kg','lb')),
            updated_at             TEXT
        )
    """)
    await db.execute("""
        INSERT INTO _user_profile_new
            (id, display_name, height_cm, gender, birth_date,
             protein_per_kg, carbs_per_kg, calorie_adjustment_pct,
             llm_mode, notes, unit_body_weight, unit_height,
             unit_exercise_weight, updated_at)
        SELECT id, display_name, height_cm, gender, birth_date,
               protein_per_kg, carbs_per_kg, calorie_adjustment_pct,
               llm_mode, notes,
               COALESCE(unit_body_weight, 'kg'),
               COALESCE(unit_height, 'cm'),
               COALESCE(unit_exercise_weight, 'kg'),
               updated_at
        FROM user_profile
    """)
    await db.execute("DROP TABLE user_profile")
    await db.execute("ALTER TABLE _user_profile_new RENAME TO user_profile")


_STANDARD_EXERCISE_TYPES = [
    # chest
    ("Bench Press", "chest"),
    ("Incline Bench Press", "chest"),
    ("Dumbbell Fly", "chest"),
    ("Cable Crossover", "chest"),
    ("Push-Up", "chest"),
    # back
    ("Deadlift", "back"),
    ("Barbell Row", "back"),
    ("Lat Pulldown", "back"),
    ("Seated Cable Row", "back"),
    ("Pull-Up", "back"),
    # legs
    ("Squat", "legs"),
    ("Leg Press", "legs"),
    ("Leg Curl", "legs"),
    ("Leg Extension", "legs"),
    ("Calf Raise", "legs"),
    ("Romanian Deadlift", "legs"),
    ("Lunge", "legs"),
    # shoulders
    ("Overhead Press", "shoulders"),
    ("Lateral Raise", "shoulders"),
    ("Face Pull", "shoulders"),
    ("Rear Delt Fly", "shoulders"),
    # arms
    ("Bicep Curl", "arms"),
    ("Tricep Pushdown", "arms"),
    ("Hammer Curl", "arms"),
    ("Skull Crusher", "arms"),
    # core
    ("Plank", "core"),
    ("Ab Crunch", "core"),
    ("Russian Twist", "core"),
    ("Hanging Leg Raise", "core"),
]


async def _seed_exercise_types(db: aiosqlite.Connection):
    """Seed standard exercise types if table is empty."""
    cursor = await db.execute("SELECT COUNT(*) FROM exercise_types")
    count = (await cursor.fetchone())[0]
    if count > 0:
        return
    await db.executemany(
        "INSERT INTO exercise_types (name, category, is_standard) VALUES (?, ?, 1)",
        _STANDARD_EXERCISE_TYPES,
    )


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await _migrate_profile(db)
        await _migrate_meal_analyses(db)
        await _migrate_body_measurements(db)
        await _migrate_workouts(db)
        await _migrate_exercise_types(db)
        await _migrate_llm_mode_check(db)
        # Seed default profile if empty
        cursor = await db.execute("SELECT COUNT(*) FROM user_profile")
        row = await cursor.fetchone()
        if row[0] == 0:
            await db.execute(
                "INSERT INTO user_profile (id) VALUES (1)"
            )
        await _seed_exercise_types(db)
        await db.commit()
    finally:
        await db.close()


def fork_to_test():
    """Copy the real database and photos to the test location.

    Run this *before* starting the app in test mode so that the test DB
    starts as a snapshot of real data.  Safe to call multiple times —
    overwrites any existing test DB.
    """
    import shutil
    from kaori.config import DATA_DIR

    real_db = DATA_DIR / "kaori.db"
    test_db = DATA_DIR / "kaori_test.db"
    real_photos = DATA_DIR / "photos"
    test_photos = DATA_DIR / "photos_test"

    if not real_db.exists():
        raise FileNotFoundError(f"Real database not found: {real_db}")

    # Copy database (overwrites existing test DB)
    shutil.copy2(real_db, test_db)
    # Also copy WAL/SHM files if present
    for suffix in ("-wal", "-shm"):
        wal = real_db.parent / (real_db.name + suffix)
        if wal.exists():
            shutil.copy2(wal, test_db.parent / (test_db.name + suffix))

    # Copy photos directory
    if real_photos.exists():
        if test_photos.exists():
            shutil.rmtree(test_photos)
        shutil.copytree(real_photos, test_photos)

    print(f"Forked real data -> test data")
    print(f"  DB:     {test_db}")
    print(f"  Photos: {test_photos}")
