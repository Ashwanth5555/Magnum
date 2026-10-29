"""Stores, neighborhoods and the product catalogue - NY / CT metro, USD.

Market note: Uber Eats does not operate in India (it exited in January 2020,
selling its India business to Zomato). The US is its home market, and US grocery
and convenience delivery is where a Magnum ice cream SKU actually lives on the
platform. The POC is therefore set across the New York City metro and southern
Connecticut, with US delivery menus, USD pricing, ZIP codes and Fahrenheit.

Ten store catchments: six in New York, four in Connecticut. The two-state split
is deliberate - dense-urban NY and suburban CT behave differently on basket
size, pack format and delivery pressure, which gives the demand desk a real
comparison rather than ten copies of one pattern.

Everything here is synthetic. No real Magnum, Uber or retailer data is used.
"""
from __future__ import annotations

from typing import Dict, List, Optional

REGION = "NY / CT metro"
STATES = ["NY", "CT"]

# --------------------------------------------------------------------------
# Neighborhoods and stores
# --------------------------------------------------------------------------
# affluence      drives basket value and premium-format mix
# activity_base  drives short-horizon order pressure and delivery load
# density        urban / suburban - shifts pack size and group-occasion priors

AREAS: List[Dict] = [
    {"area_id": "upper-east-side", "name": "Upper East Side", "state": "NY", "city": "New York", "zip": "10021", "lat": 40.7736, "lon": -73.9566, "affluence": 0.90, "activity_base": 0.84, "density": "urban"},
    {"area_id": "chelsea", "name": "Chelsea", "state": "NY", "city": "New York", "zip": "10011", "lat": 40.7465, "lon": -74.0014, "affluence": 0.86, "activity_base": 0.88, "density": "urban"},
    {"area_id": "williamsburg", "name": "Williamsburg", "state": "NY", "city": "Brooklyn", "zip": "11211", "lat": 40.7081, "lon": -73.9571, "affluence": 0.78, "activity_base": 0.86, "density": "urban"},
    {"area_id": "astoria", "name": "Astoria", "state": "NY", "city": "Queens", "zip": "11106", "lat": 40.7644, "lon": -73.9235, "affluence": 0.66, "activity_base": 0.79, "density": "urban"},
    {"area_id": "park-slope", "name": "Park Slope", "state": "NY", "city": "Brooklyn", "zip": "11215", "lat": 40.6710, "lon": -73.9814, "affluence": 0.80, "activity_base": 0.72, "density": "urban"},
    {"area_id": "white-plains", "name": "White Plains", "state": "NY", "city": "White Plains", "zip": "10601", "lat": 41.0340, "lon": -73.7629, "affluence": 0.75, "activity_base": 0.62, "density": "suburban"},
    {"area_id": "stamford", "name": "Stamford", "state": "CT", "city": "Stamford", "zip": "06901", "lat": 41.0534, "lon": -73.5387, "affluence": 0.77, "activity_base": 0.66, "density": "suburban"},
    {"area_id": "greenwich", "name": "Greenwich", "state": "CT", "city": "Greenwich", "zip": "06830", "lat": 41.0262, "lon": -73.6282, "affluence": 0.93, "activity_base": 0.58, "density": "suburban"},
    {"area_id": "norwalk", "name": "Norwalk", "state": "CT", "city": "Norwalk", "zip": "06851", "lat": 41.1177, "lon": -73.4082, "affluence": 0.63, "activity_base": 0.60, "density": "suburban"},
    {"area_id": "new-haven", "name": "New Haven", "state": "CT", "city": "New Haven", "zip": "06510", "lat": 41.3083, "lon": -72.9279, "affluence": 0.58, "activity_base": 0.68, "density": "urban"},
]

STORES: List[Dict] = [
    {
        "store_id": "ST-%02d" % (i + 1),
        "name": "%s Market" % a["name"],
        "area_id": a["area_id"],
        "area_name": a["name"],
        "state": a["state"],
        "city": a["city"],
        "zip": a["zip"],
        "latitude": a["lat"],
        "longitude": a["lon"],
        "density": a["density"],
        "opens_hour": 8,
        "closes_hour": 24,
        "fulfilment_capacity": 45 + int(round(a["activity_base"] * 50)),
        "freezer_slots": 200 + int(round(a["affluence"] * 140)),
        "transfer_lead_minutes": 75 if a["density"] == "urban" else 105,
    }
    for i, a in enumerate(AREAS)
]

