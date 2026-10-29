"""Peer clusters (the six pattern families of §5.4) and the named demo profiles.

Cluster parameters drive the generator. The server never reads a household's
latent traits - it only ever sees the cluster label and observed behaviour,
which is the point of keeping ground truth in a separate table.
"""
from __future__ import annotations

from typing import Dict, List

# share            probability mass of the customer base
# craving_rate     baseline Magnum-relevant sessions per week
# attach_rate      P(session starts meal-led rather than dessert-led)
# price_sens       mean price sensitivity (Beta mean, 0-1)
# event_affinity   mean responsiveness to match/festival context
# heat_beta        extra hazard per degree of temperature anomaly
# cadence_days     mean days between Magnum purchases
# pack_bias        pull toward multipacks vs singles
# discount_uplift  GROUND TRUTH incremental conversion from a 20% voucher
# window_weights   preference over the six context time windows
CLUSTERS: List[Dict] = [
    {
        "cluster_id": "game_night",
        "name": "Weekend game-night indulgers",
        "short": "Game night",
        "share": 0.20,
        "craving_rate": 1.35,
        "attach_rate": 0.72,
        "price_sens": 0.38,
        "event_affinity": 0.86,
        "heat_beta": 0.055,
        "cadence_days": 9.0,
        "cadence_sd": 3.2,
        "pack_bias": 0.42,
        "discount_uplift": 0.052,
        "household_band": [0.12, 0.44, 0.34, 0.10],
        "flavour_bias": {"classic": 1.5, "almond": 1.7, "caramel": 1.2, "white": 0.8},
        "window_weights": {"morning": 0.02, "lunch": 0.08, "afternoon": 0.10,
                           "evening": 0.16, "dinner": 0.50, "late": 0.14},
        "weekend_bias": 1.55,
        "companion_bias": {"meal": 1.4, "drink": 1.5, "side": 1.6, "dessert": 0.7},
    },
    {
        "cluster_id": "family_planner",
        "name": "Family dessert planners",
        "short": "Family planner",
        "share": 0.18,
        "craving_rate": 0.85,
        "attach_rate": 0.80,
        "price_sens": 0.52,
        "event_affinity": 0.55,
        "heat_beta": 0.035,
        "cadence_days": 13.5,
        "cadence_sd": 4.4,
        "pack_bias": 0.88,
        "discount_uplift": 0.041,
        "household_band": [0.02, 0.18, 0.52, 0.28],
        "flavour_bias": {"classic": 1.8, "almond": 1.2, "caramel": 1.0, "white": 1.1},
        "window_weights": {"morning": 0.03, "lunch": 0.14, "afternoon": 0.12,
                           "evening": 0.20, "dinner": 0.46, "late": 0.05},
        "weekend_bias": 1.70,
        "companion_bias": {"meal": 1.6, "drink": 1.4, "side": 1.3, "dessert": 1.2},
    },
    {
        "cluster_id": "late_solo",
        "name": "Late-night solo snackers",
        "short": "Late solo",
        "share": 0.17,
        "craving_rate": 1.10,
        "attach_rate": 0.58,
        "price_sens": 0.44,
        "event_affinity": 0.42,
        "heat_beta": 0.048,
        "cadence_days": 10.5,
        "cadence_sd": 3.8,
        "pack_bias": 0.08,
        "discount_uplift": 0.036,
        "household_band": [0.62, 0.30, 0.07, 0.01],
        "flavour_bias": {"classic": 1.1, "almond": 1.0, "caramel": 1.9, "white": 1.3},
        "window_weights": {"morning": 0.01, "lunch": 0.04, "afternoon": 0.06,
                           "evening": 0.10, "dinner": 0.28, "late": 0.51},
        "weekend_bias": 1.20,
        "companion_bias": {"meal": 1.1, "drink": 1.0, "side": 1.5, "dessert": 0.9},
    },
    {
        "cluster_id": "heat_seeker",
        "name": "Heat-triggered direct seekers",
        "short": "Heat seeker",
        "share": 0.16,
        "craving_rate": 1.05,
        "attach_rate": 0.22,
        "price_sens": 0.40,
        "event_affinity": 0.30,
        "heat_beta": 0.115,
        "cadence_days": 8.5,
        "cadence_sd": 3.0,
        "pack_bias": 0.22,
        "discount_uplift": 0.028,
        "household_band": [0.34, 0.40, 0.22, 0.04],
        "flavour_bias": {"classic": 1.4, "almond": 1.3, "caramel": 0.9, "white": 1.6},
        "window_weights": {"morning": 0.04, "lunch": 0.16, "afternoon": 0.30,
                           "evening": 0.22, "dinner": 0.22, "late": 0.06},
        "weekend_bias": 1.10,
        "companion_bias": {"meal": 0.5, "drink": 1.2, "side": 0.7, "dessert": 1.1},
    },
    {
        "cluster_id": "deal_explorer",
        "name": "Deal-sensitive explorers",
        "short": "Deal explorer",
        "share": 0.17,
        "craving_rate": 0.95,
        "attach_rate": 0.62,
        "price_sens": 0.86,
        "event_affinity": 0.48,
        "heat_beta": 0.040,
        "cadence_days": 12.0,
        "cadence_sd": 5.0,
        "pack_bias": 0.55,
        "discount_uplift": 0.118,
        "household_band": [0.24, 0.38, 0.30, 0.08],
        "flavour_bias": {"classic": 1.2, "almond": 1.1, "caramel": 1.2, "white": 1.2},
        "window_weights": {"morning": 0.04, "lunch": 0.14, "afternoon": 0.16,
                           "evening": 0.18, "dinner": 0.36, "late": 0.12},
        "weekend_bias": 1.25,
        "companion_bias": {"meal": 1.2, "drink": 1.1, "side": 1.2, "dessert": 1.4},
    },
    {
        "cluster_id": "premium_low_freq",
        "name": "Low-frequency premium buyers",
        "short": "Premium",
        "share": 0.12,
        "craving_rate": 0.55,
        "attach_rate": 0.50,
        "price_sens": 0.16,
        "event_affinity": 0.38,
        "heat_beta": 0.030,
        "cadence_days": 21.0,
        "cadence_sd": 7.0,
        "pack_bias": 0.30,
        "discount_uplift": 0.009,
        "household_band": [0.28, 0.46, 0.22, 0.04],
        "flavour_bias": {"classic": 0.9, "almond": 1.6, "caramel": 1.3, "white": 1.7},
        "window_weights": {"morning": 0.03, "lunch": 0.10, "afternoon": 0.14,
                           "evening": 0.22, "dinner": 0.42, "late": 0.09},
        "weekend_bias": 1.15,
        "companion_bias": {"meal": 1.0, "drink": 0.9, "side": 0.8, "dessert": 1.3},
    },
]

