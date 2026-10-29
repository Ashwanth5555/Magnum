"""Give the three demo households a full-season Magnum history.

The generator draws every household from the same population process, which is
correct for the population and wrong for a demo. A randomly-drawn household has
two or three Magnum orders spread thinly over the window, so the customer
screen's month-by-month chart - the one that carries the whole seasonality
argument - is a flat line hovering between zero and three with gaps in it. The
argument is true of the population and invisible in the individual, which is
the worst possible combination for a screen whose subtitle claims you can see
it one customer at a time.

So the three profiles a demo actually opens (CUS-000001..3) get their Magnum
history reshaped here: an order in every month of the window, a clear summer
peak, and a secondary bump that sits in a different season for each household
so the three screens do not read as one screen shown three times.

What this does NOT do is invent a household out of nothing. Their existing
orders, sessions, offers and items are left alone; this only adds rows, and the
added rows use the same stores, areas, splits, SKUs and price/margin arithmetic
the generator itself uses. Everything downstream - cadence, attach rate,
flavour mix, the nudge - recomputes from these tables, so the households stay
internally consistent rather than being patched at the presentation layer.

Idempotent: added rows carry an ORD-9/SES-9 id prefix and are deleted before
being rewritten, so running this twice gives the same database as running it
once.

    python3 scripts/shape_demo_seasonality.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from generator import config as cfg  # noqa: E402

DB = os.path.join(ROOT, "data", "magnum.db")

# Rows this script owns. Anything with these prefixes is ours to delete and
# rewrite; anything else in the table is the generator's and is never touched.
ORDER_PREFIX = "ORD-9"
SESSION_PREFIX = "SES-9"

FIT_END_DAY = int(cfg.DAYS * 0.72)
CAL_END_DAY = int(cfg.DAYS * 0.86)

# Magnum orders per month. Every household peaks in July-August because that is
# the thesis, but each carries its shoulder season somewhere different: the game
# night household lifts through spring as the evenings get long, the family
# planner lifts around the December holidays, and the late-solo household runs
# flatter with a mid-winter bump. Same story, three different-shaped curves.
#
# The peaks are deliberately kept near eight or nine a month. A curve topping
# out in the high teens plots beautifully and implies a household reordering
# ice cream every other day, which drags the reorder cadence under four days
# and makes every other number on the screen - due ratio, next due, the nudge's
# own timing - read as a household that never stops buying. Legibility is worth
# a lot here, but not a profile no reviewer would believe.
TARGETS = {
    "CUS-000001": {  # John Smith, game night - spring shoulder
        "2025-12": 2, "2026-01": 2, "2026-02": 1, "2026-03": 3, "2026-04": 5,
        "2026-05": 4, "2026-06": 6, "2026-07": 8, "2026-08": 9,
    },
    "CUS-000002": {  # Sarah Miller, family planner - holiday shoulder
        "2025-12": 5, "2026-01": 3, "2026-02": 2, "2026-03": 2, "2026-04": 3,
        "2026-05": 4, "2026-06": 5, "2026-07": 8, "2026-08": 7,
    },
    "CUS-000003": {  # David Brown, late solo - flatter, mid-winter bump
        "2025-12": 2, "2026-01": 3, "2026-02": 4, "2026-03": 2, "2026-04": 3,
        "2026-05": 4, "2026-06": 5, "2026-07": 7, "2026-08": 8,
    },
}

# Roughly a third of added orders carry no Magnum, so attach rate stays a
# number with something to say rather than pinning to 100%.
NON_MAGNUM_SHARE = 0.38

# Hour-of-day weights per household, matching the modal hour each screen already
# claims (game night early evening, family planner late afternoon, late solo
# genuinely late).
HOUR_PROFILE = {
    "CUS-000001": {18: 3, 19: 4, 20: 5, 21: 6, 22: 3, 17: 2, 12: 1},
    "CUS-000002": {16: 3, 17: 5, 18: 6, 19: 4, 20: 2, 11: 2, 13: 2},
    "CUS-000003": {20: 3, 21: 5, 22: 6, 23: 4, 19: 2, 0: 1, 14: 1},
}


def month_days(month: str) -> list[datetime]:
    """Days of `month` that fall inside the simulation window."""
    first = datetime.strptime(month + "-01", "%Y-%m-%d")
    days, d = [], first
    while d.month == first.month:
        if cfg.SIM_START <= d < cfg.SIM_END:
            days.append(d)
        d += timedelta(days=1)
    return days


def split_for_day(day_idx: int) -> str:
    if day_idx < FIT_END_DAY:
        return "fit"
    if day_idx < CAL_END_DAY:
        return "calibrate"
    return "holdout"


def main() -> None:
    con = sqlite3.connect(DB)

    products = pd.read_sql("SELECT * FROM products", con)
    magnum = products[products["category"] == "magnum"].set_index("sku_id")
    companions = products[products["category"].isin(["meal", "drink", "side", "dessert"])]

    who = pd.read_sql(
        "SELECT customer_id, store_id, state, home_area FROM customers "
        "WHERE customer_id IN (?, ?, ?)", con, params=list(TARGETS)).set_index("customer_id")

    # Each household's own flavour taste, read off the orders they already have
    # so the added rows extend a preference rather than inventing one.
    prior = pd.read_sql(
        "SELECT customer_id, ordered_at, has_magnum, magnum_sku FROM orders "
        "WHERE customer_id IN (?, ?, ?) AND order_id NOT LIKE ?",
        con, params=list(TARGETS) + [ORDER_PREFIX + "%"], parse_dates=["ordered_at"])

    # Clear anything a previous run added.
    con.execute("DELETE FROM order_items WHERE order_id LIKE ?", [ORDER_PREFIX + "%"])
    con.execute("DELETE FROM orders WHERE order_id LIKE ?", [ORDER_PREFIX + "%"])
    con.execute("DELETE FROM sessions WHERE session_id LIKE ?", [SESSION_PREFIX + "%"])
    con.commit()

    new_orders, new_items, new_sessions = [], [], []
    seq = 0

    for ci, (cust, targets) in enumerate(TARGETS.items()):
        rng = np.random.default_rng(cfg.SEED + 101 * (ci + 1))
        row = who.loc[cust]
        mine = prior[prior["customer_id"] == cust]

        # Flavour taste: what they already bought, else the household's cluster
        # staple. Pack sizes are drawn per order so the pack model has something
        # to learn from.
        tasted = [s for s in mine.loc[mine["has_magnum"] == 1, "magnum_sku"].dropna()]
        flavours = sorted({magnum.loc[s, "flavour"] for s in tasted if s in magnum.index})
        if not flavours:
            flavours = ["classic"]

        hours = HOUR_PROFILE[cust]
        hour_vals = np.array(list(hours))
        hour_p = np.array(list(hours.values()), dtype=float)
        hour_p /= hour_p.sum()

        for month, target in targets.items():
            days = month_days(month)
            if not days:
                continue
            have = int(((mine["ordered_at"].dt.strftime("%Y-%m") == month)
                        & (mine["has_magnum"] == 1)).sum())
            need_mag = max(0, target - have)
            need_plain = int(round(need_mag * NON_MAGNUM_SHARE / (1 - NON_MAGNUM_SHARE)))

            for k in range(need_mag + need_plain):
                is_mag = k < need_mag
                seq += 1
                day = days[int(rng.integers(0, len(days)))]
                hour = int(rng.choice(hour_vals, p=hour_p))
                minute = int(rng.integers(0, 60))
                when = day.replace(hour=hour, minute=minute)
                day_idx = (day - cfg.SIM_START).days
                split = split_for_day(day_idx)

                oid = f"{ORDER_PREFIX}{seq:05d}"
                sid = f"{SESSION_PREFIX}{seq:06d}"

                lines, subtotal, margin = [], 0.0, 0.0
                mag_sku, mag_qty = None, 0

                if is_mag:
                    flavour = flavours[int(rng.integers(0, len(flavours)))]
                    pool = magnum[magnum["flavour"] == flavour]
                    if pool.empty:
                        pool = magnum
                    mag_sku = str(pool.index[int(rng.integers(0, len(pool)))])
                    mag_qty = int(rng.integers(1, 3))
                    p = magnum.loc[mag_sku]
                    lines.append((mag_sku, "magnum", mag_qty,
                                  float(p["price"]), float(p["unit_margin"])))

                # Companion basket. A Magnum rides along with a meal about as
                # often as it is bought on its own, so the intent class is drawn
                # rather than fixed.
                n_comp = int(rng.integers(0 if is_mag else 1, 4))
                if n_comp:
                    picks = companions.sample(n_comp, random_state=int(rng.integers(0, 1 << 31)))
                    for _, c in picks.iterrows():
                        q = int(rng.integers(1, 3))
                        lines.append((str(c["sku_id"]), str(c["category"]), q,
                                      float(c["price"]), float(c["unit_margin"])))

                for sku, catg, q, price, unit_margin in lines:
                    subtotal += price * q
                    margin += unit_margin * q
                    new_items.append({
                        "order_id": oid, "sku_id": sku, "category": catg,
                        "quantity": q, "unit_price": round(price, 2),
                        "unit_margin": round(unit_margin, 2),
                        "was_recommended": int(catg == "magnum" and rng.random() < 0.55),
                    })

                discount = round(subtotal * 0.06, 2) if rng.random() < 0.22 else 0.0
                delivery_fee = 2.99
                service_fee = round(subtotal * 0.10, 2)
                total = round(subtotal - discount + delivery_fee + service_fee, 2)
                gross = round(margin, 2)
                net = round(gross - discount, 2)
                intent = ("attachment" if is_mag and n_comp else
                          "direct" if is_mag else
                          ["meal", "restock"][int(rng.integers(0, 2))])

                new_sessions.append({
                    "session_id": sid, "customer_id": cust, "store_id": row["store_id"],
                    "area_id": row["home_area"], "state": row["state"],
                    "start_time": (when - timedelta(minutes=9)).strftime("%Y-%m-%d %H:%M:%S"),
                    "day_idx": day_idx, "hour": hour, "hour_idx": day_idx * 24 + hour,
                    "assigned_policy": "baseline", "offer_arm_assigned": "none",
                    "entry_source": "organic_search", "instrumented": 0, "split": split,
                })
                new_orders.append({
                    "order_id": oid, "session_id": sid, "customer_id": cust,
                    "store_id": row["store_id"], "state": row["state"],
                    "ordered_at": when.strftime("%Y-%m-%d %H:%M:%S"), "status": "delivered",
                    "subtotal": round(subtotal, 2), "discount": discount,
                    "delivery_fee": delivery_fee, "service_fee": service_fee,
                    "total": total, "gross_margin": gross, "net_margin": net,
                    "n_lines": len(lines), "people_inferred": int(rng.integers(1, 5)),
                    "intent_class": intent, "has_magnum": int(is_mag),
                    "magnum_sku": mag_sku, "magnum_qty": mag_qty,
                    "was_substituted": 0, "split": split, "day_idx": day_idx,
                })

    pd.DataFrame(new_sessions).to_sql("sessions", con, if_exists="append", index=False)
    pd.DataFrame(new_orders).to_sql("orders", con, if_exists="append", index=False)
    pd.DataFrame(new_items).to_sql("order_items", con, if_exists="append", index=False)
    con.commit()

    check = pd.read_sql(
        "SELECT customer_id, substr(ordered_at,1,7) month, SUM(has_magnum) magnum, "
        "COUNT(*) orders FROM orders WHERE customer_id IN (?, ?, ?) "
        "GROUP BY 1, 2 ORDER BY 1, 2", con, params=list(TARGETS))
    con.close()

    print(f"added {len(new_orders)} orders / {len(new_items)} items "
          f"/ {len(new_sessions)} sessions")
    for cust, g in check.groupby("customer_id"):
        curve = " ".join(f"{m[-2:]}:{int(v)}" for m, v in zip(g["month"], g["magnum"]))
        print(f"  {cust}  {curve}")


if __name__ == "__main__":
    main()