STORE_BY_AREA: Dict[str, Dict] = {s["area_id"]: s for s in STORES}
STORE_BY_ID: Dict[str, Dict] = {s["store_id"]: s for s in STORES}
AREA_BY_ID: Dict[str, Dict] = {a["area_id"]: a for a in AREAS}
STORES_BY_STATE: Dict[str, List[Dict]] = {
    st: [s for s in STORES if s["state"] == st] for st in STATES
}


# --------------------------------------------------------------------------
# Products - US delivery / convenience assortment, USD
# --------------------------------------------------------------------------

def _p(sku_id, name, category, subcategory, price, margin_rate, units_in_pack=1,
       flavour=None, pack_size="single", portion=0.0, shareable=False,
       tags=(), terms=(), brand="Magnum", size_label="", spice=0.0, richness=0.0,
       pairs=()):
    """
    `spice`, `richness` and `pairs` describe what a dish does to the dessert
    that follows it, and they are inputs to the generator, not decorations.

    spice     0-1. Capsaicin heat drives people to a cold, milder, creamier
              dessert - the cooling response is why a wings basket behaves
              differently from a pizza basket of the same size.
    richness  0-1. How heavy the dish already is. A rich plate suppresses
              dessert volume; a light one leaves room for it.
    pairs     Flavours this dish tilts toward, strongest first. Read as an
              affinity, never as a rule - it moves a probability, and a
              household's own history still outranks it.
    """
    return {
        "sku_id": sku_id,
        "name": name,
        "brand": brand,
        "category": category,
        "subcategory": subcategory,
        "flavour": flavour,
        "pack_size": pack_size,
        "size_label": size_label,
        "units_in_pack": units_in_pack,
        "price": float(price),
        "margin_rate": float(margin_rate),
        "unit_margin": round(price * margin_rate, 2),
        "portion_size": float(portion),
        "is_shareable": bool(shareable),
        "tags": list(tags),
        "search_terms": list(terms),
        "spice": float(spice),
        "richness": float(richness),
        "pairs": list(pairs),
    }


MAGNUM_PRODUCTS: List[Dict] = [
    _p("MAG-CLS-1", "Magnum Classic Milk Chocolate Bar", "magnum", "single", 3.49, 0.44, 1,
       "classic", "single", size_label="3 fl oz bar",
       tags=("ice cream", "chocolate", "premium", "frozen", "single serve"),
       terms=("magnum", "classic", "milk chocolate", "ice cream", "bar", "dessert", "frozen")),
    _p("MAG-ALM-1", "Magnum Almond Bar", "magnum", "single", 3.79, 0.45, 1,
       "almond", "single", size_label="3 fl oz bar",
       tags=("ice cream", "chocolate", "almond", "premium", "frozen", "single serve"),
       terms=("magnum", "almond", "nut", "ice cream", "chocolate", "bar", "dessert")),
    _p("MAG-CAR-1", "Magnum Double Caramel Bar", "magnum", "single", 3.99, 0.46, 1,
       "caramel", "single", size_label="3.38 fl oz bar",
       tags=("ice cream", "caramel", "chocolate", "premium", "frozen", "single serve"),
       terms=("magnum", "caramel", "double", "ice cream", "chocolate", "bar", "dessert")),
    _p("MAG-WHT-1", "Magnum White Chocolate Bar", "magnum", "single", 3.79, 0.45, 1,
       "white", "single", size_label="3 fl oz bar",
       tags=("ice cream", "white chocolate", "premium", "frozen", "single serve"),
       terms=("magnum", "white chocolate", "ice cream", "bar", "dessert")),
    _p("MAG-ALM-3", "Magnum Almond Bars, 3 Count", "magnum", "multipack", 9.99, 0.40, 3,
       "almond", "3-count", shareable=True, size_label="3 ct box",
       tags=("ice cream", "multipack", "share", "frozen", "value", "box"),
       terms=("magnum", "almond", "3 count", "box", "multipack", "pack", "ice cream", "share")),
    _p("MAG-MIN-6", "Magnum Mini Classic Bars, 6 Count", "magnum", "multipack", 11.49, 0.38, 6,
       "classic", "6-count", shareable=True, size_label="6 ct box",
       tags=("ice cream", "multipack", "family", "share", "frozen", "value", "box", "mini"),
       terms=("magnum", "mini", "6 count", "box", "multipack", "pack", "family", "ice cream", "share")),
    # A box exists in every flavour on purpose. With packs in only two flavours,
    # every group order was forced onto those two, and any measurement of "which
    # dessert follows this dish" would really have been measuring "how many
    # people are eating" wearing a flavour label. Format and taste have to be
    # able to vary independently or the pairing evidence is worthless.
    _p("MAG-CAR-3", "Magnum Double Caramel Bars, 3 Count", "magnum", "multipack", 10.99, 0.41, 3,
       "caramel", "3-count", shareable=True, size_label="3 ct box",
       tags=("ice cream", "caramel", "multipack", "share", "frozen", "value", "box"),
       terms=("magnum", "caramel", "double", "3 count", "box", "multipack", "pack", "share")),
    _p("MAG-WHT-3", "Magnum White Chocolate Bars, 3 Count", "magnum", "multipack", 9.99, 0.40, 3,
       "white", "3-count", shareable=True, size_label="3 ct box",
       tags=("ice cream", "white chocolate", "multipack", "share", "frozen", "value", "box"),
       terms=("magnum", "white chocolate", "3 count", "box", "multipack", "pack", "share")),
]

