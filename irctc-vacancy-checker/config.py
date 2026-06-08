"""Default configuration constants."""

IRCTC_CHARTS_URL = "https://www.irctc.co.in/online-charts/"
DEFAULT_TIMEOUT = 30_000  # ms
MAX_RETRIES = 1

CLASS_TYPE_MAP = {
    "SL": ["SL", "Sleeper", "Sleeper Class"],
    "3A": ["3A", "Third AC", "3AC"],
    "3E": ["3E", "3AC Economy", "Third AC Economy"],
    "2A": ["2A", "Second AC", "2AC"],
    "1A": ["1A", "First AC", "1AC"],
    "CC": ["CC", "Chair Car"],
    "2S": ["2S", "Second Sitting"],
}

def normalize_class_type(user_input: str) -> str:
    """Map user-friendly class name to canonical short code."""
    upper = user_input.upper().strip()
    for canon, aliases in CLASS_TYPE_MAP.items():
        if upper == canon or upper in [a.upper() for a in aliases]:
            return canon
    raise ValueError(f"Unknown class type: {user_input}")