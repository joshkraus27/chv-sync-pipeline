"""
Category whitelist + GeoDirectory→iOS type mapping for the Connect Happy Valley sync.

Filtering is by PARENT BUCKET ID; typing is by bucket default + name refinement.
----------------------------------------------------------------------------------
GeoDirectory uses a two-level hierarchy: ~28 top-level buckets (parent == 0) and
hundreds of subcategories (parent == <bucket id>). Listings are tagged with
SUBCATEGORY ids. Filtering by subcategory *name* proved unreliable — singular vs
plural ("Coffee Shop" vs "Coffee Shops"), HTML entities ("Food &amp; Beverage"),
and newly-added subcategories all slipped through. So:

1. ALLOWED_PARENT_IDS — the whitelist. A listing syncs if any of its categories
   is (or descends from) one of these visitor-facing top-level buckets. Robust
   to subcategory renames and additions.

2. type assignment is two-tier, and ALWAYS yields a valid iOS PlaceType:
     a. PARENT_ID_TO_PLACE_TYPE — a guaranteed default per allowed bucket. Every
        included listing gets a valid type from its bucket, so nothing is dropped
        at transform time for "no type mapping" (the bug that capped the first
        run at 25/3873).
     b. CATEGORY_TO_PLACE_TYPE — a *refinement* over the bucket default, matched
        via `place_type_for_category_name()` which is case-, entity-, and
        plural-insensitive. So "Coffee Shop" still resolves to `cafe` even though
        the table key is "Coffee Shops".

Why type matters at all: the iOS `Place` model decodes `type` as a *non-optional*
PlaceType enum, and the Discover fetch decodes the whole result set all-or-nothing
— a single row with a null/unknown `type` breaks the entire Discover tab. Hence
the guarantee that every synced row carries a valid type.
"""

import re

# ---------------------------------------------------------------------------
# WHITELIST — top-level GeoDirectory bucket IDs that should sync to the app.
# These are visitor-facing. Resident/utility buckets (Healthcare, Professional
# Services, Home Services, etc.) are excluded — see EXCLUDED list below.
# ---------------------------------------------------------------------------
ALLOWED_PARENT_IDS = {
    284,  # Food & Beverage (restaurants, bars, cafes, breweries)
    691,  # Attractions & Tourism (museums, galleries, landmarks)
    696,  # Entertainment & Recreation (theaters, concert venues, bowling)
    700,  # Food & Beverage Retail (butchers, cheese shops, specialty grocers)
    704,  # Lodging & Accommodation (hotels, B&Bs, cabins, campgrounds)
    706,  # Natural Features (scenic landmarks)
    707,  # Parks & Recreation (parks, trails, outdoor spaces)
    713,  # Retail & Shopping (gift shops, antique stores, bookstores)
    714,  # Sports & Recreation (golf, bowling, kayak rental)
    716,  # Travel & Tourism (tourism services)
}

# Excluded parent IDs (for documentation):
# 690 Agriculture & Farms - mostly farm services, not visitor-facing
# 692 Automotive Services - car repair, parts
# 693 Community & Social Services - charities, social work
# 694 Education - K-12 schools, adult ed (excluded per Josh's decision)
# 695 Emergency Services - police, fire, EMS
# 697 Event Services - wedding venues, catering for residents
# 698 Family Services - childcare, family help
# 699 Financial Services - banks, accountants
# 701 Government & Public Services - government offices
# 702 Healthcare & Wellness - doctors, hospitals
# 703 Home Services - plumbers, contractors
# 705 Media & Entertainment Services - print shops, media production
# 708 Personal Care & Beauty - salons, barbers
# 709 Pet Services - vets, groomers
# 710 Places of Worship - churches
# 711 Professional Services - lawyers, consultants
# 712 Real Estate & Housing - realtors, apartments
# 715 Transportation & Parking - bus stations, taxi services

