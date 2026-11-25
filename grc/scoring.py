"""5x5 risk scoring methodology (Likelihood x Impact)."""

LIKELIHOOD = {1: "Rare", 2: "Unlikely", 3: "Possible", 4: "Likely", 5: "Almost certain"}
IMPACT = {1: "Negligible", 2: "Minor", 3: "Moderate", 4: "Major", 5: "Severe"}
TREATMENTS = ["Mitigate", "Accept", "Transfer", "Avoid"]

# Risk appetite: anything above this residual score needs management sign-off
RISK_APPETITE = 6


def clamp(value, lo=1, hi=5) -> int:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return 3
    return max(lo, min(hi, v))


def score(likelihood: int, impact: int) -> int:
    return clamp(likelihood) * clamp(impact)


def rating(s: int) -> str:
    if s >= 15:
        return "Critical"
    if s >= 10:
        return "High"
    if s >= 5:
        return "Medium"
    return "Low"


# AFEP palette (see afep_theme.py)
RATING_COLOURS = {"Critical": "#FF7B6B", "High": "#F2A65A", "Medium": "#E8D48B", "Low": "#7FC8A0"}
