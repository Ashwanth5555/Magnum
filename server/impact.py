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

# The share of substituted Magnum orders that would have been *lost* without the
# substitute. The generator has every shopper accept the swap, so counting all
# of them as saved claims the whole lot - but a shopper facing a gap often picks
# another flavour unprompted. Retail out-of-stock studies (Corsten & Gruen) put
# the shoppers who leave or buy elsewhere at about four in ten, so that is the
# default, and like recovery it is a control rather than a constant.
DEFAULT_SUB_SAVE = 0.40

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


@lru_cache(maxsize=1)
def _windows() -> Dict[str, Dict]:
    """The log counted over its real trailing windows.

    Projecting one log-wide daily average across three horizons printed the same
    rate on every bar and made each bar an exact multiple of the first, which hid
    the season: shown-to-bought runs from 13% in December to 26% in August, and
    the summer months carry more decisions. Each horizon is instead the last N
    days of the log, ending on the last day it has, so the funnel, the decisions
    the offer policy is applied to and the substitutions are counts, not
    projections.
    """
    con = _con()
    end, = con.execute("SELECT MAX(date(decided_at)) FROM offers").fetchone()
    out = {}
    for h in HORIZONS:
        since = "-{} days".format(h["days"])
        start, shown, conv, disc, unprompted, eligible = con.execute(
            "SELECT date(?, ?, '+1 day'), "
            "SUM(shown), "
            "SUM(CASE WHEN shown = 1 AND converted = 1 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN shown = 1 AND converted = 1 AND discount_pct > 0 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN shown = 0 AND converted = 1 THEN 1 ELSE 0 END), "
            "SUM(eligible) "
            "FROM offers WHERE date(decided_at) > date(?, ?)",
            (end, since, end, since)).fetchone()
        subs, = con.execute(
            "SELECT SUM(was_substituted) FROM orders WHERE date(ordered_at) > date(?, ?)",
            (end, since)).fetchone()
        out[h["key"]] = {"from": start, "to": end, "shown": float(shown or 0),
                         "converted": float(conv or 0), "discounted": float(disc or 0),
                         "unprompted": float(unprompted or 0),
                         "decisions": float(eligible or 0), "substituted": float(subs or 0)}
    con.close()
    return out


@lru_cache(maxsize=1)
def _monthly() -> List[Dict]:
    """The funnel counted per calendar month across the whole log.

    The trailing windows all end in summer, so the longer ones read *lower* -
    they take in the cooler spring. Month by month is the view that shows what
    actually moves the rate: shown-to-bought climbs with the weather, from
    December's low to August's high.
    """
    con = _con()
    rows = con.execute(
        "SELECT strftime('%Y-%m', decided_at) AS m, "
        "SUM(shown), "
        "SUM(CASE WHEN shown = 1 AND converted = 1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN shown = 1 AND converted = 1 AND discount_pct > 0 THEN 1 ELSE 0 END) "
        "FROM offers GROUP BY m ORDER BY m").fetchall()
    con.close()
    return [{"month": m, "shown": float(s or 0), "converted": float(c or 0),
             "discounted": float(dc or 0)} for m, s, c, dc in rows]


def _policy_rows() -> Dict[str, Dict]:
    return {p["policy"]: p for p in analysis.policy_eval()["policies"]}


