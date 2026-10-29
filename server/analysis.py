"""Offline analysis over the generated log.

Every number the Analysis screen shows is computed here from the same tables
the application reads. The one exception is `validation`, which is the only
place `ground_truth` is touched, and it returns summary statistics only -
never rows, never a per-decision score the UI could act on.
"""
from __future__ import annotations

import math
import os
import sqlite3
from functools import lru_cache
from typing import Dict, List

import numpy as np
import pandas as pd

from .store import DB, get_store, _con
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from magnum_core import catalog as cat        # noqa: E402
from magnum_core import policies as pol       # noqa: E402
from magnum_core import profiles as pf        # noqa: E402

ARMS = ["none", "reminder", "flavour_discovery", "multipack_value", "voucher20"]
PROPENSITY = 1.0 / len(ARMS)          # the logging policy randomised uniformly
MAGNUM_MARGIN_REF = 1.55              # mean unit margin, used for EIC ranking


def _offers() -> pd.DataFrame:
    con = _con()
    df = pd.read_sql(
        "SELECT o.*, s.split FROM offers o JOIN sessions s ON s.session_id = o.session_id", con,
        parse_dates=["decided_at"])
    con.close()
    return df


@lru_cache(maxsize=1)
def overview() -> Dict:
    con = _con()
    q = lambda s: con.execute(s).fetchone()
    orders, revenue, margin, mag_orders, mag_units = q(
        "SELECT COUNT(*), SUM(total), SUM(gross_margin), SUM(has_magnum), "
        "SUM(magnum_qty * CASE magnum_sku WHEN 'MAG-ALM-3' THEN 3 WHEN 'MAG-CAR-3' THEN 3 "
        "WHEN 'MAG-WHT-3' THEN 3 WHEN 'MAG-MIN-6' THEN 6 "
        "ELSE 1 END) FROM orders")
    sessions, = q("SELECT COUNT(*) FROM sessions")
    events, = q("SELECT COUNT(*) FROM events")
    customers, = q("SELECT COUNT(*) FROM customers")
    stockout_hours, total_rows = q("SELECT SUM(is_stockout), COUNT(*) FROM inventory")
    waste, = q("SELECT SUM(waste) FROM inventory")

    by_state = pd.read_sql(
        "SELECT state, COUNT(*) orders, SUM(has_magnum) magnum_orders, SUM(total) revenue "
        "FROM orders GROUP BY state", con)
    by_intent = pd.read_sql(
        "SELECT intent_class, COUNT(*) orders, AVG(has_magnum) attach, AVG(total) basket "
        "FROM orders GROUP BY intent_class", con)
    daily = pd.read_sql(
        "SELECT day_idx, COUNT(*) orders, SUM(has_magnum) magnum_orders, "
        "SUM(gross_margin) margin FROM orders GROUP BY day_idx ORDER BY day_idx", con)
    hourly = pd.read_sql(
        "SELECT CAST(strftime('%H', ordered_at) AS INT) hour, COUNT(*) orders, "
        "AVG(has_magnum) attach FROM orders GROUP BY hour ORDER BY hour", con)
    flavours = pd.read_sql(
        "SELECT magnum_sku sku_id, COUNT(*) orders FROM orders WHERE has_magnum = 1 "
        "GROUP BY magnum_sku ORDER BY orders DESC", con)
    con.close()

    daily["attach"] = daily["magnum_orders"] / daily["orders"]
    flavours["name"] = flavours["sku_id"].map(lambda s: cat.PRODUCT_BY_ID[s]["name"])
    return {
        "sessions": int(sessions), "orders": int(orders), "events": int(events),
        "customers": int(customers),
        "revenue": round(float(revenue), 2), "gross_margin": round(float(margin), 2),
        "magnum_orders": int(mag_orders), "magnum_units": int(mag_units),
        "attach_rate": round(float(mag_orders) / float(orders), 4),
        "session_to_order": round(float(orders) / float(sessions), 4),
        "avg_basket": round(float(revenue) / float(orders), 2),
        "stockout_rate": round(float(stockout_hours) / float(total_rows), 4),
        "waste_units": int(waste),
        "by_state": by_state.to_dict("records"),
        "by_intent": by_intent.round(4).to_dict("records"),
        "daily": daily.round(4).to_dict("records"),
        "hourly": hourly.round(4).to_dict("records"),
        "flavours": flavours.to_dict("records"),
    }


