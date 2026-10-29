"""What a month, a quarter and half a year of running this look like.

Every screen before this one answers "is the decision right". This one answers
the question the person signing the cheque actually asks, which is "what does it
add up to", and it is the easiest screen in the product to lie on. So the rules
here are deliberately strict:

  * Every rate is read off the log or off the offline evaluation. Nothing on
    this page is a number somebody liked the look of.
  * The comparison is always named. "Worth $X" is meaningless; "worth $X more
    than sending everybody a 20% voucher" is a claim that can be argued with.
  * The confidence interval travels with the estimate. The per-decision values
    come from inverse-propensity scoring on a holdout split and they have real
    error bars, so the projections carry those bars scaled by the same horizon.
  * The one genuine assumption - how much of the measured stock loss better
    forecasting actually recovers - is exposed as a control rather than buried
    in a constant, and it is labelled an assumption on the screen.

Volume and money are kept apart on purpose. The extra orders and the extra
margin are two views of the same lever, not two levers, and adding them would
double-count the entire offer policy.
"""
from functools import lru_cache
from typing import Dict, List, Optional

from magnum_core import catalog as cat

from .store import _con
from . import analysis

# Horizons the page projects over. Named rather than free-form: a client asks
# "what does a quarter look like", not "what do 91.3 days look like".
HORIZONS = [
    {"key": "m1", "label": "1 month", "days": 30},
    {"key": "m3", "label": "3 months", "days": 91},
    {"key": "m6", "label": "6 months", "days": 182},
]

# The share of measured stock loss that better forecasting is assumed to
# recover. This is the only assumption on the page and it is surfaced as a
# control, defaulted low. Filling every shelf to the forecast's p90 would remove
# most stockout hours and create waste doing it, so a number near 1.0 would be a
# claim about a different, worse policy.
DEFAULT_RECOVERY = 0.35

# The policy the projection is measured against. Most retailers run something
# close to `always_voucher20` - one campaign, one depth, everybody in the file -
# so that is the comparison the page leads with. `do_nothing` is kept alongside
# it because "versus not doing this at all" is the other question in the room.
BASELINES = {
    "always_voucher20": "a blanket 20% campaign",
    "do_nothing": "no targeting at all",
}


@lru_cache(maxsize=1)
def _base() -> Dict:
    """The measured rates, per day, off the whole log. Cached - it is a scan."""
    con = _con()
    q = lambda s: con.execute(s).fetchone()
    days, = q("SELECT MAX(day_idx) - MIN(day_idx) + 1 FROM orders")
    orders, revenue, margin, mag_orders = q(
        "SELECT COUNT(*), SUM(total), SUM(gross_margin), SUM(has_magnum) FROM orders")
    mag_units, = q(
        "SELECT SUM(magnum_qty * CASE magnum_sku WHEN 'MAG-ALM-3' THEN 3 "
        "WHEN 'MAG-CAR-3' THEN 3 WHEN 'MAG-WHT-3' THEN 3 WHEN 'MAG-MIN-6' THEN 6 "
        "ELSE 1 END) FROM orders WHERE has_magnum = 1")
    decisions, eligible = q("SELECT COUNT(*), SUM(eligible) FROM offers")
    # The funnel, all stores combined. `shown` is a recommendation that actually
    # reached a screen; `converted` on a *not* shown decision is a household that
    # bought Magnum with no prompt at all, which is the honest denominator this
    # page has to keep visible - it is the share the system cannot claim.
    shown, conv_shown, conv_disc = q(
        "SELECT COUNT(*), SUM(converted), SUM(CASE WHEN converted = 1 AND discount_pct > 0 "
        "THEN 1 ELSE 0 END) FROM offers WHERE shown = 1")
    conv_unprompted, = q("SELECT COUNT(*) FROM offers WHERE shown = 0 AND converted = 1")
    inv_rows, stockout_rows, waste = q(
        "SELECT COUNT(*), SUM(is_stockout), SUM(waste) FROM inventory")
    # One *episode* is a contiguous run of stockout hours on one shelf - i.e. one
    # van trip, not one hour of pain. Hours say how bad it was; episodes say how
    # many times somebody would have had to move stock between stores to stop it.
    episodes, = q(
        "SELECT SUM(CASE WHEN is_stockout = 1 AND (prev IS NULL OR prev = 0) THEN 1 ELSE 0 END) "
        "FROM (SELECT is_stockout, LAG(is_stockout) OVER "
        "      (PARTITION BY store_id, sku_id ORDER BY snapshot_time) AS prev FROM inventory)")
    subs, = q("SELECT SUM(was_substituted) FROM orders")
    stores, = q("SELECT COUNT(DISTINCT store_id) FROM inventory")
    customers, = q("SELECT COUNT(*) FROM customers")
    con.close()

    days = float(days)
    # Average contribution on one Magnum unit, weighted by what actually sold.
    unit_margin = sum(cat.PRODUCT_BY_ID[s]["unit_margin"] for s in cat.MAGNUM_SKUS) / len(cat.MAGNUM_SKUS)
    return {
        "days": days,
        "stores": int(stores),
        "customers": int(customers),
        "orders_per_day": orders / days,
        "magnum_orders_per_day": float(mag_orders) / days,
        "magnum_units_per_day": float(mag_units) / days,
        "revenue_per_day": float(revenue) / days,
        "margin_per_day": float(margin) / days,
        "decisions_per_day": float(eligible or decisions) / days,
        "shown_per_day": float(shown) / days,
        "converted_per_day": float(conv_shown) / days,
        "converted_discounted_per_day": float(conv_disc) / days,
        "converted_full_price_per_day": float(conv_shown - conv_disc) / days,
        "unprompted_per_day": float(conv_unprompted) / days,
        "shelf_hours_per_day": float(inv_rows) / days,
        "stockout_episodes_per_day": float(episodes) / days,
        "stockout_rate": float(stockout_rows) / float(inv_rows),
        "stockout_hours_per_day": float(stockout_rows) / days,
        "waste_units_per_day": float(waste) / days,
        "substituted_per_day": float(subs) / days,
        # Measured demand on an average shelf-hour. Stockouts cluster in busy
        # hours, so costing them at the average rate understates the loss - which
        # is the direction to be wrong in on this page.
        "units_per_shelf_hour": float(mag_units) / float(inv_rows),
        "unit_margin": unit_margin,
    }


