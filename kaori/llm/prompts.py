MEAL_ANALYSIS_PROMPT = (
    "Analyze this meal photo. Identify each food item and estimate portions. "
    "Return a JSON object (no markdown, no code fences) with these fields:\n"
    '- "description": one-line summary of the meal\n'
    '- "items": array of identified food items with estimated portions\n'
    '- "calories": total estimated calories (integer)\n'
    '- "protein_g": total protein in grams (number)\n'
    '- "carbs_g": total carbs in grams (number)\n'
    '- "fat_g": total fat in grams (number)\n'
    '- "confidence": "high", "medium", or "low"\n'
    "Be specific about portions (e.g., '2 large eggs', '1 cup rice'). "
    "If unsure, err on the side of slightly overestimating calories. "
    "Return ONLY the JSON object, nothing else."
)

_JSON_OUTPUT_INSTRUCTIONS = (
    'Return a JSON object (no markdown, no code fences) with these fields:\n'
    '- "description": one-line summary of the meal\n'
    '- "items": array of identified food items with estimated portions\n'
    '- "calories": total estimated calories (integer)\n'
    '- "protein_g": total protein in grams (number)\n'
    '- "carbs_g": total carbs in grams (number)\n'
    '- "fat_g": total fat in grams (number)\n'
    '- "confidence": "high", "medium", or "low"\n'
    "Be specific about portions (e.g., '2 large eggs', '1 cup rice'). "
    "If unsure, err on the side of slightly overestimating calories. "
    "Return ONLY the JSON object, nothing else."
)


def build_text_analysis_prompt(context: str, description: str, notes: str | None = None) -> str:
    """Build prompt for text-only meal analysis with historical context."""
    notes_section = f"\nNotes: {notes}" if notes else ""
    return (
        "You are a nutrition estimation assistant. "
        "Use the context below to estimate this meal's nutrition.\n\n"
        f"{context}\n"
        f"## Current Meal\nDescription: {description}{notes_section}\n\n"
        "If the user references a previous meal (e.g., 'same as yesterday'), "
        "use the recent meals data to match it.\n"
        "If the user mentions a restaurant or specific dish, "
        "estimate based on typical portions.\n\n"
        f"{_JSON_OUTPUT_INSTRUCTIONS}"
    )


def build_photo_analysis_prompt(context: str, description: str | None = None,
                                notes: str | None = None) -> str:
    """Build prompt for photo-based meal analysis with historical context."""
    parts = [
        "Analyze this meal photo. Identify each food item and estimate portions.\n"
    ]
    if context:
        parts.append(f"\n{context}\n")
    if description:
        parts.append(f"\n## User Description\n{description}\n")
        parts.append(
            "\nUse the photo as the primary source, but consider the user's description "
            "and meal history for context (e.g., portion sizes, usual preparations).\n\n"
        )
    else:
        parts.append("\n")
    if notes:
        parts.append(f"## User Notes\n{notes}\n\n")
    parts.append(_JSON_OUTPUT_INSTRUCTIONS)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Daily summary (notification)
# ---------------------------------------------------------------------------

def build_daily_summary_prompt(context: str, language: str = "en") -> str:
    """Build prompt for generating a short daily health summary for a notification."""
    lang_hint = "Respond in Chinese." if language.startswith("zh") else "Respond in English."
    return (
        "Generate a brief, encouraging daily health summary for a mobile push notification. "
        "Maximum 140 characters. Be specific about today's numbers. "
        "If there's a notable streak, mention it. Be warm but concise. "
        f"{lang_hint}\n\n"
        f"{context}\n\n"
        "Return ONLY the notification text, nothing else. No quotes, no JSON, no markdown."
    )


def build_daily_detail_prompt(context: str, language: str = "en") -> str:
    """Build prompt for a concise end-of-day health report with sections."""
    lang_hint = "Respond in Chinese." if language.startswith("zh") else "Respond in English."
    return (
        "You are a personal health assistant with a warm, playful personality. "
        "Write a concise end-of-day report. "
        f"{lang_hint}\n\n"
        f"{context}\n\n"
        "FORMAT: Start with 1-2 sentences of playful commentary summarizing the day "
        "(conversational tone, can use light humor). "
        "Then use ## section headers. Keep each section to 1-3 sentences. "
        "Skip a section entirely if no relevant data.\n\n"
        "## Nutrition\nCalories and protein vs targets. Note gaps.\n\n"
        "## Activity\nWorkout summary if any.\n\n"
        "## Weight\nTrend direction, one line.\n\n"
        "## Tips\n1-2 specific tips for tomorrow.\n\n"
        "Total ~100-150 words. Use actual numbers. Use **bold** for key numbers. "
        "Return ONLY the markdown, nothing else."
    )


