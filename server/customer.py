"""Per-household analytics.

Everything the log knows about one customer, assembled for the customer view.
This module reads `orders`, `order_items`, `offers` and `sessions` - the same
tables the application already reads - and nothing else. `latent_traits` and
`ground_truth` stay unreachable: the household's propensities are not shown
because the application does not know them, and saying so on the screen is
part of the point.

Every aggregate is returned beside its peer-cluster benchmark. A number like
"attach rate 34%" is meaningless to a reviewer without "and the cluster runs
29%", so the two always travel together.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from typing import Dict, List, Optional

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from magnum_core import catalog as cat        # noqa: E402
from magnum_core import policies as pol       # noqa: E402
from .store import get_store, _con, NOW       # noqa: E402

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Astronomical seasons, assigned by the month's midpoint: the solstice and
# equinox boundaries fall around the 20th, so a month belongs to whichever
# season holds its 15th. December is autumn on this reckoning, which is the
# only reason the window covers all four - it opens on 2 December, nineteen
# days before the solstice. Using the meteorological definition instead would
# put December in winter and leave the customer screen showing three seasons
# and an empty band, so the boundary choice is load-bearing rather than
# cosmetic.
SEASON = {12: "Autumn", 1: "Winter", 2: "Winter", 3: "Winter",
          4: "Spring", 5: "Spring", 6: "Spring",
          7: "Summer", 8: "Summer", 9: "Summer",
          10: "Autumn", 11: "Autumn"}


def _pct(x) -> float:
    return round(float(x) * 100, 2)


def _clean(obj):
    """pandas hands back NaN for an empty mean and inf for a zero-denominator
    ratio; neither is valid JSON. A household with two orders is a legitimate
    case here, so scrub rather than guard at forty call sites."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        return None if (obj != obj or obj in (float("inf"), float("-inf"))) else obj
    return obj


def _delta(mine: float, theirs: float) -> Dict:
    """Signed difference against the cluster, plus a ratio that survives a zero
    benchmark. The UI shows the ratio when it is meaningful and the difference
    when it is not."""
    d = float(mine) - float(theirs)
    return {"mine": round(float(mine), 4), "cluster": round(float(theirs), 4),
            "diff": round(d, 4),
            "ratio": round(float(mine) / float(theirs), 3) if theirs else None,
            "direction": "above" if d > 1e-9 else ("below" if d < -1e-9 else "level")}


