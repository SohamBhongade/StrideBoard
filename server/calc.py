"""Pure game calculations: no database, no Flask.

Each function takes plain values and returns plain values, so each one is easy
to test and easy to explain.
"""
import math
import re
from datetime import date, timedelta

import config

# Arabic-Indic (٠-٩) and Persian (۰-۹) digits, plus the Arabic decimal (٫)
# and thousands (٬) separators, turned into normal characters.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")


# ---------- dates and weeks ----------

def to_date(value):
    """Accept a date or a 'YYYY-MM-DD' string and return a date."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValueError("date must be a real date written as YYYY-MM-DD")


def week_bounds(day):
    """Monday and Sunday of the week that contains `day`."""
    d = to_date(day)
    monday = d - timedelta(days=d.weekday())  # weekday(): Monday = 0
    return monday, monday + timedelta(days=6)


def parse_date(value, today, max_days_back=config.MAX_DAYS_BACK):
    """Check a date from a phone or a form. Empty means today.

    Returns 'YYYY-MM-DD'. Rejects future dates and dates more than
    `max_days_back` days ago (None turns that check off).
    """
    today = to_date(today)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return today.isoformat()
    if not isinstance(value, str):
        raise ValueError("date must be text written as YYYY-MM-DD")
    d = to_date(value.translate(_DIGITS))
    if d > today:
        raise ValueError("date cannot be in the future")
    if max_days_back is not None and (today - d).days > max_days_back:
        raise ValueError(f"date is more than {max_days_back} days ago")
    return d.isoformat()


# ---------- numbers ----------

def parse_steps(value):
    """Turn a step count from a phone or form into a whole number.

    Accepts 8423, 8423.6 (rounded), "9,500.0", " 8423 " and Arabic digits "٨٤٢٣".
    Raises ValueError for anything else, negatives, or more than 100,000.
    """
    if value is None:
        raise ValueError("steps is required")
    if isinstance(value, bool):  # True/False are not step counts
        raise ValueError("steps must be a number")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().translate(_DIGITS).replace(",", "").replace(" ", "")
        if not re.fullmatch(r"-?\d+(\.\d+)?", text):
            raise ValueError("steps must be a number")
        number = float(text)
    else:
        raise ValueError("steps must be a number")

    if math.isnan(number) or math.isinf(number):
        raise ValueError("steps must be a number")
    if number < 0:
        raise ValueError("steps cannot be negative")
    steps = math.floor(number + 0.5)  # round half up: 8423.5 -> 8424
    if steps > config.MAX_DAILY_STEPS:
        raise ValueError(f"steps cannot be more than {config.MAX_DAILY_STEPS:,} in a day")
    return steps


def parse_int(value, name, low, high):
    """Whole number between low and high (inclusive), e.g. a mood of 1-5."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a whole number")
    if isinstance(value, str):
        value = value.strip().translate(_DIGITS)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number") from None
    if isinstance(value, float) and value != number:
        raise ValueError(f"{name} must be a whole number")
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low:,} and {high:,}")
    return number


def round_to_nearest(value, step):
    """Round half up to the nearest multiple of step: 9,124 -> 9,000 (step 250)."""
    return int(math.floor(value / step + 0.5)) * step


def average(values):
    """Mean of a list, or None for an empty list."""
    values = list(values)
    return sum(values) / len(values) if values else None


def percent_change(new, old):
    """Whole-number % change from old to new, or None if old is 0."""
    if not old:
        return None
    return round((new - old) / old * 100)


def goal_percent(steps, goal):
    """Steps as a whole-number % of the goal (can go above 100)."""
    return round(steps / goal * 100) if goal else 0


def steps_to_km(steps):
    """School distance challenge: 1 step = 0.7 m. Rounded to 0.1 km."""
    return round(steps * config.KM_PER_STEP, 1)


# ---------- tiers, streaks, goals ----------

def tier_for(weekly_total):
    """Name of the tier for a weekly total, e.g. 41,230 -> 'Silver'."""
    name = config.TIERS[0][0]
    for tier_name, minimum in config.TIERS:
        if weekly_total >= minimum:
            name = tier_name
    return name


def next_tier(weekly_total):
    """(next tier name, steps still needed). (None, 0) at the top tier."""
    for tier_name, minimum in config.TIERS:
        if weekly_total < minimum:
            return tier_name, minimum - weekly_total
    return None, 0


def streak(goal_met_dates, today):
    """Days in a row the goal was met, ending today or yesterday.

    goal_met_dates: dates (or 'YYYY-MM-DD' strings) when steps >= goal.
    If today's goal is not met yet, the streak still counts up to yesterday.
    """
    met = {to_date(d) for d in goal_met_dates}
    day = to_date(today)
    if day not in met:
        day -= timedelta(days=1)
    count = 0
    while day in met:
        count += 1
        day -= timedelta(days=1)
    return count


def adaptive_goal(recent_steps):
    """New daily goal from the user's last 14 days of steps, or None if fewer.

    Average x 1.10, rounded to the nearest 250, kept between 3,000 and 15,000.
    """
    recent = list(recent_steps)[: config.ADAPTIVE_MIN_DAYS]
    if len(recent) < config.ADAPTIVE_MIN_DAYS:
        return None
    goal = round_to_nearest(average(recent) * config.ADAPTIVE_FACTOR, config.ADAPTIVE_ROUND_TO)
    return max(config.ADAPTIVE_GOAL_MIN, min(config.ADAPTIVE_GOAL_MAX, goal))


# ---------- badges ----------

def badge_keys(entry_count, day_steps, streak_days, days_logged_in_week,
               week_total, last_week_total):
    """Which badge rules are met right now (a set of badge keys).

    The database layer only saves the ones the user does not have yet.
    """
    earned = set()
    if entry_count >= 1:
        earned.add("first_log")
    if day_steps >= config.TEN_K_STEPS:
        earned.add("ten_k")
    if streak_days >= 3:
        earned.add("streak_3")
    if streak_days >= 7:
        earned.add("streak_7")
    if days_logged_in_week >= config.CONSISTENT_DAYS:
        earned.add("consistent")
    if (last_week_total >= config.COMEBACK_MIN_LAST_WEEK
            and week_total >= last_week_total * config.COMEBACK_FACTOR):
        earned.add("comeback")
    if tier_for(week_total) == "Platinum":
        earned.add("platinum")
    return earned


# ---------- Weekly Wrap-Up sentence ----------

def insight_sentence(this_week, last_week, mood_goal_days, mood_other_days):
    """One plain sentence for the Weekly Wrap-Up.

    mood_goal_days / mood_other_days: mood scores (1-5) on days the goal was /
    was not met. The mood sentence is used only with 3+ days in each group.
    `last_week` should cover the same days of last week as `this_week`.
    """
    need = config.MIN_MOOD_DAYS_FOR_INSIGHT
    if len(mood_goal_days) >= need and len(mood_other_days) >= need:
        on = average(mood_goal_days)
        off = average(mood_other_days)
        return (f"On days you hit your goal, your average mood was {on:.1f} "
                f"vs {off:.1f} on other days.")

    change = percent_change(this_week, last_week)
    if change is not None:
        if change >= 5:
            return f"You walked {change}% more than last week. Nice."
        if change <= -5:
            return (f"You walked {-change}% less than last week. "
                    f"A short walk at break time can help you bounce back.")
        return "You walked about the same as last week. Steady!"
    if this_week > 0:
        return "Great start! Next week you will see how you compare."
    return "No steps yet this week. A 10-minute walk is a great start."
