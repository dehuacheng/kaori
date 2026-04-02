from datetime import date

from kaori.storage import profile_repo, weight_repo


async def get_profile() -> dict:
    """Get profile with computed fields: age, BMR, TDEE, and dynamic targets."""
    profile = await profile_repo.get()

    # Compute age
    if profile.get("birth_date"):
        try:
            bd = date.fromisoformat(profile["birth_date"])
            today = date.today()
            profile["age"] = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        except ValueError:
            profile["age"] = None
    else:
        profile["age"] = None

    # Get latest weight for target computation
    weights = await weight_repo.get_history(1)
    latest_weight = weights[0]["weight_kg"] if weights else None
    profile["latest_weight_kg"] = latest_weight

    # Compute BMR, TDEE, and targets
    targets = compute_targets(profile, latest_weight)
    profile.update(targets)

    return profile


def compute_targets(profile: dict, weight_kg: float | None) -> dict:
    """Compute calorie/macro targets from profile + current weight.

    BMR: Mifflin-St Jeor equation (sedentary TDEE = BMR * 1.2).
    Calorie target = TDEE * (1 + calorie_adjustment_pct / 100).
    Protein/carb targets = weight * per-kg rate.
    """
    result = {
        "bmr": None,
        "estimated_tdee": None,
        "target_calories": None,
        "target_protein_g": None,
        "target_carbs_g": None,
    }

    height = profile.get("height_cm")
    age = profile.get("age")
    gender = profile.get("gender")
    adjustment = profile.get("calorie_adjustment_pct") or 0

    # Mifflin-St Jeor BMR
    if weight_kg and height and age and gender in ("male", "female"):
        if gender == "male":
            bmr = 10 * weight_kg + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight_kg + 6.25 * height - 5 * age - 161
        result["bmr"] = round(bmr)
        tdee = bmr * 1.2  # sedentary baseline
        result["estimated_tdee"] = round(tdee)
        result["target_calories"] = round(tdee * (1 + adjustment / 100))

    # Per-kg macro targets
    if weight_kg:
        protein_per_kg = profile.get("protein_per_kg") or 1.6
        carbs_per_kg = profile.get("carbs_per_kg") or 3.0
        result["target_protein_g"] = round(weight_kg * protein_per_kg)
        result["target_carbs_g"] = round(weight_kg * carbs_per_kg)

    return result


async def update_profile(**fields) -> dict:
    return await profile_repo.update(**fields)


def format_profile_context(profile: dict) -> str:
    """Format profile data as context for LLM prompts."""
    parts = []
    if profile.get("gender"):
        parts.append(f"Gender: {profile['gender']}")
    if profile.get("age") is not None:
        parts.append(f"Age: {profile['age']}")
    if profile.get("height_cm"):
        parts.append(f"Height: {profile['height_cm']}cm")
    if profile.get("latest_weight_kg"):
        parts.append(f"Current weight: {profile['latest_weight_kg']}kg")
    if profile.get("target_calories"):
        parts.append(f"Daily calorie target: {profile['target_calories']} kcal")
    if profile.get("target_protein_g"):
        parts.append(f"Daily protein target: {profile['target_protein_g']}g")
    if profile.get("target_carbs_g"):
        parts.append(f"Daily carbs target: {profile['target_carbs_g']}g")
    if profile.get("notes"):
        parts.append(f"Additional context: {profile['notes']}")
    if not parts:
        return ""
    return "## User Profile\n" + "\n".join(parts)
