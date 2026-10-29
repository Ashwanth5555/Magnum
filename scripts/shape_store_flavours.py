"""Give each store a flavour identity of its own.

The generator draws a household's flavour preference from one population-wide
distribution and never conditions it on which shelf the order was filled from.
That is defensible - taste is a property of a person, not a postcode - but it
produces ten stores whose Magnum mix is 25/25/25/25 to within two points, and a
demand desk where changing the store changes nothing you can see. The screen
claims "the mix is fitted per store"; the data has to make that true.

Real dark stores do not look like this. A shelf in Greenwich and a shelf in
Astoria are stocked and re-stocked against what their own catchment actually
takes, and after a season of that the mixes are genuinely different - not
because the households are different people, but because the shelf, the
neighbourhood's meal mix and the reorder loop have had time to compound.

So this reassigns the flavour of existing Magnum order lines toward a per-store
affinity. It does NOT add or remove orders, change quantities, or move a line
between pack sizes: a 3-count stays a 3-count, a single stays a single, only
which flavour it was is redrawn. Prices, margins and the order's own money
columns are corrected by the exact delta so nothing downstream disagrees with
itself.

Idempotent. The target flavour for a line is a pure function of a stable hash
of (order_id, sku position, store) - it does not read the line's current
flavour - so a second run computes the same target it computed the first time,
and the money delta is then zero.

    python3 scripts/shape_store_flavours.py
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from collections import defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from generator import config as cfg  # noqa: E402

DB = os.path.join(ROOT, "data", "magnum.db")

# Each store's share of Magnum units by flavour. Written as a neighbourhood
# story rather than as noise, because a demo gets asked "why does Greenwich
# look like that?" and "the random seed" is not an answer:
#
#   Upper East Side  - white chocolate; the premium single is the habit here
#   Chelsea          - caramel, and late; the bar closest to a night-out dessert
#   Williamsburg     - almond, heavily; the flavour that indexes youngest
#   Astoria          - classic; the biggest family catchment, buying the known one
#   Park Slope       - classic and minis, for the same reason, one step stronger
#   White Plains     - caramel with an almond second; suburban evening dessert
#   Stamford         - white chocolate, an office-lunch shelf
#   Greenwich        - almond premium, the least classic shelf in the network
#   Norwalk          - classic, the most ordinary mix of the ten
#   New Haven        - caramel, and the latest-skewing catchment of them all
#
# Shares are held apart enough that switching store visibly re-ranks the stack -
# a leading flavour is roughly double the trailing one - without any store
# becoming a single-flavour shelf, which no real store is.
AFFINITY = {
    "ST-01": {"white": 0.40, "classic": 0.24, "almond": 0.21, "caramel": 0.15},
    "ST-02": {"caramel": 0.41, "white": 0.24, "classic": 0.19, "almond": 0.16},
    "ST-03": {"almond": 0.45, "caramel": 0.22, "white": 0.19, "classic": 0.14},
    "ST-04": {"classic": 0.42, "almond": 0.24, "white": 0.19, "caramel": 0.15},
    "ST-05": {"classic": 0.45, "caramel": 0.21, "white": 0.18, "almond": 0.16},
    "ST-06": {"caramel": 0.38, "almond": 0.26, "classic": 0.20, "white": 0.16},
    "ST-07": {"white": 0.43, "almond": 0.22, "caramel": 0.19, "classic": 0.16},
    "ST-08": {"almond": 0.41, "white": 0.27, "caramel": 0.19, "classic": 0.13},
    "ST-09": {"classic": 0.38, "white": 0.23, "caramel": 0.21, "almond": 0.18},
    "ST-10": {"caramel": 0.44, "classic": 0.22, "almond": 0.18, "white": 0.16},
}

FLAVOURS = ["almond", "caramel", "classic", "white"]


def draw(store_id: str, key: str) -> str:
    """A flavour for this line, drawn from the store's affinity by a stable hash
    of the line's own identity. Deterministic across runs and across machines -
    `hash()` is salted per process and would not be."""
    h = hashlib.sha256(f"{cfg.SEED}|{store_id}|{key}".encode()).digest()
    u = int.from_bytes(h[:8], "big") / float(1 << 64)
    acc = 0.0
    shares = AFFINITY[store_id]
    for f in FLAVOURS:
        acc += shares[f]
        if u < acc:
            return f
    return FLAVOURS[-1]


# Days of sales the shelf is re-balanced against. The generator replenishes off
# a lagged seven-day average; four weeks is the same idea with the week-to-week
# noise taken out, which is what a shelf that has been restocked forty times
# would have converged to.
RESHELVE_WINDOW_DAYS = 28


def reshelve(con) -> None:
    """Re-balance the final inventory snapshot to each store's own mix.

    Phase one changes what each catchment buys; the shelf has to follow, or the
    demand desk shows a caramel store stocked mostly with white chocolate and
    the reviewer is right to call it. The generator's replenishment rule already
    says what the shelf should look like - a multiple of recent sales - it just
    computed it from one network-wide popularity vector instead of per store.

    So the last snapshot is re-allocated across SKUs in proportion to that
    store's own trailing four weeks of unit sales. Each store's TOTAL on-hand is
    preserved exactly: this moves units between SKUs on one shelf, it does not
    conjure stock, and network on-hand is unchanged. Whether a store is short
    therefore still comes out of the simulation rather than being set here -
    what changes is which SKU it is short of.
    """
    # Resolved once. Left inline in the UPDATE it is a full scan of a
    # half-million-row table per row updated, which turns eighty writes into
    # minutes of CPU.
    latest = con.execute("SELECT MAX(snapshot_time) FROM inventory").fetchone()[0]
    snap = pd.read_sql(
        "SELECT store_id, sku_id, on_hand FROM inventory WHERE snapshot_time = ?",
        con, params=[latest])
    end = pd.read_sql("SELECT MAX(ordered_at) t FROM orders", con)["t"].iloc[0]
    recent = pd.read_sql(
        "SELECT o.store_id, i.sku_id, SUM(i.quantity) units FROM order_items i "
        "JOIN orders o ON o.order_id = i.order_id WHERE i.category = 'magnum' "
        "AND o.ordered_at >= datetime(?, ?) GROUP BY 1, 2",
        con, params=[end, f"-{RESHELVE_WINDOW_DAYS} days"])

    weights = {(r.store_id, r.sku_id): float(r.units) for r in recent.itertuples()}
    rows = []
    for store_id, g in snap.groupby("store_id"):
        total = int(g["on_hand"].sum())
        skus = list(g["sku_id"])
        # A one-unit floor per SKU: a shelf that has genuinely sold none of a
        # flavour still carries a facing of it, and a zero here would read as a
        # stockout the simulation never had.
        w = {s: max(0.05, weights.get((store_id, s), 0.0)) for s in skus}
        wsum = sum(w.values())
        raw = {s: (total - len(skus)) * w[s] / wsum for s in skus}
        alloc = {s: 1 + int(raw[s]) for s in skus}
        # Largest-remainder, so the units that rounding drops go to the SKUs
        # that were closest to earning one and the total lands exactly.
        short = total - sum(alloc.values())
        for s in sorted(skus, key=lambda s: raw[s] - int(raw[s]), reverse=True)[:short]:
            alloc[s] += 1
        rows += [(alloc[s], store_id, s) for s in skus]

    con.executemany(
        "UPDATE inventory SET on_hand = ?, is_stockout = (? = 0) "
        "WHERE snapshot_time = ? AND store_id = ? AND sku_id = ?",
        [(n, n, latest, st, sk) for n, st, sk in rows])
    con.commit()
    print(f"re-shelved {len(rows)} SKU slots across {snap['store_id'].nunique()} stores")


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    products = pd.read_sql("SELECT * FROM products WHERE category = 'magnum'", con)
    # One SKU per (flavour, pack size). Classic has no 3-count - its multipack is
    # the 6-count mini - so packs are matched on "is it a multipack", not on the
    # literal pack label, or every classic multi would have nowhere to land.
    by_slot: dict[tuple[str, bool], str] = {}
    for r in products.itertuples():
        by_slot[(r.flavour, r.pack_size != "single")] = r.sku_id
    price = {r.sku_id: (float(r.price), float(r.unit_margin)) for r in products.itertuples()}
    is_multi = {r.sku_id: r.pack_size != "single" for r in products.itertuples()}

    lines = pd.read_sql(
        "SELECT i.rowid rid, i.order_id, i.sku_id, i.quantity, i.unit_price, i.unit_margin, "
        "o.store_id FROM order_items i JOIN orders o ON o.order_id = i.order_id "
        "WHERE i.category = 'magnum' ORDER BY i.order_id, i.rowid", con)

    seen: dict[str, int] = defaultdict(int)
    item_updates, order_delta, magnum_sku = [], defaultdict(lambda: [0.0, 0.0]), {}
    changed = 0

    for r in lines.itertuples():
        if r.store_id not in AFFINITY:
            continue
        pos = seen[r.order_id]
        seen[r.order_id] += 1
        want = draw(r.store_id, f"{r.order_id}#{pos}")
        new_sku = by_slot.get((want, is_multi[r.sku_id]), r.sku_id)

        new_price, new_margin = price[new_sku]
        d_sub = (new_price - float(r.unit_price)) * int(r.quantity)
        d_mar = (new_margin - float(r.unit_margin)) * int(r.quantity)
        if new_sku != r.sku_id or abs(d_sub) > 1e-9:
            changed += new_sku != r.sku_id
            item_updates.append((new_sku, round(new_price, 2), round(new_margin, 2), r.rid))
            order_delta[r.order_id][0] += d_sub
            order_delta[r.order_id][1] += d_mar
        # orders.magnum_sku names the first Magnum line of the order.
        if pos == 0:
            magnum_sku[r.order_id] = new_sku

    cur = con.cursor()
    cur.executemany(
        "UPDATE order_items SET sku_id = ?, unit_price = ?, unit_margin = ? WHERE rowid = ?",
        item_updates)
    cur.executemany("UPDATE orders SET magnum_sku = ? WHERE order_id = ?",
                    [(v, k) for k, v in magnum_sku.items()])
    # The service fee is a percentage of subtotal, so a changed subtotal changes
    # it, and total has to be rebuilt from the parts rather than nudged.
    cur.executemany(
        "UPDATE orders SET subtotal = ROUND(subtotal + ?, 2), "
        "service_fee = ROUND((subtotal + ?) * 0.10, 2), "
        "gross_margin = ROUND(gross_margin + ?, 2), "
        "net_margin = ROUND(net_margin + ?, 2), "
        "total = ROUND((subtotal + ?) - discount + delivery_fee "
        "              + ROUND((subtotal + ?) * 0.10, 2), 2) "
        "WHERE order_id = ?",
        [(d[0], d[0], d[1], d[1], d[0], d[0], oid) for oid, d in order_delta.items()])
    con.commit()

    reshelve(con)

    check = pd.read_sql(
        "SELECT o.store_id, p.flavour, SUM(i.quantity) units FROM order_items i "
        "JOIN orders o ON o.order_id = i.order_id JOIN products p ON p.sku_id = i.sku_id "
        "WHERE i.category = 'magnum' GROUP BY 1, 2", con)
    con.close()

    wide = check.pivot(index="store_id", columns="flavour", values="units").fillna(0)
    print(f"{changed} of {len(lines)} magnum lines re-flavoured\n")
    print((wide.div(wide.sum(axis=1), axis=0) * 100).round(1).to_string())


if __name__ == "__main__":
    main()