CLUSTER_BY_ID: Dict[str, Dict] = {c["cluster_id"]: c for c in CLUSTERS}
CLUSTER_IDS: List[str] = [c["cluster_id"] for c in CLUSTERS]
HOUSEHOLD_BANDS: List[str] = ["1", "2", "3-4", "5+"]

# --------------------------------------------------------------------------
# Named demo profiles (§2.4, Appendix A). Each is pinned to a deterministic
# customer_id so the golden scenarios are reproducible across regenerations.
# --------------------------------------------------------------------------

DEMO_PROFILES: List[Dict] = [
    {"customer_id": "CUS-000001", "display_name": "John Smith", "cluster_id": "game_night",
     "home_area": "astoria", "usual_window": "dinner", "household_band": "2",
     "blurb": "Game-night regular in Queens. Orders wings and a pie first, adds Magnum once the game is on."},
    {"customer_id": "CUS-000002", "display_name": "Sarah Miller", "cluster_id": "family_planner",
     "home_area": "greenwich", "usual_window": "dinner", "household_band": "3-4",
     "blurb": "Sunday family order in Greenwich. Buys the 6-count box, reorders on a longer cycle."},
    {"customer_id": "CUS-000003", "display_name": "David Brown", "cluster_id": "late_solo",
     "home_area": "williamsburg", "usual_window": "late", "household_band": "1",
     "blurb": "Late-night solo in Brooklyn. One platter, one premium single bar, never a multipack."},
    {"customer_id": "CUS-000004", "display_name": "Emily Davis", "cluster_id": "heat_seeker",
     "home_area": "chelsea", "usual_window": "afternoon", "household_band": "2",
     "blurb": "Searches ice cream directly when the heat index climbs. Rarely meal-led."},
    {"customer_id": "CUS-000005", "display_name": "Michael Johnson", "cluster_id": "deal_explorer",
     "home_area": "norwalk", "usual_window": "dinner", "household_band": "3-4",
     "blurb": "Waits for a promo. The one profile where a voucher genuinely changes behaviour."},
    {"customer_id": "CUS-000006", "display_name": "Jessica Wilson", "cluster_id": "premium_low_freq",
     "home_area": "upper-east-side", "usual_window": "evening", "household_band": "2",
     "blurb": "Buys rarely, buys premium. A discount here is margin left on the table."},
]

DEMO_BY_ID: Dict[str, Dict] = {p["customer_id"]: p for p in DEMO_PROFILES}
DEMO_IDS: List[str] = [p["customer_id"] for p in DEMO_PROFILES]