COMPANION_PRODUCTS: List[Dict] = [
    # Meals (6) - portion_size counts people fed
    _p("MEA-PIZ-L", "Large Cheese Pizza", "meal", "pizza", 21.99, 0.33, 1, None, "single",
       portion=2.8, shareable=True, brand="Vinnie's Pizzeria", size_label="18 in, 8 slices",
       tags=("meal", "pizza", "share", "dinner", "classic"),
       terms=("pizza", "cheese", "pie", "large", "meal", "dinner", "slice"),
       spice=0.05, richness=0.6, pairs=('classic', 'almond')),
    _p("MEA-PIZ-P", "Large Pepperoni Pizza", "meal", "pizza", 24.99, 0.32, 1, None, "single",
       portion=2.8, shareable=True, brand="Vinnie's Pizzeria", size_label="18 in, 8 slices",
       tags=("meal", "pizza", "share", "dinner"),
       terms=("pizza", "pepperoni", "pie", "large", "meal", "dinner"),
       spice=0.22, richness=0.7, pairs=('classic', 'almond')),
    _p("MEA-HAL-1", "Chicken Over Rice Platter", "meal", "platter", 11.49, 0.37, 1, None, "single",
       portion=1.2, brand="53rd St. Halal", size_label="large platter, white sauce",
       tags=("meal", "halal", "platter", "solo", "late night"),
       terms=("chicken over rice", "halal", "platter", "gyro", "meal", "rice"),
       spice=0.62, richness=0.55, pairs=('white', 'caramel')),
    _p("MEA-HER-I", "Italian Hero", "meal", "sandwich", 13.49, 0.36, 1, None, "single",
       portion=1.1, brand="Court St. Deli", size_label="12 in",
       tags=("meal", "sandwich", "deli", "solo"),
       terms=("hero", "italian", "sub", "sandwich", "deli", "meal", "hoagie"),
       spice=0.18, richness=0.65, pairs=('caramel', 'classic')),
    _p("MEA-BUR-B", "Bacon Cheeseburger", "meal", "burger", 13.99, 0.36, 1, None, "single",
       portion=1.0, brand="Court St. Deli", size_label="8 oz patty",
       tags=("meal", "burger", "solo"),
       terms=("burger", "cheeseburger", "bacon", "meal", "sandwich"),
       spice=0.1, richness=0.82, pairs=('caramel', 'white')),
    _p("MEA-WNG-8", "Buffalo Wings, 8 Piece", "meal", "wings", 14.99, 0.35, 1, None, "single",
       portion=1.6, shareable=True, brand="Court St. Deli", size_label="8 pc",
       tags=("meal", "wings", "share", "game day", "spicy"),
       terms=("wings", "buffalo", "chicken", "game day", "meal", "share"),
       spice=0.78, richness=0.58, pairs=('white', 'almond')),
    # Drinks (5)
    _p("DRK-COK-2", "Coca-Cola, 20 oz", "drink", "soda", 2.79, 0.46, 1, None, "single",
       portion=1.0, brand="Coca-Cola", size_label="20 fl oz",
       tags=("drink", "soda", "cold"), terms=("coke", "coca cola", "soda", "pop", "drink"),
       spice=0.0, richness=0.12, pairs=()),
    _p("DRK-COK-D", "Diet Coke, 20 oz", "drink", "soda", 2.79, 0.46, 1, None, "single",
       portion=1.0, brand="Coca-Cola", size_label="20 fl oz",
       tags=("drink", "soda", "diet", "cold"), terms=("diet coke", "diet", "soda", "pop", "drink"),
       spice=0.0, richness=0.02, pairs=()),
    _p("DRK-LEM-2", "Lemonade, 20 oz", "drink", "juice", 3.29, 0.50, 1, None, "single",
       portion=1.0, brand="Orchard Lane", size_label="20 fl oz",
       tags=("drink", "lemonade", "cold"), terms=("lemonade", "lemon", "juice", "drink"),
       spice=0.0, richness=0.1, pairs=()),
    _p("DRK-WAT-1", "Bottled Water, 1 L", "drink", "water", 1.99, 0.42, 1, None, "single",
       portion=1.0, brand="Clearwell", size_label="1 L",
       tags=("drink", "water"), terms=("water", "bottled water", "drink"),
       spice=0.0, richness=0.0, pairs=()),
    _p("DRK-TEA-2", "Sweet Iced Tea, 20 oz", "drink", "tea", 2.99, 0.48, 1, None, "single",
       portion=1.0, brand="Orchard Lane", size_label="20 fl oz",
       tags=("drink", "tea", "cold"), terms=("iced tea", "sweet tea", "tea", "drink"),
       spice=0.0, richness=0.12, pairs=()),
    # Sides / snacks (5)
    _p("SID-FRY-1", "French Fries", "side", "fries", 4.49, 0.52, 1, None, "single",
       portion=0.9, shareable=True, brand="Court St. Deli", size_label="large",
       tags=("side", "fries", "share", "snack"), terms=("fries", "french fries", "side", "snack"),
       spice=0.02, richness=0.45, pairs=()),
    _p("SID-MOZ-6", "Mozzarella Sticks, 6 Piece", "side", "fried", 6.99, 0.49, 1, None, "single",
       portion=1.2, shareable=True, brand="Court St. Deli", size_label="6 pc",
       tags=("side", "share", "snack", "game day"), terms=("mozzarella sticks", "cheese sticks", "side", "snack"),
       spice=0.04, richness=0.6, pairs=('caramel', 'classic')),
    _p("SID-ONI-1", "Onion Rings", "side", "fried", 5.49, 0.50, 1, None, "single",
       portion=1.0, shareable=True, brand="Court St. Deli", size_label="basket",
       tags=("side", "share", "snack"), terms=("onion rings", "rings", "side", "snack"),
       spice=0.08, richness=0.52, pairs=()),
    _p("SID-CHP-S", "Tortilla Chips & Salsa", "side", "chips", 5.99, 0.47, 1, None, "single",
       portion=1.6, shareable=True, brand="Sunset Taqueria", size_label="16 oz",
       tags=("side", "chips", "share", "game day", "snack"),
       terms=("chips", "tortilla chips", "salsa", "side", "snack"),
       spice=0.55, richness=0.3, pairs=('white', 'almond')),
    _p("SID-KNO-6", "Garlic Knots, 6 Piece", "side", "bread", 5.49, 0.51, 1, None, "single",
       portion=1.3, shareable=True, brand="Vinnie's Pizzeria", size_label="6 pc",
       tags=("side", "bread", "share"), terms=("garlic knots", "knots", "bread", "side"),
       spice=0.12, richness=0.48, pairs=('classic', 'caramel')),
    # Other desserts (4) - the competitive set a Magnum has to win
    _p("DES-BRW-1", "Fudge Brownie", "dessert", "bakery", 4.49, 0.43, 1, "brownie", "single",
       portion=1.0, brand="Hudson Bake Shop", size_label="single",
       tags=("dessert", "chocolate", "bakery"), terms=("brownie", "fudge", "chocolate", "dessert"),
       spice=0.0, richness=0.8, pairs=()),
    _p("DES-CHS-1", "New York Cheesecake Slice", "dessert", "bakery", 6.49, 0.41, 1, None, "single",
       portion=1.0, brand="Hudson Bake Shop", size_label="slice",
       tags=("dessert", "cake", "premium"), terms=("cheesecake", "cake", "dessert", "slice"),
       spice=0.0, richness=0.85, pairs=()),
    _p("DES-PNT-1", "Vanilla Bean Ice Cream Pint", "dessert", "ice cream", 6.99, 0.37, 1, "vanilla", "pint",
       portion=3.2, shareable=True, brand="Frostlane", size_label="1 pint",
       tags=("dessert", "ice cream", "frozen", "share", "family"),
       terms=("ice cream", "pint", "vanilla", "dessert", "family", "frozen"),
       spice=0.0, richness=0.7, pairs=()),
    _p("DES-CKI-4", "Black & White Cookies, 4 Pack", "dessert", "bakery", 4.99, 0.45, 1, "chocolate", "4-pack",
       portion=1.8, shareable=True, brand="Hudson Bake Shop", size_label="4 ct",
       tags=("dessert", "cookies", "share"), terms=("cookies", "black and white", "dessert", "4 pack"),
       spice=0.0, richness=0.55, pairs=()),
]