def _wilson_diff_ci(x1, n1, x0, n0, z=1.96):
    """Normal-approximation CI on a difference of two randomised proportions."""
    if n1 == 0 or n0 == 0:
        return 0.0, 0.0, 0.0
    p1, p0 = x1 / n1, x0 / n0
    se = math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    d = p1 - p0
    return d, d - z * se, d + z * se


@lru_cache(maxsize=1)
def uplift(split: str = "holdout") -> Dict:
    df = _offers()
    df = df[df["eligible"] == 1]
    if split != "all":
        df = df[df["split"] == split]
    base = df[df["arm_assigned"] == "none"]
    x0, n0 = int(base["converted"].sum()), int(len(base))
    rows = []
    for arm in ARMS:
        a = df[df["arm_assigned"] == arm]
        if not len(a):
            continue
        x1, n1 = int(a["converted"].sum()), int(len(a))
        d, lo, hi = _wilson_diff_ci(x1, n1, x0, n0)
        reward = float(a["decision_reward"].mean())
        base_reward = float(base["decision_reward"].mean())
        rows.append({
            "arm": arm,
            "n": n1,
            "conversions": x1,
            "attach_rate": round(x1 / n1, 4),
            "uplift_pp": round(d * 100, 3),
            "ci_low_pp": round(lo * 100, 3),
            "ci_high_pp": round(hi * 100, 3),
            "significant": bool(arm != "none" and (lo > 0 or hi < 0)),
            "reward_per_decision": round(reward, 4),
            "reward_vs_none": round(reward - base_reward, 4),
            "discount_cost_per_decision": round(float(a["discount_value"].mean()), 4),
            "contact_cost_per_decision": round(float(a["contact_cost"].mean()), 4),
        })
    rows.sort(key=lambda r: -r["reward_vs_none"])
    st = get_store()
    return {
        "split": split, "n_decisions": int(len(df)),
        "baseline_attach": round(x0 / n0, 4) if n0 else 0.0,
        "arms": rows,
        "cells": st.uplift_detail,
        "note": ("Arms were randomised uniformly at 20% each, so a difference of means is "
                 "an unbiased uplift estimate. Suppressed decisions are excluded on both "
                 "sides, which keeps the comparison like-for-like."),
    }


def _eic(arm: str, up: float) -> float:
    lib = {o["arm"]: o for o in pol.OFFER_LIBRARY}
    if arm == "none":
        return 0.0
    o = lib[arm]
    disc = o["discount_pct"] * (MAGNUM_MARGIN_REF / 0.42)      # discount on the price, not margin
    return up * (MAGNUM_MARGIN_REF - disc) - o["contact_cost"]