def build_weekly_detail_prompt(context: str, language: str = "en") -> str:
    """Build prompt for a weekly health report with playful commentary."""
    lang_hint = "Respond in Chinese." if language.startswith("zh") else "Respond in English."
    return (
        "You are a personal health assistant with a warm, playful personality. "
        "Write a weekly health report. "
        f"{lang_hint}\n\n"
        f"{context}\n\n"
        "FORMAT: Start with 1-2 sentences of playful commentary about the week "
        "(conversational, light humor welcome). "
        "Then use ## section headers. Keep each section to 2-4 sentences. "
        "Skip sections with no data.\n\n"
        "## Weight Trend\nStart/end weight, delta. One-line assessment.\n\n"
        "## Nutrition\nAvg daily calories/protein. Consistency.\n\n"
        "## Training\nWorkout count, highlights.\n\n"
        "## Plan\n2-3 specific goals for next week.\n\n"
        "Total ~150-200 words. Use actual numbers. Use **bold** for key numbers. "
        "Return ONLY the markdown, nothing else."
    )


# ---------------------------------------------------------------------------
# Exercise identification
# ---------------------------------------------------------------------------

EXERCISE_IDENTIFICATION_PROMPT = (
    "Identify the exercise or gym machine in this photo. "
    "Return a JSON object (no markdown, no code fences) with these fields:\n"
    '- "name": the common name of the exercise or machine '
    '(e.g., "Lat Pulldown", "Leg Press", "Cable Crossover")\n'
    '- "category": one of: chest, back, legs, shoulders, arms, core, cardio, full_body\n'
    '- "description": a brief one-line description of what this exercise targets\n'
    '- "confidence": "high", "medium", or "low"\n'
    "Use standard exercise names that a gym-goer would recognize. "
    "If the machine can be used for multiple exercises, identify the most common one. "
    "Return ONLY the JSON object, nothing else."
)


def build_exercise_identification_prompt(user_hint: str | None = None) -> str:
    """Build prompt for identifying a gym machine/exercise from a photo."""
    if user_hint:
        return (
            f"{EXERCISE_IDENTIFICATION_PROMPT}\n\n"
            f"The user says this is: {user_hint}"
        )
    return EXERCISE_IDENTIFICATION_PROMPT


# ---------------------------------------------------------------------------
# Workout summary
# ---------------------------------------------------------------------------

def build_workout_summary_prompt(
    workout_text: str,
    user_weight_kg: float | None = None,
    history_text: str | None = None,
) -> str:
    """Build prompt for summarizing a workout with personal trainer analysis."""
    weight_note = ""
    if user_weight_kg:
        weight_note = f"\nThe user weighs {user_weight_kg:.1f} kg. Use this for calorie estimation.\n"

    history_section = ""
    if history_text:
        history_section = (
            f"\n## Previous Workout History\n{history_text}\n"
            "Use the history above to compare progress, note improvements or regressions, "
            "and give personalized recommendations.\n"
        )

    return (
        "You are a personal trainer analyzing a client's workout. "
        "Summarize this workout, estimate calories burned, and provide coaching feedback.\n\n"
        f"## Current Workout\n{workout_text}\n"
        f"{weight_note}"
        f"{history_section}\n"
        "Return a JSON object (no markdown, no code fences) with these fields:\n"
        '- "total_sets": total number of sets performed (integer)\n'
        '- "total_reps": total number of reps across all sets (integer)\n'
        '- "total_volume_kg": total training volume in kg (sum of weight * reps for each set) (number)\n'
        '- "estimated_calories": estimated kilocalories burned during this workout (number)\n'
        '- "muscle_groups_worked": array of muscle groups targeted (e.g., ["chest", "triceps", "shoulders"])\n'
        '- "summary": a brief 1-2 sentence workout summary\n'
        '- "intensity": one of "light", "moderate", "hard", "very_hard"\n'
        '- "trainer_notes": 2-4 sentences of personal trainer observations — '
        "muscle balance, exercise selection quality, volume appropriateness, "
        "anything notable about today's session\n"
        '- "progress_notes": 2-3 sentences comparing with previous workouts — '
        "volume trends, weight progression, consistency patterns. "
        'If no history is available, note this is the first tracked session\n'
        '- "recommendations": 2-3 actionable suggestions for the next session — '
        "what to adjust, exercises to add/swap, weight progression advice\n\n"
        "Base calorie estimation on exercises, total volume, and typical energy expenditure. "
        "Be specific and actionable in your trainer feedback — avoid generic advice. "
        "Return ONLY the JSON object, nothing else."
    )


# ---------------------------------------------------------------------------
# Meal history compaction
# ---------------------------------------------------------------------------

def build_compaction_prompt(old_summary: str | None, meals_text: str) -> str:
    """Build prompt for compacting meal history into an updated summary."""
    parts = ["You are summarizing a user's meal habits for future reference.\n\n"]
    if old_summary:
        parts.append(f"## Previous Meal Habit Summary\n{old_summary}\n\n")
    parts.append(f"## Additional Meals Since Last Summary\n{meals_text}\n\n")
    parts.append(
        "Produce an updated summary of this user's meal habits, patterns, "
        "typical portions, and calorie ranges. Include:\n"
        "- Recurring meals and their typical nutrition\n"
        "- Meal timing patterns (what they eat for breakfast vs lunch vs dinner)\n"
        "- Preferred restaurants or cuisines if apparent\n"
        "- Typical daily calorie and protein ranges\n"
        "- Any notable dietary preferences or restrictions\n\n"
        "Be specific and concise. This summary will be used as context when the user "
        "logs future meals (e.g., 'same as usual breakfast').\n"
        "Return ONLY the summary text, no JSON, no markdown headers."
    )
    return "".join(parts)
