"""Data access and feature building.

Everything the policies need is derived once at startup from `data/magnum.db`
and cached in memory: personal history per customer, peer aggregates per
cluster, the uplift table fitted on the FIT split only, latest inventory, and
per-store demand rates.

Two tables are deliberately unreachable from here: `latent_traits` and
`ground_truth`. Rule 5 of section 5.5 keeps them out of the application. They
are used in one place only - the validation panel - and that comparison is
computed server-side and returned as summary statistics, never as rows.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DB = os.path.join(DATA, "magnum.db")

import sys
sys.path.insert(0, ROOT)
from magnum_core import catalog as cat            # noqa: E402
from magnum_core import context as cx             # noqa: E402
from magnum_core import profiles as pf            # noqa: E402
from generator import config as gcfg              # noqa: E402

HELD_OUT_TABLES = {"latent_traits", "ground_truth"}
BROWSABLE = ["customers", "stores", "products", "contexts", "sessions", "events",
             "orders", "order_items", "inventory", "offers", "notifications", "forecasts"]

NOW = gcfg.SIM_END          # the demo's "current time"


def _con():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


# Below this many orders a slice has nothing to say and every lift is held at 1.0.
MIN_PROFILE_ORDERS = 400


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.ready = False
        self.load()

    # ------------------------------------------------------------------
    def load(self):
        if not os.path.exists(DB):
            raise RuntimeError("data/magnum.db not found - run: python3 generator/generate.py")
        con = _con()
        t0 = datetime.now()

        self.quality = json.load(open(os.path.join(DATA, "data_quality.json")))
        self.customers = pd.read_sql(
            "SELECT customer_id, display_name, home_area, state, zip, store_id, "
            "household_size_band, peer_cluster, consent_marketing, consent_personalisation, "
            "is_demo_profile FROM customers", con)
        self.customers_by_id = self.customers.set_index("customer_id")

        orders = pd.read_sql(
            "SELECT order_id, customer_id, store_id, state, ordered_at, total, discount, "
            "gross_margin, has_magnum, magnum_sku, magnum_qty, intent_class, people_inferred, "
            "was_substituted, split, day_idx FROM orders", con, parse_dates=["ordered_at"])
        items = pd.read_sql(
            "SELECT order_id, sku_id, category, quantity FROM order_items", con)
        self.orders = orders

        self._build_customer_features(orders, items)
        self._build_cluster_features(orders, items)
        self._build_uplift_table(con)
        self._build_pair_table(con)
        self._build_inventory(con)
        self._build_rates(con)
        self._build_contacts(con)
        self._build_occasion_profile(con)
        self.contexts_meta = pd.read_sql(
            "SELECT store_id, MIN(timestamp) a, MAX(timestamp) b, COUNT(*) n FROM contexts "
            "GROUP BY store_id", con)
        con.close()
        self.loaded_in = (datetime.now() - t0).total_seconds()
        self.ready = True

    # ------------------------------------------------------------------
    def _build_customer_features(self, orders, items):
        mag = orders[orders["has_magnum"] == 1].sort_values(["customer_id", "ordered_at"])
        g = mag.groupby("customer_id")

        gaps = mag.groupby("customer_id")["ordered_at"].apply(
            lambda s: s.diff().dt.total_seconds().div(86400).mean())
        last = g["ordered_at"].max()
        n_mag = g.size()
        units = mag.assign(units=mag["magnum_qty"] * mag["magnum_sku"].map(
            lambda s: cat.PACK_UNITS.get(s, 1)))
        avg_units = units.groupby("customer_id")["units"].mean()
        usual_hour = g["ordered_at"].apply(lambda s: int(s.dt.hour.mode().iloc[0]) if len(s) else 20)
        disc_resp = g["discount"].apply(lambda s: float((s > 0).mean()))

        mag["flavour"] = mag["magnum_sku"].map(lambda s: cat.PRODUCT_BY_ID.get(s, {}).get("flavour"))
        fl = (mag.groupby(["customer_id", "flavour"]).size().rename("n").reset_index())
        fl["share"] = fl["n"] / fl.groupby("customer_id")["n"].transform("sum")
        flavour_map: Dict[str, Dict[str, float]] = {}
        for r in fl.itertuples():
            flavour_map.setdefault(r.customer_id, {})[r.flavour] = round(float(r.share), 4)

        mag["is_pack"] = mag["magnum_sku"].isin(cat.MAGNUM_PACKS)
        pack_share = mag.groupby("customer_id")["is_pack"].mean()

        allg = orders.groupby("customer_id")
        n_orders = allg.size()
        spend = allg["total"].sum()
        last_order = allg["ordered_at"].max()

        it = items.merge(orders[["order_id", "customer_id"]], on="order_id", how="left")
        cs = it.groupby(["customer_id", "category"])["quantity"].sum().rename("q").reset_index()
        cs["share"] = cs["q"] / cs.groupby("customer_id")["q"].transform("sum")
        cat_map: Dict[str, Dict[str, float]] = {}
        for r in cs.itertuples():
            cat_map.setdefault(r.customer_id, {})[r.category] = round(float(r.share), 4)

        cluster_cadence = {c["cluster_id"]: c["cadence_days"] for c in pf.CLUSTERS}
        feats: Dict[str, Dict] = {}
        for cid, row in self.customers_by_id.iterrows():
            lm = last.get(cid)
            cadence = gaps.get(cid)
            if cadence is None or (isinstance(cadence, float) and math.isnan(cadence)):
                cadence = cluster_cadence.get(row["peer_cluster"], 12.0)
            days_since = (NOW - lm).total_seconds() / 86400.0 if pd.notna(lm) else None
            feats[cid] = {
                "customer_id": cid,
                "display_name": row["display_name"],
                "peer_cluster": row["peer_cluster"],
                "home_area": row["home_area"],
                "state": row["state"],
                "store_id": row["store_id"],
                "household_size_band": row["household_size_band"],
                "consent_marketing": bool(row["consent_marketing"]),
                "consent_personalisation": bool(row["consent_personalisation"]),
                "orders": int(n_orders.get(cid, 0)),
                "spend": round(float(spend.get(cid, 0.0)), 2),
                "magnum_orders": int(n_mag.get(cid, 0)),
                "last_magnum_at": lm.isoformat() if pd.notna(lm) else None,
                "last_order_at": last_order.get(cid).isoformat() if pd.notna(last_order.get(cid)) else None,
                "days_since_magnum": round(days_since, 2) if days_since is not None else None,
                "cadence_days": round(float(cadence), 2),
                "due_ratio": round(days_since / float(cadence), 3) if days_since is not None else 0.0,
                "avg_units": round(float(avg_units.get(cid, 1.5)), 2),
                "usual_hour": int(usual_hour.get(cid, 20)),
                "pack_share": round(float(pack_share.get(cid, 0.0)), 3),
                "discount_response": round(float(disc_resp.get(cid, 0.0)), 3),
                "flavour_shares": flavour_map.get(cid, {}),
                "category_shares": cat_map.get(cid, {}),
            }
        self.customer_features = feats

    # ------------------------------------------------------------------
    def _build_cluster_features(self, orders, items):
        o = orders.merge(self.customers[["customer_id", "peer_cluster"]], on="customer_id")
        mag = o[o["has_magnum"] == 1].copy()
        mag["flavour"] = mag["magnum_sku"].map(lambda s: cat.PRODUCT_BY_ID.get(s, {}).get("flavour"))
        mag["units"] = mag["magnum_qty"] * mag["magnum_sku"].map(lambda s: cat.PACK_UNITS.get(s, 1))
        mag["is_pack"] = mag["magnum_sku"].isin(cat.MAGNUM_PACKS)

        it = items.merge(o[["order_id", "peer_cluster"]], on="order_id", how="left")
        out: Dict[str, Dict] = {}
        for cl in pf.CLUSTER_IDS:
            m = mag[mag["peer_cluster"] == cl]
            i = it[(it["peer_cluster"] == cl) & (it["category"] != "magnum")]
            fl = m.groupby("flavour").size()
            sk = i.groupby("sku_id")["quantity"].sum()
            hours = m["ordered_at"].dt.hour.value_counts().sort_index()
            meta = pf.CLUSTER_BY_ID[cl]
            out[cl] = {
                "cluster_id": cl,
                "name": meta["name"],
                "short": meta["short"],
                "customers": int((self.customers["peer_cluster"] == cl).sum()),
                "magnum_orders": int(len(m)),
                "attach_rate": round(float((o[o["peer_cluster"] == cl]["has_magnum"] == 1).mean()), 4),
                "avg_units": round(float(m["units"].mean()) if len(m) else 1.6, 2),
                "pack_share": round(float(m["is_pack"].mean()) if len(m) else 0.3, 3),
                "flavour_shares": {k: round(float(v / fl.sum()), 4) for k, v in fl.items()} if len(fl) else {},
                "sku_shares": {k: round(float(v / sk.sum()), 4) for k, v in sk.items()} if len(sk) else {},
                "hour_histogram": {int(k): int(v) for k, v in hours.items()},
                "peak_hour": int(hours.idxmax()) if len(hours) else 20,
                "avg_people": round(float(o[o["peer_cluster"] == cl]["people_inferred"].mean()), 2),
                # Share of the cluster's orders that carried any discount. The
                # customer view compares a household's discount response against
                # this, and a comparison needs both halves.
                "discount_share": round(float((o[o["peer_cluster"] == cl]["discount"] > 0).mean()), 4),
                "cadence_days": float(meta["cadence_days"]),
            }
        self.cluster_features = out

    # ------------------------------------------------------------------
    def _build_uplift_table(self, con):
        """Fitted on the FIT split only. This is the V1 'uplift proxy' of §6.2:
        a difference of randomised means per arm, per cluster, shrunk toward the
        pooled arm effect so a thin cell cannot swing a live decision."""
        df = pd.read_sql(
            "SELECT o.arm_assigned, o.cluster, o.converted, o.eligible, s.split "
            "FROM offers o JOIN sessions s ON s.session_id = o.session_id "
            "WHERE o.eligible = 1", con)
        fit = df[df["split"] == "fit"]
        self.uplift_fit_rows = int(len(fit))

        pooled = fit.groupby("arm_assigned")["converted"].mean()
        base_all = float(pooled.get("none", 0.0))
        by_cluster = fit.groupby(["arm_assigned", "cluster"])["converted"].agg(["mean", "count"])
        base_cluster = {c: float(by_cluster.loc[("none", c), "mean"])
                        for c in pf.CLUSTER_IDS if ("none", c) in by_cluster.index}

        table: Dict[str, Dict[str, float]] = {}
        detail: List[Dict] = []
        for arm in pooled.index:
            pooled_up = float(pooled[arm]) - base_all
            table[arm] = {"__all__": round(pooled_up, 5)}
            for cl in pf.CLUSTER_IDS:
                key = (arm, cl)
                if key not in by_cluster.index:
                    table[arm][cl] = round(pooled_up, 5)
                    continue
                raw = float(by_cluster.loc[key, "mean"]) - base_cluster.get(cl, base_all)
                n = float(by_cluster.loc[key, "count"])
                # James-Stein style shrinkage: a cell needs ~400 decisions before
                # it is trusted over the pooled effect.
                w = n / (n + 400.0)
                shrunk = w * raw + (1 - w) * pooled_up
                table[arm][cl] = round(shrunk, 5)
                detail.append({"arm": arm, "cluster": cl, "raw_uplift_pp": round(raw * 100, 3),
                               "shrunk_uplift_pp": round(shrunk * 100, 3), "n": int(n),
                               "shrinkage_weight": round(w, 3)})
        self.uplift_table = table
        self.uplift_detail = detail

    # ------------------------------------------------------------------
    def _build_pair_table(self, con):
        """What each non-Magnum item does to the Magnum that rides with it.

        Two effects, both measured off the order log rather than asserted by a
        merchandiser: which flavour the pairing pulls toward, and how many bars
        the basket ends up carrying. The generator planted the structure and the
        aggregation finds it - which is the point, because it means the number
        on the screen is a number from the data and not a rule in the code.

        Held to n >= 120 co-purchase baskets. Below that the flavour split of a
        few dozen orders is noise, and a rail that reorders itself on noise is
        worse than a rail that ignores the signal.
        """
        oi = pd.read_sql("SELECT order_id, sku_id, quantity FROM order_items", con)
        pb = cat.PRODUCT_BY_ID
        oi["cat"] = oi.sku_id.map(lambda s: pb[s]["category"])
        oi["flavour"] = oi.sku_id.map(lambda s: pb[s]["flavour"])
        oi["units"] = [pb[r.sku_id]["units_in_pack"] * r.quantity for r in oi.itertuples()]

        mag = oi[oi.cat == "magnum"]
        other = oi[oi.cat != "magnum"]
        if mag.empty or other.empty:
            self.pair_table, self.pair_base = {}, {}
            return

        base_counts = mag.groupby("flavour").order_id.nunique()
        base = (base_counts / base_counts.sum()).to_dict()
        mag_units = mag.groupby("order_id").units.sum()
        base_units = float(mag_units.mean())

        joined = other[["order_id", "sku_id"]].merge(
            mag[["order_id", "flavour"]], on="order_id")
        counts = joined.groupby(["sku_id", "flavour"]).order_id.nunique().unstack(fill_value=0)
        totals = counts.sum(axis=1)
        units_by_sku = other[["order_id", "sku_id"]].merge(
            mag_units.rename("u"), on="order_id").groupby("sku_id").u.mean()

        table = {}
        for sku in counts.index:
            n = int(totals.loc[sku])
            if n < 120:
                continue
            lift = {f: round(float(counts.loc[sku, f]) / n / base[f], 3)
                    for f in counts.columns if base.get(f)}
            top = max(lift, key=lift.get)
            table[sku] = {
                "n": n,
                "flavour_lift": lift,
                "top_flavour": top,
                "top_lift": lift[top],
                "units_ratio": round(float(units_by_sku.get(sku, base_units)) / base_units, 3),
                "avg_units": round(float(units_by_sku.get(sku, base_units)), 2),
            }

        # A category rolls up its members weighted by how often each appears, so
        # browsing "Meals" carries the aisle's average pull rather than whichever
        # SKU happens to sort first.
        by_cat = {}
        for sku, row in table.items():
            by_cat.setdefault(pb[sku]["category"], []).append(row)
        cat_table = {}
        for c, rows in by_cat.items():
            tot = sum(r["n"] for r in rows)
            flavours = {f: round(sum(r["flavour_lift"].get(f, 1.0) * r["n"] for r in rows) / tot, 3)
                        for f in base}
            top = max(flavours, key=flavours.get)
            cat_table[c] = {
                "n": tot, "flavour_lift": flavours, "top_flavour": top,
                "top_lift": flavours[top],
                "units_ratio": round(sum(r["units_ratio"] * r["n"] for r in rows) / tot, 3),
            }

        self.pair_table = table
        self.pair_by_category = cat_table
        self.pair_base = {"flavour_mix": {k: round(v, 4) for k, v in base.items()},
                          "avg_units": round(base_units, 3)}

    def _build_inventory(self, con):
        last = pd.read_sql(
            "SELECT store_id, sku_id, on_hand, reserved, inbound, waste, snapshot_time "
            "FROM inventory WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM inventory)", con)
        self.inventory_time = last["snapshot_time"].iloc[0] if len(last) else None
        self.stock: Dict[str, Dict[str, int]] = {}
        self.inbound: Dict[str, Dict[str, int]] = {}
        for r in last.itertuples():
            self.stock.setdefault(r.store_id, {})[r.sku_id] = int(r.on_hand)
            self.inbound.setdefault(r.store_id, {})[r.sku_id] = int(r.inbound)
        self.stock_baseline = {s: dict(v) for s, v in self.stock.items()}

    # ------------------------------------------------------------------
    def _build_rates(self, con):
        """Units per unit-of-demand-index-hour, per store and SKU. This is the
        'seasonal hourly baseline' half of the V1 demand model."""
        units = pd.read_sql(
            "SELECT o.store_id, i.sku_id, SUM(i.quantity) units FROM order_items i "
            "JOIN orders o ON o.order_id = i.order_id WHERE i.category = 'magnum' "
            "GROUP BY o.store_id, i.sku_id", con)
        idx = pd.read_sql("SELECT store_id, SUM(absolute_index) s FROM contexts GROUP BY store_id", con)
        m = units.merge(idx, on="store_id")
        m["rate"] = m["units"] / m["s"]
        self.rates = {(r.store_id, r.sku_id): float(r.rate) for r in m.itertuples()}
        self.observed_units = {(r.store_id, r.sku_id): int(r.units) for r in m.itertuples()}

    # ------------------------------------------------------------------
    def _build_contacts(self, con):
        df = pd.read_sql(
            "SELECT customer_id, decided_at FROM offers WHERE shown = 1", con,
            parse_dates=["decided_at"])
        cut24 = NOW - timedelta(hours=24)
        cut7 = NOW - timedelta(days=7)
        self.contacts_24h = df[df["decided_at"] >= cut24].groupby("customer_id").size().to_dict()
        self.contacts_7d = df[df["decided_at"] >= cut7].groupby("customer_id").size().to_dict()

    # ------------------------------------------------------------------
    def _build_occasion_profile(self, con):
        """What the day of the week and the match window actually do to a basket.

        Both of these were serving as pricing inputs and nothing else, which is
        backwards: the log has plenty to say about them. Joining every Magnum
        order to the hourly context panel it was placed in gives a measured
        answer for each - what share of orders were packs rather than singles,
        how many bars came home, and which flavours over- and under-index.

        Everything here is a *lift* against the same quantity measured over the
        whole log, so a value of 1.0 means "this day is unremarkable on this
        dimension" and the serving policy leaves it alone. Nothing is asserted;
        if the log has no opinion, the lift is 1.0 and no term fires.
        """
        mag = pd.read_sql(
            "SELECT o.order_id, o.store_id, o.ordered_at, o.magnum_sku, o.magnum_qty "
            "FROM orders o WHERE o.has_magnum = 1", con, parse_dates=["ordered_at"])
        ctx = pd.read_sql(
            "SELECT store_id, timestamp, day_of_week, in_game_window FROM contexts",
            con, parse_dates=["timestamp"])
        mag["timestamp"] = mag["ordered_at"].dt.floor("h")
        m = mag.merge(ctx, on=["store_id", "timestamp"], how="inner")

        packs = set(cat.MAGNUM_PACKS)
        pack_of = {p["sku_id"]: int(p["units_in_pack"]) for p in cat.PRODUCTS
                   if p["category"] == "magnum"}
        flav_of = {p["sku_id"]: p.get("flavour") or "" for p in cat.PRODUCTS
                   if p["category"] == "magnum"}
        m = m[m["magnum_sku"].isin(pack_of)]
        m["is_pack"] = m["magnum_sku"].isin(packs)
        m["bars"] = m["magnum_sku"].map(pack_of) * m["magnum_qty"]
        m["flavour"] = m["magnum_sku"].map(flav_of)

        base_pack = float(m["is_pack"].mean())
        base_bars = float(m["bars"].mean())
        base_flav = m["flavour"].value_counts(normalize=True).to_dict()

        def slice_profile(sub):
            n = int(len(sub))
            if n < MIN_PROFILE_ORDERS:
                return {"n": n, "pack_lift": 1.0, "bars_lift": 1.0, "flavour_lift": {}}
            fl = sub["flavour"].value_counts(normalize=True).to_dict()
            return {
                "n": n,
                "pack_lift": round(float(sub["is_pack"].mean()) / base_pack, 4) if base_pack else 1.0,
                "bars_lift": round(float(sub["bars"].mean()) / base_bars, 4) if base_bars else 1.0,
                "flavour_lift": {f: round(fl.get(f, 0.0) / base_flav[f], 4)
                                 for f in base_flav if base_flav[f] > 0},
            }

        by_day = {int(d): slice_profile(sub) for d, sub in m.groupby("day_of_week")}
        by_game = {int(g): slice_profile(sub) for g, sub in m.groupby("in_game_window")}
        self.occasion_profile = {
            "by_day": by_day,
            "game": by_game.get(1, {"n": 0, "pack_lift": 1.0, "bars_lift": 1.0, "flavour_lift": {}}),
            "no_game": by_game.get(0, {"n": 0, "pack_lift": 1.0, "bars_lift": 1.0, "flavour_lift": {}}),
            "base": {"pack_share": round(base_pack, 4), "bars": round(base_bars, 4),
                     "flavour_share": {k: round(v, 4) for k, v in base_flav.items()},
                     "n": int(len(m))},
        }

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------
    def features(self, customer_id: str) -> Optional[Dict]:
        return self.customer_features.get(customer_id)

    def cluster(self, cluster_id: str) -> Optional[Dict]:
        return self.cluster_features.get(cluster_id)

    def store_stock(self, store_id: str) -> Dict[str, int]:
        return dict(self.stock.get(store_id, {}))

    def rate(self, store_id: str, sku_id: str) -> float:
        return self.rates.get((store_id, sku_id), 0.05)

    def reset(self):
        """Restore the deterministic golden scenario (§8.3 /api/demo/reset)."""
        with self.lock:
            self.stock = {s: dict(v) for s, v in self.stock_baseline.items()}
        return {"scenario_id": "G1", "reset_at": datetime.utcnow().isoformat() + "Z"}


_store: Optional[Store] = None
# Guards construction, not use. Without it every request that arrives before the
# first build finishes starts a build of its own: `_store is None` is still true
# for all of them. Locally that window is 2.5s and nothing is knocking, so it
# never showed. On App Service the warm-up thread and each health poll each got
# their own 579 MB Store, the instance went to 2.5 GB, and no build ever won.
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:                 # re-check: another thread may have built it
                _store = Store()
    return _store


def store_if_built() -> Optional[Store]:
    """The store if it is already built, else None. Never builds one.

    For liveness checks, which must answer while the build is still running
    rather than queue behind it.
    """
    return _store