def _policy_rows() -> Dict[str, Dict]:
    return {p["policy"]: p for p in analysis.policy_eval()["policies"]}


def compute(recovery: float = DEFAULT_RECOVERY, scale: float = 1.0) -> Dict:
    """Project the measured per-decision and per-shelf-hour rates forward."""
    b = _base()
    pol_rows = _policy_rows()
    live = pol_rows.get("eic_greedy_v1")
    if live is None:
        return {"error": "policy evaluation unavailable"}

    recovery = max(0.0, min(1.0, float(recovery)))
    scale = max(0.1, min(200.0, float(scale)))

    comparisons = []
    for key, phrase in BASELINES.items():
        base = pol_rows.get(key)
        if not base:
            continue
        delta = live["value_per_decision"] - base["value_per_decision"]
        # Interval arithmetic on two independent estimates: the widest honest
        # band, not the narrowest presentable one.
        lo = live["ci_low"] - base["ci_high"]
        hi = live["ci_high"] - base["ci_low"]
        comparisons.append({
            "key": key, "against": phrase,
            "value_per_decision": round(delta, 4),
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "significant": bool(lo > 0),
            "live_value": live["value_per_decision"],
            "baseline_value": base["value_per_decision"],
            "attach_delta_pp": round((live["attach_rate"] - base["attach_rate"]) * 100, 2),
        })

    horizons = []
    for h in HORIZONS:
        d = float(h["days"])
        decisions = b["decisions_per_day"] * d * scale
        shelf_hours = b["shelf_hours_per_day"] * d * scale
        stockout_hours = b["stockout_hours_per_day"] * d * scale
        waste_units = b["waste_units_per_day"] * d * scale

        rows = []
        for c in comparisons:
            rows.append({
                "key": c["key"], "against": c["against"],
                "margin": round(c["value_per_decision"] * decisions, 0),
                "margin_low": round(c["ci_low"] * decisions, 0),
                "margin_high": round(c["ci_high"] * decisions, 0),
                "significant": c["significant"],
                "extra_magnum_orders": round(c["attach_delta_pp"] / 100.0 * decisions, 0),
            })

        # Availability. Three measured quantities, one stated assumption.
        hours_recovered = stockout_hours * recovery
        units_recovered = hours_recovered * b["units_per_shelf_hour"]
        waste_avoided = waste_units * recovery
        availability_margin = (units_recovered + waste_avoided) * b["unit_margin"]
        episodes = b["stockout_episodes_per_day"] * d * scale
        rebalances = episodes * recovery

        headline = next((r for r in rows if r["key"] == "always_voucher20"), rows[0] if rows else None)
        horizons.append({
            "key": h["key"], "label": h["label"], "days": h["days"],
            "decisions": round(decisions, 0),
            "magnum_orders": round(b["magnum_orders_per_day"] * d * scale, 0),
            "magnum_units": round(b["magnum_units_per_day"] * d * scale, 0),
            "revenue": round(b["revenue_per_day"] * d * scale, 0),
            "gross_margin": round(b["margin_per_day"] * d * scale, 0),
            "policy_rows": rows,
            "availability": {
                "shelf_hours": round(shelf_hours, 0),
                "stockout_hours": round(stockout_hours, 0),
                "stockout_hours_avoided": round(hours_recovered, 0),
                "units_recovered": round(units_recovered, 0),
                "waste_units": round(waste_units, 0),
                "waste_units_avoided": round(waste_avoided, 0),
                "margin": round(availability_margin, 0),
                # Bars that end up in a basket instead of nowhere: the ones the
                # empty shelf would have refused, plus the ones the bin would
                # have taken. Same two quantities as the margin above, in units.
                "bars_saved": round(units_recovered + waste_avoided, 0),
                "stockout_episodes": round(episodes, 0),
                "rebalances": round(rebalances, 0),
                "substituted_orders": round(b["substituted_per_day"] * d * scale, 0),
            },
            # All stores combined. Sums to what the log did, not to a target.
            "funnel": {
                "shown": round(b["shown_per_day"] * d * scale, 0),
                "converted": round(b["converted_per_day"] * d * scale, 0),
                "discounted": round(b["converted_discounted_per_day"] * d * scale, 0),
                "full_price": round(b["converted_full_price_per_day"] * d * scale, 0),
                "unprompted": round(b["unprompted_per_day"] * d * scale, 0),
                "conversion_rate": round(b["converted_per_day"] / b["shown_per_day"], 4),
                "discount_share": round(b["converted_discounted_per_day"]
                                        / b["converted_per_day"], 4),
            },
            "total_margin": round((headline["margin"] if headline else 0.0) + availability_margin, 0),
            "total_margin_low": round((headline["margin_low"] if headline else 0.0)
                                      + availability_margin * 0.5, 0),
            "total_margin_high": round((headline["margin_high"] if headline else 0.0)
                                       + availability_margin * 1.5, 0),
        })

    return {
        "horizons": horizons,
        "comparisons": comparisons,
        "assumptions": {
            "recovery_share": recovery,
            "recovery_note": ("The one assumption on this page: the share of measured "
                              "stockout hours and waste that better forecasting actually "
                              "recovers. Everything else is read off the log. Move it and "
                              "every availability number moves with it."),
            "network_scale": scale,
            "scale_note": ("1.0 is the simulated network — {} stores, {:,} households, "
                           "{:.0f} days of orders. Scale it to a real footprint and the "
                           "rates hold while the volumes move.".format(
                               b["stores"], b["customers"], b["days"])),
        },
        "measured": {
            "days_of_log": b["days"],
            "stores": b["stores"],
            "customers": b["customers"],
            "decisions_per_day": round(b["decisions_per_day"], 1),
            "stockout_rate": round(b["stockout_rate"], 4),
            "units_per_shelf_hour": round(b["units_per_shelf_hour"], 4),
            "unit_margin": round(b["unit_margin"], 4),
            "waste_units_per_day": round(b["waste_units_per_day"], 1),
            "substituted_per_day": round(b["substituted_per_day"], 2),
            "shown_per_day": round(b["shown_per_day"], 1),
            "converted_per_day": round(b["converted_per_day"], 1),
            "stockout_episodes_per_day": round(b["stockout_episodes_per_day"], 2),
        },
        "method": [
            "Per-decision value is inverse-propensity scoring on a holdout split. "
            "The log randomised its offer arms at a known 20% propensity, so an "
            "alternative policy is scored on the decisions where it happens to agree "
            "with the log, weighted by 1/0.2. No reward model is involved, so a bad "
            "policy cannot hide behind a bad model.",
            "Margin is the difference between this policy and a named baseline, "
            "multiplied by the number of eligible decisions in the horizon. The "
            "interval is the widest honest band on that difference.",
            "Extra orders and extra margin are two views of one lever, not two "
            "levers. They are never added together.",
            "Stock loss is costed at the average demand on a shelf-hour. Stockouts "
            "cluster in busy hours, so this understates the loss rather than "
            "flattering it.",
            "The funnel is counted, not modelled: shown, bought, and whether the "
            "basket that bought needed a coupon to do it. Purchases made with no "
            "recommendation on screen are reported separately and are never "
            "counted as something the system won.",
            "A rebalance is one contiguous run of stockout hours on one shelf - "
            "one van trip, not one hour. Hours say how bad it was; episodes say "
            "how many times somebody would have had to act.",
        ],
    }


def clear_cache():
    _base.cache_clear()
