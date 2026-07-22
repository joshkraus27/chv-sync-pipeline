"""
Yodel category → iOS EventCategory mapping for the Connect Happy Valley events sync.

Why this exists (the same contract that drives config/categories.py)
--------------------------------------------------------------------
The iOS `Event` model decodes `category` as a *non-optional* `EventCategory`
enum whose only valid raw values are:
    sports | music | family | food_beverage | move_explore | other
and the Events (Tonight) tab decodes the whole result set all-or-nothing — a
single row with an unknown category breaks the entire tab. So every synced row
MUST carry one of those six values. Yodel emits ~25 free-form category names,
so we map them here and default anything unrecognized to `other`.

Mapping philosophy (signed off with Josh)
-----------------------------------------
Bias visitor-facing culture/community categories toward the most discoverable
bucket rather than burying them in `other`:
  - Arts / Film / Clubs → `music` (the app's "Music & Entertainment" bucket)
  - Festivals/Fairs / Seasonal / Kids & Family → `family`
  - Markets → `food_beverage` (food/drink visitor draws)
  - Health & Fitness / Parks & Rec / Outdoors / Travel / History & Museums
    → `move_explore`
`other` is reserved for genuinely bucket-less categories (Classes/Workshops,
Hobbies, Science & Tech, etc.).

Multi-category events: an event can carry several categories. We pick the FIRST
that maps to a real (non-`other`) bucket for better discoverability, and only
fall back to `other` when none of its categories map — see
`event_category_for_names()`.
"""

# The complete, authoritative set of raw values the iOS EventCategory enum
# accepts (Models/Event.swift). Anything else breaks the Tonight tab decode.
VALID_EVENT_CATEGORIES = {
    "sports", "music", "family", "food_beverage", "move_explore", "other",
}

DEFAULT_EVENT_CATEGORY = "other"

# Yodel category name → EventCategory raw value.
# Keys are matched case-/whitespace-insensitively (see _normalize).
CATEGORY_MAP = {
    "Music & Entertainment": "music",
    "Food & Drink": "food_beverage",
    "Arts": "music",                 # arts & entertainment — kept visible
    "Classes/Workshops": "other",
    "Health & Fitness": "move_explore",
    "Kids & Family": "family",
    "Film": "music",                 # entertainment — kept visible
    "Clubs": "music",                # nightlife/entertainment
    "Seasonal & Holiday": "family",  # community draw
    "Festivals/Fairs": "family",     # core visitor event — kept visible
    "Hobbies": "other",
    "Sports, Adult": "sports",
    "History & Museums": "move_explore",  # explore-culture
    "Science & Tech": "other",
    "Auto, Boat & Air": "other",
    "Lifestyle": "other",
    "Parks & Rec": "move_explore",
    "Markets": "food_beverage",      # food/drink visitor draws
    "Outdoors": "move_explore",
    "Causes": "other",
    "Fashion": "other",
    "Retail": "other",
    "Sports, Youth": "sports",
    "Travel": "move_explore",
    "Business": "other",
}


def _normalize(name):
    """Casefold + collapse internal whitespace for tolerant key matching."""
    if not name:
        return ""
    return " ".join(str(name).split()).casefold()


# Normalized lookup built once from CATEGORY_MAP.
_NORMALIZED_MAP = {_normalize(k): v for k, v in CATEGORY_MAP.items()}


def event_category_for_name(name):
    """Map a single Yodel category name to an EventCategory raw value.

    Returns the mapped value, or DEFAULT_EVENT_CATEGORY ('other') if the name
    isn't recognized. Never returns an invalid enum value.
    """
    return _NORMALIZED_MAP.get(_normalize(name), DEFAULT_EVENT_CATEGORY)


def event_category_for_names(names):
    """Resolve an EventCategory from an event's ordered list of category names.

    Picks the FIRST name that maps to a real (non-`other`) bucket, so a
    multi-category event surfaces under its most discoverable bucket rather
    than whatever Yodel happened to list first. Falls back to `other` only when
    none of the event's categories map to a real bucket (or it has none).
    """
    mapped_first = None
    for name in names or []:
        mapped = event_category_for_name(name)
        if mapped_first is None:
            mapped_first = mapped
        if mapped != DEFAULT_EVENT_CATEGORY:
            return mapped
    return mapped_first or DEFAULT_EVENT_CATEGORY