@lru_cache(maxsize=1)
def policy_eval() -> Dict:
    """Inverse-propensity scoring on the holdout split.

    Because the log randomised arms with known probability 0.2, an alternative
    policy is scored by keeping the decisions where it happens to agree with the
    log and weighting them by 1/0.2. No model of the reward is involved, so a
    bad policy cannot hide behind a bad model.
    """
    st = get_store()
    df = _offers()
    df = df[(df["eligible"] == 1) & (df["split"] == "holdout")].copy()
    ut = st.uplift_table

    # Each policy's choice depends only on the cluster, so the decision rule is
    # a six-entry lookup rather than a row-wise apply. The apply version took
    # twelve seconds on the holdout split; this is instant.
    def best(score):
        table = {}
        for cl in pf.CLUSTER_IDS:
            arm, val = "none", 0.0
            for a in ARMS:
                u = ut.get(a, {}).get(cl, ut.get(a, {}).get("__all__", 0.0))
                v = score(a, u)
                if v > val:
                    arm, val = a, v
            table[cl] = arm
        return table

    policies = {
        "do_nothing": {cl: "none" for cl in pf.CLUSTER_IDS},
        "always_voucher20": {cl: "voucher20" for cl in pf.CLUSTER_IDS},
        "always_reminder": {cl: "reminder" for cl in pf.CLUSTER_IDS},
        "uplift_greedy": best(lambda a, u: u),
        "eic_greedy_v1": best(_eic),
    }

    n = len(df)
    out = []
    for name, table in policies.items():
        chosen = df["cluster"].map(table)
        match = (chosen == df["arm_assigned"])
        w = match.astype(float) / PROPENSITY
        vals = w * df["decision_reward"]
        est = float(vals.mean())
        se = float(vals.std(ddof=1) / math.sqrt(n))
        conv = float((w * df["converted"]).mean())
        ess = float(w.sum() ** 2 / (w ** 2).sum()) if (w ** 2).sum() > 0 else 0.0
        mix = chosen.value_counts(normalize=True).round(4).to_dict()
        out.append({
            "policy": name,
            "value_per_decision": round(est, 4),
            "ci_low": round(est - 1.96 * se, 4),
            "ci_high": round(est + 1.96 * se, 4),
            "attach_rate": round(conv, 4),
            "matched_decisions": int(match.sum()),
            "effective_sample_size": int(ess),
            "arm_mix": mix,
        })
    out.sort(key=lambda r: -r["value_per_decision"])
    return {
        "estimator": "inverse propensity scoring (IPS), propensity = 0.20 by design",
        "split": "holdout", "n_decisions": n, "policies": out,
        "note": ("Reward is the Magnum contribution of the decision: unit margin minus "
                 "discount given minus contact cost. A policy that contacts everyone pays "
                 "the contact cost on every decision, including the ones that would have "
                 "converted anyway."),
    }