# ---------------------------------------------------------------------------
# Stable id -> human name for the 28 top-level buckets. Used only for readable
# log output (the parent-bucket breakdown). Hardcoded because the top-level
# buckets are stable; subcategories below them churn.
# ---------------------------------------------------------------------------
PARENT_BUCKET_NAMES = {
    284: "Food & Beverage",
    690: "Agriculture & Farms",
    691: "Attractions & Tourism",
    692: "Automotive Services",
    693: "Community & Social Services",
    694: "Education",
    695: "Emergency Services",
    696: "Entertainment & Recreation",
    697: "Event Services",
    698: "Family Services",
    699: "Financial Services",
    700: "Food & Beverage Retail",
    701: "Government & Public Services",
    702: "Healthcare & Wellness",
    703: "Home Services",
    704: "Lodging & Accommodation",
    705: "Media & Entertainment Services",
    706: "Natural Features",
    707: "Parks & Recreation",
    708: "Personal Care & Beauty",
    709: "Pet Services",
    710: "Places of Worship",
    711: "Professional Services",
    712: "Real Estate & Housing",
    713: "Retail & Shopping",
    714: "Sports & Recreation",
    715: "Transportation & Parking",
    716: "Travel & Tourism",
}

# The complete, authoritative set of raw values the iOS PlaceType enum accepts
# (Models/Place.swift). Anything else makes the app's decode throw.
VALID_PLACE_TYPES = {
    "restaurant", "bar", "cafe", "hotel", "experience", "venue", "shop",
}

# ---------------------------------------------------------------------------
# TIER 1 (guaranteed): allowed bucket id -> default iOS PlaceType.
# Every allowed bucket MUST appear here so every included listing gets a valid
# type even when its subcategory name isn't in the refinement table below.
# ---------------------------------------------------------------------------
PARENT_ID_TO_PLACE_TYPE = {
    284: "restaurant",   # Food & Beverage — refined to cafe/bar by name where known
    700: "shop",         # Food & Beverage Retail (butchers, grocers, specialty)
    704: "hotel",        # Lodging & Accommodation
    691: "experience",   # Attractions & Tourism
    706: "experience",   # Natural Features
    707: "experience",   # Parks & Recreation
    714: "experience",   # Sports & Recreation
    716: "experience",   # Travel & Tourism
    696: "venue",        # Entertainment & Recreation
    713: "shop",         # Retail & Shopping
}

# ---------------------------------------------------------------------------
# TIER 2 (refinement): GeoDirectory subcategory name -> iOS PlaceType.
#
# This sharpens the bucket default when a subcategory name is recognized — e.g.
# a "Coffee Shop" or "Brewery" inside Food & Beverage becomes cafe/bar instead
# of the bucket's `restaurant` default. Matching is done via
# place_type_for_category_name(), which normalizes case, HTML entities, and
# singular/plural, so the historical name-mismatch bug no longer drops rows; at
# worst a name simply falls back to its bucket default.
#
# Valid iOS PlaceType raw values: restaurant | bar | cafe | hotel | experience
#                                 | venue | shop
# ---------------------------------------------------------------------------
CATEGORY_TO_PLACE_TYPE = {
    # Gather (food & drink)
    "Restaurants": "restaurant",
    "Outdoor Dining": "restaurant",     # a way of dining out -> restaurant
    "Coffee Shops": "cafe",
    "Cafes": "cafe",
    "Ice Cream Shops": "cafe",          # treat-counter, not a sit-down meal
    "Bakeries": "cafe",
    "Desserts": "cafe",
    "Bars": "bar",
    "Pubs": "bar",
    "Breweries": "bar",
    "Wineries": "bar",                  # drink-led tasting venue -> bar

    # Explore (outdoors & attractions) — all map to the "experience" bucket
    "Parks": "experience",
    "Trails": "experience",
    "Hiking": "experience",
    "State Forests": "experience",
    "State Parks": "experience",
    "Natural Features": "experience",
    "Scenic Areas": "experience",
    "Museums": "experience",
    "Historic Sites": "experience",
    "Art Galleries": "experience",
    "Attractions": "experience",
    "Tourism": "experience",
    "Landmarks": "experience",
    "Hidden Gems": "experience",

    # Stay (lodging) — all map to "hotel" (the app's only lodging type)
    "Hotels": "hotel",
    "Vacation Rentals": "hotel",
    "Bed and Breakfasts": "hotel",
    "Boutique Hotels": "hotel",
    "Resorts": "hotel",
    "Camping": "hotel",                 # overnight lodging, not a day activity
    "Campgrounds": "hotel",

    # Selective Retail -> "shop"
    "Gift Shops": "shop",
    "Souvenir Shops": "shop",
    "Local Shops": "shop",
    "Bookstores": "shop",
    "Antique Shops": "shop",
    "Art Stores": "shop",

    # Selective Sports & Recreation
    "Sports Venues": "venue",           # built spectator space -> venue
    "Recreation Centers": "experience", # an activity destination
    "Skiing": "experience",
    "Golf Courses": "experience",

    # Selective Entertainment -> "venue" (built entertainment/event spaces)
    "Theaters": "venue",
    "Cinemas": "venue",
    "Live Music": "venue",
    "Comedy Clubs": "venue",
    "Event Venues": "venue",
}


