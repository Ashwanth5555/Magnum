"""Generation volumes and simulation window (§5.1 of the build document)."""
from __future__ import annotations

from datetime import datetime

SEED = 20260901

# Simulation window: 39 weeks of hourly context and inventory, ending the day
# before the documented "prepared" date so the demo has a clean recent history.
#
# The window deliberately spans December to September. An ice cream demo run
# only over summer cannot show the one driver the whole thesis rests on - a
# 12-week June-to-September window never drops below 60F, so "attach rises with
# temperature" is asserted rather than demonstrated. Starting in December buys
# a genuine 35F-to-90F ramp, snow days, and a seasonality curve worth plotting.
SIM_END = datetime(2026, 9, 1, 0, 0)
WEEKS = 39
DAYS = WEEKS * 7                           # 273
HOURS = DAYS * 24                          # 6,552
SIM_START = datetime(2025, 12, 2, 0, 0)    # SIM_END - 273 days

N_CUSTOMERS = 5_000
TARGET_SESSIONS = 240_000
TARGET_ORDERS = 90_000
TARGET_EVENTS = 500_000

FORECAST_HORIZON_HOURS = 48
# Backtest origins: a forecast run every 7 days at noon, each looking 48 hours
# ahead. Without origins inside the window there is nothing to score the
# forecast against - the live snapshot at SIM_END predicts hours no order ever
# lands in, so every accuracy metric comes back empty.
FORECAST_ORIGIN_EVERY_DAYS = 7
FORECAST_ORIGIN_HOUR = 12

# Offer arms. Assignment is uniform at random and logged, so incremental
# effects are estimable rather than inferred from who happened to be targeted.
OFFER_ARMS = [
    {"arm": "none", "offer_id": None, "discount_pct": 0.0, "contact_cost": 0.00},
    {"arm": "voucher20", "offer_id": "MAGNUM20", "discount_pct": 0.20, "contact_cost": 0.05},
    {"arm": "multipack_value", "offer_id": "PACKVALUE", "discount_pct": 0.08, "contact_cost": 0.05},
    {"arm": "flavour_discovery", "offer_id": "TRYNEW", "discount_pct": 0.00, "contact_cost": 0.03},
    {"arm": "reminder", "offer_id": "REORDER", "discount_pct": 0.00, "contact_cost": 0.02},
]

# Baseline conversion levers, tuned so the generated funnel lands on the
# volumes above without any per-run fudge factor.
BASE_ORDER_CONVERSION = 0.40
# Intercept of the Magnum attach logit. Tuned so overall attach lands near 30%,
# split roughly 55% on dessert-led sessions and 15% on meal-led ones.
MAGNUM_LOGIT_INTERCEPT = -2.95

# Share of sessions carrying the full client-side interaction stream.
INSTRUMENTATION_RATE = 0.35

# Cabinet / inventory policy used when simulating stock.
SAFETY_STOCK_UNITS = 6
REPLENISH_HOUR = 11
REPLENISH_COVER = 1.45
DAILY_SHRINK_RATE = 0.004
TRANSFER_LEAD_MINUTES = 90