@lru_cache(maxsize=1)
def forecast_accuracy() -> Dict:
    """Scored on the weekly backtest origins only - the live run at SIM_END
    predicts hours no order can land in.

    Reported at three grains on purpose. Hourly store-SKU demand is mostly zero
    or one unit, so a percentage error on it is arithmetic noise, not a signal;
    p90 coverage is the honest hourly metric because it answers the question the
    shelf asks. WAPE is reported where a planner reads it: units per SKU per day
    and per store per day.
    """
    con = _con()
    fc = pd.read_sql(
        "SELECT generated_at, target_hour, offset, store_id, sku_id, p10, p50, p90 "
        "FROM forecasts WHERE origin_kind = 'backtest'", con)
    act = pd.read_sql(
        "SELECT o.store_id, i.sku_id, strftime('%Y-%m-%d %H:00:00', o.ordered_at) target_hour, "
        "SUM(i.quantity) units FROM order_items i JOIN orders o ON o.order_id = i.order_id "
        "WHERE i.category = 'magnum' GROUP BY 1,2,3", con)
    con.close()
    m = fc.merge(act, on=["store_id", "sku_id", "target_hour"], how="left")
    m["units"] = m["units"].fillna(0.0)
    m["date"] = m["target_hour"].str[:10]

    def wape(g):
        d = g["units"].sum()
        return float((g["p50"] - g["units"]).abs().sum() / d) if d > 0 else float("nan")

    hourly_wape = wape(m)
    sku_day = m.groupby(["store_id", "sku_id", "date"])[["p50", "units"]].sum().reset_index()
    store_day = m.groupby(["store_id", "date"])[["p50", "units"]].sum().reset_index()
    sku_day_wape = wape(sku_day)
    store_day_wape = wape(store_day)

    cover90 = float((m["units"] <= m["p90"]).mean())
    cover10 = float((m["units"] >= m["p10"]).mean())
    bias = float((m["p50"] - m["units"]).mean())
    pin90 = float(np.where(m["units"] >= m["p90"], 0.90 * (m["units"] - m["p90"]),
                           0.10 * (m["p90"] - m["units"])).mean())
    pin50 = float(np.where(m["units"] >= m["p50"], 0.50 * (m["units"] - m["p50"]),
                           0.50 * (m["p50"] - m["units"])).mean())

    m["bucket"] = (m["offset"] // 12 * 12).astype(int)
    by_off = []
    for b, g in m.groupby("bucket"):
        by_off.append({"horizon_bucket": int(b), "label": "%d-%dh" % (b, b + 11),
                       "wape_hourly": round(wape(g), 4),
                       "coverage_p90": round(float((g["units"] <= g["p90"]).mean()), 4),
                       "actual_units": int(g["units"].sum()), "n": int(len(g))})

    by_store = []
    for sid, g in m.groupby("store_id"):
        sd = g.groupby("date")[["p50", "units"]].sum().reset_index()
        by_store.append({"store_id": sid,
                         "store": cat.STORE_BY_ID[sid]["name"] if sid in cat.STORE_BY_ID else sid,
                         "wape_store_day": round(wape(sd), 4),
                         "coverage_p90": round(float((g["units"] <= g["p90"]).mean()), 4),
                         "actual_units": int(g["units"].sum())})

    by_sku = []
    for sku, g in m.groupby("sku_id"):
        sd = g.groupby("date")[["p50", "units"]].sum().reset_index()
        by_sku.append({"sku_id": sku, "name": cat.PRODUCT_BY_ID[sku]["name"],
                       "wape_sku_day": round(wape(sd), 4),
                       "coverage_p90": round(float((g["units"] <= g["p90"]).mean()), 4),
                       "actual_units": int(g["units"].sum())})

    # Predicted vs actual at the daily grain, which is the plot that reads.
    ts = (m.groupby("date")[["p50", "units"]].sum().reset_index()
          .rename(columns={"p50": "forecast", "units": "actual"}))
    scatter = sku_day.sample(min(500, len(sku_day)), random_state=7)
    return {
        "n_pairs": int(len(m)),
        "origins": int(fc["generated_at"].nunique()),
        "wape_hourly": round(hourly_wape, 4),
        "wape_sku_day": round(sku_day_wape, 4),
        "wape_store_day": round(store_day_wape, 4),
        "bias_units_per_hour": round(bias, 4),
        "coverage_p90": round(cover90, 4),
        "coverage_p10": round(cover10, 4),
        "pinball_p90": round(pin90, 4),
        "pinball_p50": round(pin50, 4),
        "by_horizon": by_off,
        "by_store": by_store,
        "by_sku": by_sku,
        "timeseries": ts.round(2).to_dict("records"),
        "scatter": scatter.round(2).to_dict("records"),
        "note": ("p90 coverage is the number that matters for stock: the share of hours the "
                 "shelf would have survived had it been filled to p90. WAPE is quoted per "
                 "SKU-day because hourly demand for one flavour in one store is usually zero "
                 "or one unit, where a percentage error means nothing."),
    }


@lru_cache(maxsize=1)
def demand_drivers() -> Dict:
    """What actually moves attach, measured on the log rather than asserted."""
    con = _con()
    o = pd.read_sql(
        "SELECT o.has_magnum, o.intent_class, o.people_inferred, c.temperature_f, "
        "c.temp_anomaly_f, c.weather, c.in_game_window, c.day, c.hour, c.season, "
        "c.demand_index, c.absolute_index, c.activity "
        "FROM orders o JOIN contexts c ON c.store_id = o.store_id "
        "AND c.timestamp = strftime('%Y-%m-%d %H:00:00', o.ordered_at)", con)
    con.close()

    def grp(col, bins=None, labels=None):
        d = o.copy()
        if bins is not None:
            d[col] = pd.cut(d[col], bins=bins, labels=labels)
        g = d.groupby(col, observed=True)["has_magnum"].agg(["mean", "count"]).reset_index()
        g.columns = [col, "attach", "n"]
        return g.round(4).to_dict("records")

    temp = grp("temperature_f", bins=[-20, 32, 45, 60, 72, 82, 90, 120],
               labels=["<32", "32-45", "45-60", "60-72", "72-82", "82-90", "90+"])
    hot = o[o["temperature_f"] >= 80]["has_magnum"].mean()
    cold = o[o["temperature_f"] < 50]["has_magnum"].mean()
    game_on = o[o["in_game_window"] == 1]["has_magnum"].mean()
    game_off = o[o["in_game_window"] == 0]["has_magnum"].mean()

    return {
        "temperature": temp,
        "weather": grp("weather"),
        "hour": grp("hour"),
        "day": grp("day"),
        "season": grp("season"),
        "activity": grp("activity"),
        "game_window": grp("in_game_window"),
        "intent": grp("intent_class"),
        "headline": {
            "hot_vs_cold_attach": [round(float(hot), 4), round(float(cold), 4)],
            "hot_vs_cold_ratio": round(float(hot / cold), 2),
            "game_vs_not_attach": [round(float(game_on), 4), round(float(game_off), 4)],
            "game_lift_pp": round(float(game_on - game_off) * 100, 2),
        },
    }


@lru_cache(maxsize=1)
def stockouts() -> Dict:
    con = _con()
    by_store = pd.read_sql(
        "SELECT store_id, AVG(is_stockout) stockout_rate, SUM(waste) waste, "
        "AVG(on_hand) avg_on_hand FROM inventory GROUP BY store_id", con)
    by_sku = pd.read_sql(
        "SELECT sku_id, AVG(is_stockout) stockout_rate, SUM(waste) waste, "
        "AVG(on_hand) avg_on_hand FROM inventory GROUP BY sku_id", con)
    by_hour = pd.read_sql(
        "SELECT CAST(strftime('%H', snapshot_time) AS INT) hour, AVG(is_stockout) stockout_rate "
        "FROM inventory GROUP BY hour ORDER BY hour", con)
    subs, = con.execute("SELECT SUM(was_substituted) FROM orders").fetchone()
    orders, = con.execute("SELECT COUNT(*) FROM orders").fetchone()
    con.close()
    by_store["store"] = by_store["store_id"].map(
        lambda s: cat.STORE_BY_ID[s]["name"] if s in cat.STORE_BY_ID else s)
    by_sku["name"] = by_sku["sku_id"].map(lambda s: cat.PRODUCT_BY_ID[s]["name"])
    return {
        "by_store": by_store.round(4).to_dict("records"),
        "by_sku": by_sku.round(4).to_dict("records"),
        "by_hour": by_hour.round(4).to_dict("records"),
        "substituted_orders": int(subs),
        "substitution_rate": round(float(subs) / float(orders), 4),
    }


@lru_cache(maxsize=1)
def validation() -> Dict:
    """The only read of `ground_truth`, and it never leaves this function as rows.

    Point of the panel: the estimate recovered from the randomised log is
    compared against the propensities the generator actually used. If the two
    disagree, the analysis layer is wrong, not the data.
    """
    con = _con()
    gt = pd.read_sql("SELECT arm_assigned arm, true_arm_uplift true_uplift, p_magnum_base, p_magnum_with_arm FROM ground_truth WHERE eligible = 1", con)
    con.close()
    true_by_arm = gt.groupby("arm")["true_uplift"].mean() * 100
    obs = {r["arm"]: r for r in uplift("all")["arms"]}
    rows = []
    for arm in ARMS:
        t = float(true_by_arm.get(arm, 0.0))
        o = obs.get(arm, {})
        rows.append({
            "arm": arm,
            "true_uplift_pp": round(t, 3),
            "observed_uplift_pp": o.get("uplift_pp", 0.0),
            "abs_error_pp": round(abs(t - o.get("uplift_pp", 0.0)), 3),
            "inside_ci": bool(o.get("ci_low_pp", 0) <= t <= o.get("ci_high_pp", 0)),
        })
    st = get_store()
    return {
        "arms": rows,
        "max_abs_error_pp": round(max(r["abs_error_pp"] for r in rows), 3),
        "checks": st.quality.get("checks", []),
        "disclosure": ("ground_truth and latent_traits are evaluation-only tables. They are "
                       "read here to score the analysis and nowhere else - no ranking, offer, "
                       "reorder or forecast call can reach them, and the data explorer will "
                       "not serve them."),
    }


def clear_cache():
    for f in (overview, uplift, policy_eval, forecast_accuracy, demand_drivers, stockouts, validation):
        f.cache_clear()