# ---------------------------------------------------------------------------
# Robust subcategory-name -> type lookup.
#
# The first sync failed because category names in the API ("Coffee Shop",
# "Food &amp; Beverage") didn't exactly equal our table keys ("Coffee Shops").
# These helpers normalize case, a few HTML entities, and singular/plural so the
# refinement table actually fires. Anything still unrecognized falls back to the
# bucket default — it is never dropped.
# ---------------------------------------------------------------------------
_ENTITY_REPLACEMENTS = (
    ("&amp;", "&"),
    ("&#038;", "&"),
    ("&#038;amp;", "&"),
    ("&#8217;", "'"),
    ("&#x27;", "'"),
    ("&#039;", "'"),
)


def _normalize_cat_name(name: str) -> str:
    """Lowercase, entity-decode, and collapse whitespace for tolerant matching."""
    if not name:
        return ""
    s = name
    for a, b in _ENTITY_REPLACEMENTS:
        s = s.replace(a, b)
    s = s.casefold().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _singular_variants(norm: str) -> set:
    """Return {name} plus a naive singular form, to bridge plural/singular drift."""
    variants = {norm}
    if norm.endswith("ies") and len(norm) > 3:
        variants.add(norm[:-3] + "y")      # bakeries -> bakery, wineries -> winery
    elif norm.endswith("s") and len(norm) > 1:
        variants.add(norm[:-1])            # coffee shops -> coffee shop, hotels -> hotel
    return variants


# Build a normalized index from the refinement table. Each table key contributes
# both its normalized form and a singularized form, so an incoming name in either
# number resolves. First write wins on the rare collision (documented).
_NAME_TYPE_INDEX = {}
for _name, _ptype in CATEGORY_TO_PLACE_TYPE.items():
    for _variant in _singular_variants(_normalize_cat_name(_name)):
        _NAME_TYPE_INDEX.setdefault(_variant, _ptype)


def place_type_for_category_name(name):
    """Resolve an iOS PlaceType from a subcategory name, or None if unrecognized.

    Tolerant of case, the common HTML entities, and singular/plural. Callers use
    this as a refinement over the bucket default — a None just means "use the
    bucket default", never "drop the row".
    """
    norm = _normalize_cat_name(name)
    if not norm:
        return None
    for variant in _singular_variants(norm):
        ptype = _NAME_TYPE_INDEX.get(variant)
        if ptype is not None:
            return ptype
    return None


# ---------------------------------------------------------------------------
# Excluded buckets (for documentation)
# ---------------------------------------------------------------------------
EXCLUDED_CATEGORIES_NOTE = """
Excluded top-level buckets (resident/utility "Live Here" categories, not
visitor-facing): Agriculture & Farms, Automotive Services, Community & Social
Services, Education, Emergency Services, Event Services, Family Services,
Financial Services, Government & Public Services, Healthcare & Wellness, Home
Services, Media & Entertainment Services, Personal Care & Beauty, Pet Services,
Places of Worship, Professional Services, Real Estate & Housing, Transportation
& Parking.
"""