def analytics(customer_id: str) -> Optional[Dict]:
    st = get_store()
    cf = st.features(customer_id)
    if not cf:
        return None
    clf = st.cluster(cf["peer_cluster"])
    con = _con()

    orders = pd.read_sql(
        "SELECT order_id, store_id, state, ordered_at, subtotal, discount, total, "
        "gross_margin, has_magnum, magnum_sku, magnum_qty, intent_class, people_inferred, "
        "was_substituted, split FROM orders WHERE customer_id = ? ORDER BY ordered_at",
        con, params=[customer_id], parse_dates=["ordered_at"])
    items = pd.read_sql(
        "SELECT oi.order_id, oi.sku_id, oi.category, oi.quantity, "
        "oi.unit_price * oi.quantity AS line_total, oi.was_recommended "
        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
        "WHERE o.customer_id = ?", con, params=[customer_id])
    offers = pd.read_sql(
        "SELECT decided_at, arm_assigned, eligible, shown, converted, discount_pct, "
        "discount_value, contact_cost, decision_reward, cluster, heat_pull "
        "FROM offers WHERE customer_id = ? ORDER BY decided_at",
        con, params=[customer_id], parse_dates=["decided_at"])
    sess = con.execute(
        "SELECT COUNT(*) n FROM sessions WHERE customer_id = ?",
        [customer_id]).fetchone()
    con.close()

    n_orders = int(len(orders))
    n_sessions = int(sess["n"] or 0)
    mag = orders[orders["has_magnum"] == 1]
    units = int((mag["magnum_qty"] * mag["magnum_sku"].map(
        lambda s: cat.PACK_UNITS.get(s, 1))).sum()) if len(mag) else 0

    # ---- lifetime -------------------------------------------------------
    lifetime = {
        "sessions": n_sessions,
        "orders": n_orders,
        "session_to_order": round(n_orders / n_sessions, 4) if n_sessions else 0.0,
        "spend": round(float(orders["total"].sum()), 2),
        "margin": round(float(orders["gross_margin"].sum()), 2),
        "avg_basket": round(float(orders["total"].mean()), 2) if n_orders else 0.0,
        "discount_taken": round(float(orders["discount"].sum()), 2),
        "magnum_orders": int(len(mag)),
        "magnum_units": units,
        "magnum_spend": round(float(mag["total"].sum()), 2) if len(mag) else 0.0,
        "first_order_at": orders["ordered_at"].min().isoformat() if n_orders else None,
        "last_order_at": orders["ordered_at"].max().isoformat() if n_orders else None,
        "substitution_rate": round(float(orders["was_substituted"].mean()), 4) if n_orders else 0.0,
    }

    # ---- versus the peer cluster ---------------------------------------
    attach = float(orders["has_magnum"].mean()) if n_orders else 0.0
    avg_units = float((mag["magnum_qty"] * mag["magnum_sku"].map(
        lambda s: cat.PACK_UNITS.get(s, 1))).mean()) if len(mag) else 0.0
    pack_share = float(mag["magnum_sku"].isin(cat.MAGNUM_PACKS).mean()) if len(mag) else 0.0
    versus = {
        "attach_rate": _delta(attach, clf["attach_rate"]),
        "avg_units": _delta(avg_units, clf["avg_units"]),
        "pack_share": _delta(pack_share, clf["pack_share"]),
        "avg_people": _delta(float(orders["people_inferred"].mean()) if n_orders else 0.0,
                             clf["avg_people"]),
        "discount_response": _delta(cf["discount_response"], clf["discount_share"]),
    }

    # ---- cadence and what happens next ---------------------------------
    due = cf["due_ratio"]
    if cf["days_since_magnum"] is None:
        cadence_state, cadence_note = "unknown", "No Magnum purchase in the window."
    elif due >= 1.25:
        cadence_state, cadence_note = "overdue", "Past the household's own rhythm."
    elif due >= 0.85:
        cadence_state, cadence_note = "due", "Inside the reorder window."
    else:
        cadence_state, cadence_note = "early", "Bought recently - a reminder would be noise."
    next_due = None
    if cf["last_magnum_at"]:
        next_due = (pd.Timestamp(cf["last_magnum_at"])
                    + timedelta(days=float(cf["cadence_days"]))).isoformat()
    cadence = {
        "cadence_days": cf["cadence_days"],
        "days_since_magnum": cf["days_since_magnum"],
        "due_ratio": due,
        "state": cadence_state,
        "note": cadence_note,
        "next_due_at": next_due,
        "usual_hour": cf["usual_hour"],
        "cluster_cadence_days": clf.get("cadence_days"),
    }

    # ---- mixes, always beside the cluster's ------------------------------
    def mix(mine: Dict[str, float], theirs: Dict[str, float]) -> List[Dict]:
        keys = sorted(set(mine) | set(theirs), key=lambda k: -mine.get(k, 0.0))
        return [{"key": k, "mine": round(mine.get(k, 0.0), 4),
                 "cluster": round(theirs.get(k, 0.0), 4)} for k in keys]

    flavour_mix = mix(cf["flavour_shares"], clf["flavour_shares"])
    category_mix = mix(cf["category_shares"], {})

    # ---- rhythm ---------------------------------------------------------
    if n_orders:
        hh = orders["ordered_at"].dt.hour.value_counts()
        dd = orders["ordered_at"].dt.dayofweek.value_counts()
        hours = [{"hour": h, "orders": int(hh.get(h, 0))} for h in range(24)]
        days = [{"day": DOW[d], "orders": int(dd.get(d, 0))} for d in range(7)]
        m = orders.set_index("ordered_at")
        monthly = (m.resample("MS")
                   .agg(orders=("order_id", "count"), spend=("total", "sum"),
                        attach=("has_magnum", "mean"),
                        magnum_orders=("has_magnum", "sum"),
                        magnum_units=("magnum_qty", "sum")))
        trend = [{"month": i.strftime("%Y-%m"), "orders": int(r.orders),
                  "spend": round(float(r.spend), 2), "attach": round(float(r.attach), 4),
                  "magnum_orders": int(r.magnum_orders),
                  "magnum_units": int(r.magnum_units),
                  "season": SEASON[i.month]}
                 for i, r in monthly.iterrows()]
    else:
        hours, days, trend = [], [], []

    # ---- offers this household actually saw ------------------------------
    arms: List[Dict] = []
    if len(offers):
        el = offers[offers["eligible"] == 1]
        g = el.groupby("arm_assigned").agg(n=("converted", "size"), conv=("converted", "sum"))
        base = float(g.loc["none", "conv"] / g.loc["none", "n"]) if "none" in g.index else 0.0
        for arm, r in g.iterrows():
            rate = float(r.conv) / float(r.n) if r.n else 0.0
            arms.append({"arm": arm, "n": int(r.n), "conversions": int(r.conv),
                         "rate": round(rate, 4),
                         "vs_none_pp": round((rate - base) * 100, 2) if arm != "none" else 0.0})
        arms.sort(key=lambda a: -a["n"])
    offer_history = {
        "decisions": int(len(offers)),
        "eligible": int(offers["eligible"].sum()) if len(offers) else 0,
        "shown": int(offers["shown"].sum()) if len(offers) else 0,
        "converted": int(offers["converted"].sum()) if len(offers) else 0,
        "arms": arms,
        "note": ("Arms were assigned uniformly at random, so this household's own "
                 "per-arm rates are unbiased but very small-sample. The pooled "
                 "estimates on the analysis screen are the ones to trust."),
    }

    # ---- what the policy layer would say about them right now -------------
    contacts_24h = int(st.contacts_24h.get(customer_id, 0))
    contacts_7d = int(st.contacts_7d.get(customer_id, 0))
    eligibility = {
        "consent_marketing": cf["consent_marketing"],
        "consent_personalisation": cf["consent_personalisation"],
        "contacts_24h": contacts_24h,
        "contacts_7d": contacts_7d,
        "cap_24h": 1,
        "cap_7d": pol.FREQ_CAP_PER_7D,
        "cap_hit": contacts_24h >= 1 or contacts_7d >= pol.FREQ_CAP_PER_7D,
        "suppressed": (cf["days_since_magnum"] is not None
                       and cf["days_since_magnum"] * 24 < 12),
        "suppress_hours": 12,
    }

    # ---- recent orders ---------------------------------------------------
    recent = []
    for r in orders.tail(10).iloc[::-1].itertuples():
        skus = items[items["order_id"] == r.order_id]
        recent.append({
            "order_id": r.order_id, "ordered_at": r.ordered_at.isoformat(),
            "store_id": r.store_id, "total": round(float(r.total), 2),
            "discount": round(float(r.discount), 2),
            "has_magnum": bool(r.has_magnum),
            "magnum_sku": r.magnum_sku,
            "magnum_name": cat.PRODUCT_BY_ID.get(r.magnum_sku, {}).get("name"),
            "intent_class": r.intent_class, "people": int(r.people_inferred),
            "lines": int(len(skus)), "units": int(skus["quantity"].sum()),
            "split": r.split,
        })

    top_sku = (items.groupby("sku_id")["quantity"].sum().sort_values(ascending=False)
               if len(items) else pd.Series(dtype=float))
    favourites = [{"sku_id": s, "name": cat.PRODUCT_BY_ID.get(s, {}).get("name", s),
                   "category": cat.PRODUCT_BY_ID.get(s, {}).get("category"),
                   "units": int(q)} for s, q in top_sku.head(8).items()]

    return _clean({
        "customer_id": customer_id,
        "identity": {
            "display_name": cf["display_name"], "home_area": cf["home_area"],
            "state": cf["state"], "store_id": cf["store_id"],
            "household_size_band": cf["household_size_band"],
            "cluster": {"id": clf["cluster_id"], "name": clf["name"], "short": clf["short"],
                        "customers": clf["customers"], "peak_hour": clf["peak_hour"]},
        },
        "lifetime": lifetime,
        "versus_cluster": versus,
        "cadence": cadence,
        "flavour_mix": flavour_mix,
        "category_mix": category_mix,
        "favourites": favourites,
        "hours": hours,
        "days": days,
        "trend": trend,
        "offer_history": offer_history,
        "eligibility": eligibility,
        "recent_orders": recent,
        "as_of": NOW.isoformat(),
        "held_out": ("This household's latent traits are not read here. Everything above "
                     "is derived from the same logged tables the application ranks on."),
    })