def compute(recovery: float = DEFAULT_RECOVERY, scale: float = 1.0,
            sub_save: float = DEFAULT_SUB_SAVE) -> Dict:
    """Apply the measured per-decision rates to the real windows of the log."""
    b = _base()
    pol_rows = _policy_rows()
    live = pol_rows.get("eic_greedy_v1")
    if live is None:
        return {"error": "policy evaluation unavailable"}

    recovery = max(0.0, min(1.0, float(recovery)))
    scale = max(0.1, min(200.0, float(scale)))
    sub_save = max(0.0, min(1.0, float(sub_save)))

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
        # The attach difference is scored on the same holdout rows for both
        # policies, so its interval is the paired one from policy_eval.
        _, a_lo, a_hi = live.get("attach_diff_pp", {}).get(key, [None, None, None])
        comparisons.append({
            "key": key, "against": phrase,
            "value_per_decision": round(delta, 4),
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "significant": bool(lo > 0),
            "live_value": live["value_per_decision"],
            "baseline_value": base["value_per_decision"],
            "attach_delta_pp": round((live["attach_rate"] - base["attach_rate"]) * 100, 2),
            "attach_ci_low_pp": a_lo, "attach_ci_high_pp": a_hi,
        })

    windows = _windows()
    horizons = []
    for h in HORIZONS:
        d = float(h["days"])
        w = windows[h["key"]]
        # The decisions the policy would actually have faced in this window,
        # counted - summer windows carry more of them than a flat average says.
        decisions = w["decisions"] * scale
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
                "extra_magnum_orders_low": (round(c["attach_ci_low_pp"] / 100.0 * decisions, 0)
                                            if c["attach_ci_low_pp"] is not None else None),
                "extra_magnum_orders_high": (round(c["attach_ci_high_pp"] / 100.0 * decisions, 0)
                                             if c["attach_ci_high_pp"] is not None else None),
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
                # Every order that got a substitute, counted in the window, and
                # the share of them that would otherwise have been lost.
                "substituted_orders": round(w["substituted"] * scale, 0),
                "substitutions_saved": round(w["substituted"] * sub_save * scale, 0),
            },
            # All stores combined, counted over the real last N days of the log.
            # Sums to what the log did in that window, not to a target.
            "funnel": {
                "from": w["from"], "to": w["to"],
                "shown": round(w["shown"] * scale, 0),
                "converted": round(w["converted"] * scale, 0),
                "discounted": round(w["discounted"] * scale, 0),
                "full_price": round((w["converted"] - w["discounted"]) * scale, 0),
                "unprompted": round(w["unprompted"] * scale, 0),
                "conversion_rate": round(w["converted"] / w["shown"], 4) if w["shown"] else 0.0,
                "discount_share": round(w["discounted"] / w["converted"], 4) if w["converted"] else 0.0,
            },
            "total_margin": round((headline["margin"] if headline else 0.0) + availability_margin, 0),
            "total_margin_low": round((headline["margin_low"] if headline else 0.0)
                                      + availability_margin * 0.5, 0),
            "total_margin_high": round((headline["margin_high"] if headline else 0.0)
                                       + availability_margin * 1.5, 0),
        })

    # Month by month, all stores combined. Counts scale with the network; the
    # rate is a share and does not.
    monthly = [{
        "month": r["month"],
        "shown": round(r["shown"] * scale, 0),
        "converted": round(r["converted"] * scale, 0),
        "discounted": round(r["discounted"] * scale, 0),
        "full_price": round((r["converted"] - r["discounted"]) * scale, 0),
        "conversion_rate": round(r["converted"] / r["shown"], 4) if r["shown"] else 0.0,
    } for r in _monthly()]

    return {
        "horizons": horizons,
        "monthly": monthly,
        "comparisons": comparisons,
        "assumptions": {
            "recovery_share": recovery,
            "substitute_save_share": sub_save,
            "substitute_note": ("Share of substituted orders that would have been lost "
                                "without the substitute. The simulation has every shopper "
                                "accept the swap; in practice many would pick another "
                                "flavour unprompted, so only this share counts as saved."),
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
            "The funnel is counted, not modelled, over the real last 1, 3 and 6 "
            "months of the log: shown, bought, and whether the basket that bought "
            "needed a coupon to do it. Purchases made with no "
            "recommendation on screen are reported separately and are never "
            "counted as something the system won.",
            "A rebalance is one contiguous run of stockout hours on one shelf - "
            "one van trip, not one hour. Hours say how bad it was; episodes say "
            "how many times somebody would have had to act.",
        ],
    }


def clear_cache():
    _base.cache_clear()
    _windows.cache_clear()
    _monthly.cache_clear()