PRODUCTS: List[Dict] = MAGNUM_PRODUCTS + COMPANION_PRODUCTS
PRODUCT_BY_ID: Dict[str, Dict] = {p["sku_id"]: p for p in PRODUCTS}
MAGNUM_SKUS: List[str] = [p["sku_id"] for p in MAGNUM_PRODUCTS]
MAGNUM_SINGLES: List[str] = [p["sku_id"] for p in MAGNUM_PRODUCTS if p["subcategory"] == "single"]
MAGNUM_PACKS: List[str] = [p["sku_id"] for p in MAGNUM_PRODUCTS if p["subcategory"] == "multipack"]
FLAVOURS: List[str] = ["classic", "almond", "caramel", "white"]

# How each flavour trades against temperature. Heat does not just sell more ice
# cream, it sells different ice cream: in a heatwave the lighter, less cloying
# bars move and the heavy chocolate-caramel ones stall, and in February it is the
# other way round. +1 means the flavour gains the most on the hottest days.
#
# This lives here, next to the flavours themselves, because the generator and
# the live ranker both need it and they must not be allowed to disagree - a
# recommender tuned to a seasonality its own training data does not contain is
# the single easiest way to make a demo that cannot be reproduced.
HEAT_FLAVOUR_TILT: Dict[str, float] = {
    "white": 1.00,      # mildest and least rich - the hot-day bar
    "almond": 0.55,     # the texture carries; still light enough
    "classic": -0.55,   # milk chocolate holds up all year, gains in the cold
    "caramel": -1.00,   # richest and sweetest - a cold-weather bar
}

SINGLE_BY_FLAVOUR: Dict[str, str] = {
    "classic": "MAG-CLS-1",
    "almond": "MAG-ALM-1",
    "caramel": "MAG-CAR-1",
    "white": "MAG-WHT-1",
}
PACK_UNITS: Dict[str, int] = {p["sku_id"]: p["units_in_pack"] for p in MAGNUM_PRODUCTS}

CATEGORIES: List[Dict] = [
    {"id": "magnum", "label": "Magnum"},
    {"id": "meal", "label": "Meals"},
    {"id": "drink", "label": "Drinks"},
    {"id": "side", "label": "Sides"},
    {"id": "dessert", "label": "Desserts"},
]
CATEGORY_IDS: List[str] = [c["id"] for c in CATEGORIES]


def product(sku_id: str) -> Optional[Dict]:
    return PRODUCT_BY_ID.get(sku_id)


def catalogue_for_category(category: str) -> List[Dict]:
    return [p for p in PRODUCTS if p["category"] == category]
