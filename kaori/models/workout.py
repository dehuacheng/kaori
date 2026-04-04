from pydantic import BaseModel


# --- Exercise Types ---

class ExerciseTypeCreate(BaseModel):
    name: str
    category: str | None = None
    notes: str | None = None


class ExerciseTypeUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    notes: str | None = None


class ExerciseIdentification(BaseModel):
    name: str
    category: str
    description: str
    confidence: str  # "high", "medium", "low"


# --- Sets ---

class SetCreate(BaseModel):
    set_number: int
    reps: int | None = None
    weight_kg: float | None = None
    duration_seconds: int | None = None
    notes: str | None = None


class SetUpdate(BaseModel):
    reps: int | None = None
    weight_kg: float | None = None
    duration_seconds: int | None = None
    notes: str | None = None


# --- Workout Exercises ---

class WorkoutExerciseCreate(BaseModel):
    exercise_type_id: int
    order_index: int = 0
    notes: str | None = None
    sets: list[SetCreate] | None = None


class WorkoutExerciseUpdate(BaseModel):
    exercise_type_id: int | None = None
    order_index: int | None = None
    notes: str | None = None


# --- Workouts ---

# Apple Health activity types relevant to weight training
ACTIVITY_TYPES = [
    "traditionalStrengthTraining",
    "functionalStrengthTraining",
    "highIntensityIntervalTraining",
    "coreTraining",
    "flexibility",
    "mixedCardio",
    "running",
    "cycling",
    "swimming",
    "yoga",
    "pilates",
    "hiking",
    "crossTraining",
    "walking",
    "stairClimbing",
    "elliptical",
    "rowing",
    "dance",
    "jumpRope",
    "other",
]


class WorkoutCreate(BaseModel):
    date: str | None = None  # defaults to today
    notes: str | None = None
    activity_type: str = "traditionalStrengthTraining"
    duration_minutes: float | None = None
    calories_burned: float | None = None
    source: str = "manual"  # "manual" or "healthkit"
    exercises: list[WorkoutExerciseCreate] | None = None


class WorkoutUpdate(BaseModel):
    date: str | None = None
    notes: str | None = None
    activity_type: str | None = None
    duration_minutes: float | None = None


class WorkoutSummary(BaseModel):
    """LLM-generated workout summary with personal trainer analysis."""
    total_sets: int
    total_reps: int
    total_volume_kg: float  # sum of (weight * reps) across all sets
    estimated_calories: float
    muscle_groups_worked: list[str]
    summary: str
    intensity: str  # "light", "moderate", "hard", "very_hard"
    trainer_notes: str  # Personal trainer observations about form, balance, etc.
    progress_notes: str  # Comparison with previous workouts (or "First workout" if none)
    recommendations: str  # Actionable suggestions for next session


# --- Timer Presets ---

class TimerPresetCreate(BaseModel):
    name: str
    rest_seconds: int = 60
    work_seconds: int = 0
    sets: int = 3
    notes: str | None = None


class TimerPresetUpdate(BaseModel):
    name: str | None = None
    rest_seconds: int | None = None
    work_seconds: int | None = None
    sets: int | None = None
    notes: str | None = None
