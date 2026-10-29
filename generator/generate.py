"""Deterministic synthetic commerce generator (epic E1).

Produces every table in section 5.2 of the build document plus two
evaluation-only tables (`latent_traits`, `ground_truth`) that the application is
never allowed to read. Market is the NY / CT metro; currency USD; temperatures
Fahrenheit. Nothing here derives from real Magnum, Uber or retailer data.

Run:  python3 generator/generate.py
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import time
from datetime import timedelta

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from magnum_core import GENERATOR_VERSION, POLICY_VERSION      # noqa: E402
from magnum_core import catalog as cat
from magnum_core import policies as pol                          # noqa: E402
from magnum_core import context as cx                           # noqa: E402
from magnum_core import profiles as pf                          # noqa: E402
from generator import config as cfg                             # noqa: E402

DATA = os.path.join(ROOT, "data")
DELIVERY_FEE = 2.99
SERVICE_FEE_RATE = 0.10


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    return math.log(p / (1.0 - p))


def log(msg):
    print("  " + msg, flush=True)


# ==========================================================================
# 1. Customers and latent traits
# ==========================================================================

def build_customers(rng):
    n = cfg.N_CUSTOMERS
    shares = np.array([c["share"] for c in pf.CLUSTERS])
    cluster_idx = rng.choice(len(pf.CLUSTERS), size=n, p=shares / shares.sum())

    area_ids = [a["area_id"] for a in cat.AREAS]
    area_weight = np.array([a["activity_base"] for a in cat.AREAS])
    area_idx = rng.choice(len(area_ids), size=n, p=area_weight / area_weight.sum())
    customer_ids = ["CUS-%06d" % (i + 1) for i in range(n)]

    band = np.empty(n, dtype=object)
    price_sens = np.zeros(n); event_aff = np.zeros(n); craving = np.zeros(n)
    cadence = np.zeros(n); pack_bias = np.zeros(n); heat_beta = np.zeros(n)
    attach = np.zeros(n); disc_uplift = np.zeros(n); pref_hour = np.zeros(n, dtype=int)
    flavour_pref = np.zeros((n, len(cat.FLAVOURS)))

    for ci, clus in enumerate(pf.CLUSTERS):
        m = cluster_idx == ci
        k = int(m.sum())
        if k == 0:
            continue
        band[m] = rng.choice(pf.HOUSEHOLD_BANDS, size=k, p=clus["household_band"])
        conc = 9.0
        price_sens[m] = rng.beta(clus["price_sens"] * conc, (1 - clus["price_sens"]) * conc, size=k)
        event_aff[m] = rng.beta(clus["event_affinity"] * conc, (1 - clus["event_affinity"]) * conc, size=k)
        craving[m] = np.clip(rng.lognormal(math.log(clus["craving_rate"]), 0.34, size=k), 0.15, 6.0)
        cadence[m] = np.clip(rng.normal(clus["cadence_days"], clus["cadence_sd"], size=k), 2.5, 60.0)
        pack_bias[m] = np.clip(rng.normal(clus["pack_bias"], 0.16, size=k), 0.0, 1.0)
        heat_beta[m] = np.clip(rng.normal(clus["heat_beta"], 0.012, size=k), 0.0, 0.25)
        attach[m] = np.clip(rng.normal(clus["attach_rate"], 0.12, size=k), 0.02, 0.98)
        # True incremental effect of the 20% voucher, scaled by this person's own
        # price sensitivity. This is the number the uplift work has to recover.
        disc_uplift[m] = np.clip(
            clus["discount_uplift"] * (0.35 + 1.30 * price_sens[m]) + rng.normal(0, 0.010, size=k),
            -0.02, 0.40)
        alpha = np.array([clus["flavour_bias"][f] for f in cat.FLAVOURS]) * 2.4
        flavour_pref[m] = rng.dirichlet(alpha, size=k)
        ww = clus["window_weights"]
        wsel = rng.choice([w["id"] for w in cx.TIME_WINDOWS], size=k,
                          p=np.array([ww[w["id"]] for w in cx.TIME_WINDOWS]))
        pref_hour[m] = [cx.TIME_WINDOW_BY_ID[w]["peak_hour"] for w in wsel]

    # Pin the six named demo profiles onto the first six customers so the golden
    # scenarios are stable across regenerations.
    for i, prof in enumerate(pf.DEMO_PROFILES):
        clus = pf.CLUSTER_BY_ID[prof["cluster_id"]]
        cluster_idx[i] = pf.CLUSTER_IDS.index(prof["cluster_id"])
        area_idx[i] = area_ids.index(prof["home_area"])
        band[i] = prof["household_band"]
        price_sens[i] = clus["price_sens"]; event_aff[i] = clus["event_affinity"]
        craving[i] = clus["craving_rate"]; cadence[i] = clus["cadence_days"]
        pack_bias[i] = clus["pack_bias"]; heat_beta[i] = clus["heat_beta"]
        attach[i] = clus["attach_rate"]
        disc_uplift[i] = clus["discount_uplift"] * (0.35 + 1.30 * clus["price_sens"])
        alpha = np.array([clus["flavour_bias"][f] for f in cat.FLAVOURS])
        flavour_pref[i] = alpha / alpha.sum()
        pref_hour[i] = cx.TIME_WINDOW_BY_ID[prof["usual_window"]]["peak_hour"]

    clusters = np.array([pf.CLUSTER_IDS[i] for i in cluster_idx])
    areas = np.array([area_ids[i] for i in area_idx])
    created = [cfg.SIM_START - timedelta(days=int(d)) for d in rng.integers(30, 900, size=n)]
    display = [pf.DEMO_PROFILES[i]["display_name"] if i < len(pf.DEMO_PROFILES)
               else "Shopper %05d" % (i + 1) for i in range(n)]

    customers = pd.DataFrame({
        "customer_id": customer_ids,
        "display_name": display,
        "home_area": areas,
        "state": [cat.AREA_BY_ID[a]["state"] for a in areas],
        "zip": [cat.AREA_BY_ID[a]["zip"] for a in areas],
        "store_id": [cat.STORE_BY_AREA[a]["store_id"] for a in areas],
        "household_size_band": band,
        "peer_cluster": clusters,
        "consent_marketing": rng.random(n) < 0.88,
        "consent_personalisation": rng.random(n) < 0.94,
        "created_at": created,
        "is_demo_profile": [i < len(pf.DEMO_PROFILES) for i in range(n)],
    })

    traits = pd.DataFrame({
        "customer_id": customer_ids,
        "peer_cluster": clusters,
        "craving_rate_per_week": craving.round(4),
        "cadence_days": cadence.round(3),
        "price_sensitivity": price_sens.round(4),
        "event_affinity": event_aff.round(4),
        "heat_beta": heat_beta.round(4),
        "attach_propensity": attach.round(4),
        "pack_bias": pack_bias.round(4),
        "true_voucher_uplift": disc_uplift.round(5),
        "preferred_hour": pref_hour,
    })
    for j, f in enumerate(cat.FLAVOURS):
        traits["flavour_pref_" + f] = flavour_pref[:, j].round(4)

    tr = {"cluster_idx": cluster_idx, "area_idx": area_idx, "craving": craving,
          "cadence": cadence, "price_sens": price_sens, "event_aff": event_aff,
          "heat_beta": heat_beta, "attach": attach, "pack_bias": pack_bias,
          "disc_uplift": disc_uplift, "flavour_pref": flavour_pref, "band": band,
          "areas": areas, "clusters": clusters}
    return customers, traits, tr


# ==========================================================================
# 2. Hourly context per store (rule 2 of section 5.5)
# ==========================================================================

def build_contexts(rng):
    n_days, n_areas = cfg.DAYS, len(cat.AREAS)
    dates = [cfg.SIM_START + timedelta(days=int(d)) for d in range(n_days)]
    season_by_day = np.array([cx.season_for_month(d.month) for d in dates])

    # City-wide sports calendar: roughly two to three game evenings a week.
    game_by_day = np.zeros(n_days, dtype=bool)
    for d in range(n_days):
        dow = dates[d].weekday()
        p = {4: 0.46, 5: 0.58, 6: 0.50, 2: 0.26, 3: 0.22}.get(dow, 0.10)
        game_by_day[d] = rng.random() < p

    weather = np.empty((n_areas, n_days), dtype=object)
    event = np.empty((n_areas, n_days), dtype=object)
    season_weather_p = {
        "summer": (["hot", "warm", "cool", "rain"], [0.40, 0.38, 0.08, 0.14]),
        "spring": (["hot", "warm", "cool", "rain"], [0.10, 0.40, 0.29, 0.21]),
        "fall": (["hot", "warm", "cool", "rain"], [0.07, 0.33, 0.38, 0.22]),
        "winter": (["warm", "cool", "rain", "snow"], [0.10, 0.46, 0.20, 0.24]),
    }
    for a in range(n_areas):
        for d in range(n_days):
            opts, probs = season_weather_p[season_by_day[d]]
            weather[a, d] = rng.choice(opts, p=probs)
            event[a, d] = rng.choice(["none", "street_festival", "concert", "public_holiday"],
                                     p=[0.942, 0.024, 0.022, 0.012])

    cols = {k: np.zeros((n_areas, n_days * 24), dtype=float) for k in
            ("temp", "anom", "abs", "lift", "group", "heat", "activity")}
    game_win = np.zeros((n_areas, n_days * 24), dtype=bool)
    rows = []
    for a, area in enumerate(cat.AREAS):
        store_id = cat.STORE_BY_AREA[area["area_id"]]["store_id"]
        base_activity = area["activity_base"]
        for d in range(n_days):
            date = dates[d]
            dow = date.weekday()
            season = season_by_day[d]
            w = str(weather[a, d])
            ev = str(event[a, d])
            day_name = cx.DAYS[dow]
            day_noise = rng.normal(0, 2.6)
            for h in range(24):
                idx = d * 24 + h
                ts = date + timedelta(hours=h)
                in_game = bool(game_by_day[d] and cx.DEFAULT_GAME_START <= h < cx.DEFAULT_GAME_END)
                act_score = (base_activity + (0.10 if dow >= 4 else 0.0)
                             + (0.08 if ev != "none" else 0.0) + (0.06 if in_game else 0.0)
                             + rng.normal(0, 0.05))
                activity = "high" if act_score > 0.80 else ("low" if act_score < 0.62 else "normal")
                temp = cx.temperature_for(season, w, h) + day_noise + rng.normal(0, 1.2)
                raw = cx.raw_demand_multiplier(day_name, h, season, w, bool(game_by_day[d]),
                                               ev, activity, in_game_window=in_game)
                neutral = cx.raw_demand_multiplier(day_name, h, season, "warm", False, "none", "normal")
                anom = temp - cx.SEASON_BY_ID[season]["norm_temp"]
                heat_pull = max(0.0, min(1.0, (temp - cx.FREEZING_F) / 62.0))
                gb = cx.EVENT_BY_ID[ev]["group_bias"] + (cx.GAME_SHAREABLE_BIAS if in_game else 0.0)
                gb += 0.20 if dow >= 4 else 0.0
                gb += 0.15 if 17 <= h < 22 else (-0.30 if h >= 22 or h < 6 else 0.0)
                if area["density"] == "suburban":
                    gb += 0.18                      # bigger households, car trips, freezer space

                cols["temp"][a, idx] = temp
                cols["anom"][a, idx] = anom
                cols["abs"][a, idx] = raw / cx._REFERENCE_MULTIPLIER
                cols["lift"][a, idx] = raw / neutral
                cols["group"][a, idx] = gb
                cols["heat"][a, idx] = heat_pull
                cols["activity"][a, idx] = cx.ACTIVITY_BY_ID[activity]["multiplier"]
                game_win[a, idx] = in_game

                rows.append((
                    store_id, area["area_id"], area["state"], ts, date.date().isoformat(),
                    day_name, dow, h, season, w, bool(game_by_day[d]), in_game, ev, activity,
                    round(float(temp), 1), cx.humidity_for(season, w), cx.WEATHER_BY_ID[w]["rain_in"],
                    round(float(anom), 2), round(cx.ACTIVITY_BY_ID[activity]["multiplier"], 3),
                    round(raw / neutral, 4), round(raw / cx._REFERENCE_MULTIPLIER, 4),
                ))

    contexts = pd.DataFrame(rows, columns=[
        "store_id", "area_id", "state", "timestamp", "date", "day", "day_of_week", "hour",
        "season", "weather", "game_day", "in_game_window", "event", "activity",
        "temperature_f", "humidity_pct", "rain_in", "temp_anomaly_f", "activity_index",
        "demand_index", "absolute_index"])
    grid = {"cols": cols, "game_win": game_win, "season_by_day": season_by_day,
            "game_by_day": game_by_day, "weather": weather, "event": event, "dates": dates}
    return contexts, grid


# ==========================================================================
# 3. Sessions
# ==========================================================================

def build_sessions(rng, cust, tr, grid):
    n, weeks = cfg.N_CUSTOMERS, cfg.WEEKS
    scale = cfg.TARGET_SESSIONS / (tr["craving"].sum() * weeks)
    counts = np.maximum(rng.poisson(tr["craving"] * weeks * scale), 1)
    total = int(counts.sum())
    log("sessions to draw: %s" % f"{total:,}")
    cust_of_session = np.repeat(np.arange(n), counts)

    dates = grid["dates"]
    dows = np.array([d.weekday() for d in dates])
    # Mean daily temperature anomaly per area, used to pull sessions toward hot days.
    anom_by_area_day = grid["cols"]["anom"].reshape(len(cat.AREAS), cfg.DAYS, 24).mean(axis=2)

    cl_of_session = tr["cluster_idx"][cust_of_session]
    ar_of_session = tr["area_idx"][cust_of_session]
    day_idx = np.zeros(total, dtype=int)
    for ci, clus in enumerate(pf.CLUSTERS):
        for ai in range(len(cat.AREAS)):
            mask = (cl_of_session == ci) & (ar_of_session == ai)
            k = int(mask.sum())
            if k == 0:
                continue
            w = np.array([cx.WEEKDAY_CURVE[d] for d in dows])
            w = w * np.where(dows >= 4, clus["weekend_bias"], 1.0)
            w = w * np.maximum(0.15, 1.0 + clus["heat_beta"] * 1.4 * anom_by_area_day[ai])
            day_idx[mask] = rng.choice(cfg.DAYS, size=k, p=w / w.sum())

    win_ids = [w["id"] for w in cx.TIME_WINDOWS]
    hour = np.zeros(total, dtype=int)
    for ci, clus in enumerate(pf.CLUSTERS):
        mask = cl_of_session == ci
        k = int(mask.sum())
        if k == 0:
            continue
        p = np.array([clus["window_weights"][w] for w in win_ids])
        chosen = rng.choice(len(win_ids), size=k, p=p / p.sum())
        hrs = np.zeros(k, dtype=int)
        for wi, w in enumerate(cx.TIME_WINDOWS):
            wm = chosen == wi
            kk = int(wm.sum())
            if kk == 0:
                continue
            span = np.arange(w["start_hour"], w["end_hour"])
            pw = np.array([cx.HOUR_CURVE[s % 24] for s in span])
            hrs[wm] = rng.choice(span, size=kk, p=pw / pw.sum())
        hour[mask] = hrs

    minute = rng.integers(0, 60, size=total)
    order = np.lexsort((minute, hour, day_idx))
    cust_of_session = cust_of_session[order]
    day_idx, hour, minute = day_idx[order], hour[order], minute[order]

    start = [cfg.SIM_START + timedelta(days=int(day_idx[i]), hours=int(hour[i]),
                                       minutes=int(minute[i])) for i in range(total)]
    sessions = pd.DataFrame({
        "session_id": ["SES-%08d" % (i + 1) for i in range(total)],
        "customer_idx": cust_of_session,
        "customer_id": cust["customer_id"].values[cust_of_session],
        "store_id": cust["store_id"].values[cust_of_session],
        "area_id": cust["home_area"].values[cust_of_session],
        "state": cust["state"].values[cust_of_session],
        "start_time": start,
        "day_idx": day_idx,
        "hour": hour,
        "hour_idx": day_idx * 24 + hour,
        "area_idx": tr["area_idx"][cust_of_session],
    })
    # Randomised assignment - the reason incremental effects are estimable here
    # rather than inferred from who happened to be targeted.
    sessions["assigned_policy"] = rng.choice(["baseline", "personalised"], size=total)
    sessions["offer_arm_assigned"] = rng.choice([a["arm"] for a in cfg.OFFER_ARMS], size=total)
    sessions["entry_source"] = rng.choice(
        ["organic_search", "category_browse", "notification", "banner", "reorder_link"],
        size=total, p=[0.46, 0.24, 0.14, 0.10, 0.06])
    # Client-side instrumentation sampling. Every session emits a lifecycle
    # event; a deterministic sample carries the full interaction stream. This
    # is how production telemetry is actually collected, and it keeps the event
    # table near the documented volume instead of an order of magnitude above it.
    sessions["instrumented"] = rng.random(total) < cfg.INSTRUMENTATION_RATE
    return sessions


# ==========================================================================
# 4. The simulation walk
# ==========================================================================
# One pass in time order. It has to be a single ordered walk because inventory
# depletion, contact frequency caps and each household's own purchase cadence
# are all stateful and all interact: a stockout changes what a customer buys,
# which changes when they are next due, which changes whether contacting them
# is worth the fee. Rule 4 of section 5.5 - stock is never backfilled from
# future demand - falls out of doing it this way.

MEALS_SHARE = ["MEA-PIZ-L", "MEA-PIZ-P", "MEA-WNG-8"]
MEALS_SOLO = ["MEA-HAL-1", "MEA-HER-I", "MEA-BUR-B"]
DRINKS = ["DRK-COK-2", "DRK-COK-D", "DRK-LEM-2", "DRK-WAT-1", "DRK-TEA-2"]
SIDES = ["SID-FRY-1", "SID-MOZ-6", "SID-ONI-1", "SID-CHP-S", "SID-KNO-6"]
DESSERTS = ["DES-BRW-1", "DES-CHS-1", "DES-PNT-1", "DES-CKI-4"]
BAND_BASE = {"1": 1.0, "2": 2.0, "3-4": 3.4, "5+": 5.0}
MAG_POPULARITY = np.array([0.24, 0.20, 0.14, 0.11, 0.12, 0.11, 0.05, 0.03])  # order of cat.MAGNUM_SKUS

# True incremental effect of each arm, expressed against the customer's own
# voucher responsiveness. Only the voucher moves people much, and it is the
# arm that costs the most margin - which is the finding the POC has to survive.
ARM_EFFECT = {
    "none": lambda u, due, d: 0.0,
    # The voucher's effect scales with how deep the voucher actually is. A 25%
    # note is not a 20% note with a different label, and holding the effect flat
    # while the depth moves would make every dynamic-discount claim unfalsifiable.
    "voucher20": lambda u, due, d: u * (d / 0.20),
    "multipack_value": lambda u, due, d: (0.34 * u + 0.014) * (d / 0.08),
    "flavour_discovery": lambda u, due, d: 0.10 * u + 0.009,
    "reminder": lambda u, due, d: 0.06 * u + 0.011 * min(2.0, max(0.0, due - 0.6)),
}

# --------------------------------------------------------------------------
# How the plate in front of someone changes the dessert behind it
# --------------------------------------------------------------------------
# These four constants are the whole dish-to-dessert mechanism, kept together
# and named so the effect sizes can be argued with rather than reverse-engineered
# out of a logit. Each one is an affinity, not a rule: it moves a probability,
# and a household's own eight-month history still outranks all of them.

# Heat pushes people toward a cold, creamy, milder finish. This is the single
# largest dish effect in the model and the easiest one to defend out loud.
SPICE_ATTACH_BETA = 0.85      # logit points at maximum spice
SPICE_QTY_BETA = 0.55         # extra units at maximum spice

# A heavy plate has already done the job dessert was going to do.
RICH_ATTACH_BETA = -0.30
RICH_QTY_BETA = -0.35

# How hard the dishes in the basket tilt flavour choice. 1.30 means a dish's
# first-listed flavour carries 2.6x its baseline odds - visible in a single
# basket, still losable to a strong personal preference, which is the balance
# a recommender has to strike anyway.
PAIR_FLAVOUR_TILT = 1.60

# Warm weather raises units, not just attach. Nobody buys one bar for the house
# in August.
HEAT_QTY_BETA = 0.90

# And how hard temperature tilts flavour choice, using the shared tilt in the
# catalogue. At the extremes of the window this moves a flavour's odds by about
# a third either way - enough to see in a season-over-season mix, small enough
# that a household that only buys caramel still mostly buys caramel in July.
HEAT_FLAVOUR_BETA = 0.55

# The box that carries each flavour. Every flavour has one, so choosing a
# format never silently changes what someone is eating.
PACK_FOR_FLAVOUR = {"classic": "MAG-MIN-6", "caramel": "MAG-CAR-3",
                    "almond": "MAG-ALM-3", "white": "MAG-WHT-3"}


def basket_character(line):
    """Reduce a basket to the three numbers that predict the dessert after it.

    Returns (spice, richness, pair_weights). spice and richness are
    quantity-weighted means over the food in the basket - a lone drink should
    not make a basket read as light, so drinks carry near-zero richness and are
    simply weak votes. pair_weights is an unnormalised score per flavour, with
    a dish's first-listed flavour counting nearly twice its second.
    """
    spice = rich = wsum = 0.0
    pair_w = {}
    for sku, qty, _ in line:
        p = cat.PRODUCT_BY_ID[sku]
        # Prominence, not line count. A basket is not an average of equals: the
        # wings are what the table is eating and the fries are what came with
        # them, so portion size carries the vote. Without this a single side
        # dish cancels the main course and every basket reads the same.
        w = float(qty) * (0.6 + p["portion_size"])
        # And a hot dish is louder than a mild one about what should follow it.
        pw = w * (1.0 + 1.2 * p["spice"])
        spice += p["spice"] * w
        rich += p["richness"] * w
        wsum += w
        for r, f in enumerate(p["pairs"]):
            pair_w[f] = pair_w.get(f, 0.0) + pw * (1.0 if r == 0 else 0.55)
    if wsum:
        spice /= wsum
        rich /= wsum
    return spice, rich, pair_w


def simulate(rng, cust, tr, sessions, grid):
    n_areas, n_mag = len(cat.AREAS), len(cat.MAGNUM_SKUS)
    n_sessions = len(sessions)
    mag_price = np.array([cat.PRODUCT_BY_ID[s]["price"] for s in cat.MAGNUM_SKUS])
    mag_margin = np.array([cat.PRODUCT_BY_ID[s]["unit_margin"] for s in cat.MAGNUM_SKUS])
    mag_units = np.array([cat.PACK_UNITS[s] for s in cat.MAGNUM_SKUS])
    flavour_to_mag = {f: cat.MAGNUM_SKUS.index(cat.SINGLE_BY_FLAVOUR[f]) for f in cat.FLAVOURS}
    pack_idx = {cat.MAGNUM_SKUS.index(sk) for sk in cat.MAGNUM_PACKS}

    # --- inventory state -------------------------------------------------
    area_factor = np.array([a["activity_base"] for a in cat.AREAS])
    base_daily = np.outer(26.0 * area_factor, MAG_POPULARITY)          # units/day per store x sku
    stock = np.ceil(base_daily * 1.6 + cfg.SAFETY_STOCK_UNITS).astype(int)
    sold_hist = np.tile(base_daily[:, :, None], (1, 1, 7))
    sold_today = np.zeros((n_areas, n_mag))
    sold_prev_hour = np.zeros((n_areas, n_mag), dtype=int)
    sold_this_hour = np.zeros((n_areas, n_mag), dtype=int)
    inbound_today = np.zeros((n_areas, n_mag), dtype=int)
    waste_today = np.zeros((n_areas, n_mag), dtype=int)
    freezer_cap = np.array([cat.STORES[i]["freezer_slots"] for i in range(n_areas)])

    inv_rows = []
    stockout_hours = np.zeros((n_areas, n_mag), dtype=int)

    def snapshot(hour_index):
        d, h = divmod(hour_index, 24)
        ts = cfg.SIM_START + timedelta(days=int(d), hours=int(h))
        for a in range(n_areas):
            sid = cat.STORES[a]["store_id"]
            for s in range(n_mag):
                oh = int(stock[a, s])
                if oh <= 0:
                    stockout_hours[a, s] += 1
                inv_rows.append((ts, sid, cat.MAGNUM_SKUS[s], oh, int(sold_prev_hour[a, s]),
                                 int(inbound_today[a, s]), int(waste_today[a, s]), oh <= 0))

    def advance_to(hour_index):
        """Walk the inventory clock forward, replenishing and writing snapshots."""
        nonlocal sold_prev_hour, sold_this_hour, sold_today, inbound_today, waste_today
        while cur[0] < hour_index:
            hi = cur[0]
            h = hi % 24
            if h == cfg.REPLENISH_HOUR:
                # Target from a LAGGED seven-day average. Nothing here can see
                # tomorrow, so hot days genuinely run short.
                avg = sold_hist.mean(axis=2)
                target = np.ceil(avg * cfg.REPLENISH_COVER).astype(int) + cfg.SAFETY_STOCK_UNITS
                share_cap = np.floor(np.outer(freezer_cap, MAG_POPULARITY)).astype(int)
                target = np.minimum(target, share_cap)
                add = np.maximum(0, target - stock)
                stock[:] = stock + add
                inbound_today[:] = add
            if h == 23:
                # Freezer shrink and date-code expiry. Stochastic rounding, or a
                # 0.4%/day rate on a shelf of fifteen units always floors to zero
                # and the waste column reads as a perfect cold chain.
                expected = stock * cfg.DAILY_SHRINK_RATE
                w = np.floor(expected).astype(int)
                w = w + (rng.random(expected.shape) < (expected - w)).astype(int)
                stock[:] = np.maximum(0, stock - w)
                waste_today[:] = w
                sold_hist[:, :, hi // 24 % 7] = sold_today
                sold_today[:] = 0.0
                inbound_today[:] = 0
            snapshot(hi)
            sold_prev_hour = sold_this_hour.copy()
            sold_this_hour = np.zeros((n_areas, n_mag), dtype=int)
            cur[0] += 1

    cur = [0]

    # --- customer state --------------------------------------------------
    n_cust = cfg.N_CUSTOMERS
    # Seed the clock: each household starts part-way through its own cycle.
    last_mag_day = -rng.exponential(tr["cadence"] * 0.6)
    last_order_day = last_mag_day.copy()
    last_contact_day = np.full(n_cust, -999.0)
    contacts_7d = np.zeros(n_cust, dtype=int)
    contact_log_day = [[] for _ in range(n_cust)]
    mag_purchases = np.zeros(n_cust, dtype=int)
    units_bought = np.zeros(n_cust, dtype=int)
    flavour_counts = np.zeros((n_cust, len(cat.FLAVOURS)), dtype=int)
    pack_counts = np.zeros(n_cust, dtype=int)
    spend_total = np.zeros(n_cust)

    # --- pre-drawn randomness (deterministic and fast) --------------------
    u_order = rng.random(n_sessions); u_mag = rng.random(n_sessions)
    u_intent = rng.random(n_sessions); u_people = rng.random(n_sessions)
    u_pack = rng.random(n_sessions); u_flav = rng.random(n_sessions)
    u_side = rng.random(n_sessions); u_drink = rng.random(n_sessions)
    u_dess = rng.random(n_sessions); u_meal = rng.random(n_sessions)
    u_sub = rng.random(n_sessions)
    n_pick = rng.random((n_sessions, 4))

    cols = grid["cols"]
    game_win = grid["game_win"]
    s_cust = sessions["customer_idx"].values
    s_area = sessions["area_idx"].values
    s_hidx = sessions["hour_idx"].values
    s_arm = sessions["offer_arm_assigned"].values
    s_policy = sessions["assigned_policy"].values
    s_id = sessions["session_id"].values
    s_store = sessions["store_id"].values
    s_state = sessions["state"].values
    s_entry = sessions["entry_source"].values
    arm_cfg = {a["arm"]: a for a in cfg.OFFER_ARMS}

    band = tr["band"]; cadence = tr["cadence"]; heat_beta = tr["heat_beta"]
    attach = tr["attach"]; event_aff = tr["event_aff"]; pack_bias = tr["pack_bias"]
    disc_uplift = tr["disc_uplift"]; flavour_pref = tr["flavour_pref"]
    price_sens = tr["price_sens"]

    LOGIT_ORDER = logit(cfg.BASE_ORDER_CONVERSION)
    MAG_INTERCEPT = cfg.MAGNUM_LOGIT_INTERCEPT

    orders = []; items = []; offers = []; truth = []
    order_no = 0

    t0 = time.time()
    for i in range(n_sessions):
        c = s_cust[i]; a = s_area[i]; hi = s_hidx[i]
        if hi > cur[0]:
            advance_to(hi)
        day_f = hi / 24.0
        anom = cols["anom"][a, hi]; heat = cols["heat"][a, hi]
        gb = cols["group"][a, hi]; abs_idx = cols["abs"][a, hi]
        lift = cols["lift"][a, hi]; in_game = bool(game_win[a, hi])

        due = max(0.0, (day_f - last_mag_day[c]) / cadence[c])

        # ---- does the session convert to an order at all? ----------------
        lo = (LOGIT_ORDER + 0.30 * (lift - 1.0) + 0.18 * min(2.5, due)
              + (0.35 if s_entry[i] in ("notification", "reorder_link") else 0.0)
              - 0.10 * (s_policy[i] == "baseline"))
        if u_order[i] >= 1.0 / (1.0 + math.exp(-lo)):
            continue

        # ---- intent: dessert-led or meal-led (§4.2) ----------------------
        p_direct = min(0.97, max(0.02, (1.0 - attach[c]) * (0.80 + 0.55 * heat)))
        direct = u_intent[i] < p_direct

        # ---- inferred occasion size (§4.4) -------------------------------
        base_people = BAND_BASE[band[c]]
        people = int(np.clip(round(base_people * (0.72 + 0.40 * u_people[i]) + 0.70 * gb), 1, 6))

        line = []                       # (sku_id, qty, was_recommended)
        if not direct:
            n_meals = 1 if people <= 2 else (2 if people <= 4 else 3)
            pool = MEALS_SHARE if people >= 3 else MEALS_SOLO
            picks = []
            for k in range(n_meals):
                picks.append(pool[int(n_pick[i, k] * len(pool)) % len(pool)])
            for skew in set(picks):
                line.append((skew, picks.count(skew), False))
            n_drinks = int(round(people * (0.55 + 0.4 * u_drink[i])))
            if n_drinks > 0:
                line.append((DRINKS[int(n_pick[i, 3] * len(DRINKS)) % len(DRINKS)], n_drinks, False))
            if u_side[i] < (0.35 + 0.45 * max(0.0, gb)):
                line.append((SIDES[int(u_side[i] * len(SIDES)) % len(SIDES)], 1, False))
        else:
            if u_dess[i] < 0.22:
                line.append((DESSERTS[int(u_dess[i] * len(DESSERTS)) % len(DESSERTS)], 1, False))

        # ---- what is already on the plate --------------------------------
        b_spice, b_rich, pair_w = basket_character(line)
        top_basket_pair = max(pair_w, key=lambda k: pair_w[k]) if pair_w else None

        # ---- Magnum attach: the decision the whole POC is about -----------
        # Coefficients are in Fahrenheit units: heat_beta is per-degree-F, so the
        # anomaly term contributes tenths of a logit, not whole logits.
        lm = (MAG_INTERCEPT
              + 0.55 * math.log1p(min(3.0, due))
              + heat_beta[c] * 0.85 * anom
              # Anomaly alone says "unusually warm for the season", which is not
              # the same thing as warm. Over a nine-month window the absolute
              # term is what separates a 38F February from an 88F July; without
              # it a cold day at its seasonal norm attaches like a hot one.
              + heat_beta[c] * 2.60 * (heat - 0.62)
              + 0.60 * event_aff[c] * (1.0 if in_game else 0.0)
              + 0.60 * (1.0 if direct else 0.0)
              + 0.18 * gb
              + 0.20 * (lift - 1.0)
              # A wings basket and a burger basket of the same size do not
              # attach at the same rate, and the difference is not size. Heat
              # pushes toward a cold finish; a plate that was already heavy has
              # done the job dessert was going to do.
              + SPICE_ATTACH_BETA * b_spice
              + RICH_ATTACH_BETA * b_rich)
        p_base = 1.0 / (1.0 + math.exp(-lm))
        arm = s_arm[i]

        # Frequency caps are applied to DELIVERY, not to assignment, and the
        # suppression is logged. Randomisation stays intact for anyone who
        # later restricts the analysis to non-suppressed decisions.
        contact_days = contact_log_day[c]
        while contact_days and day_f - contact_days[0] > 7.0:
            contact_days.pop(0)
        suppression = None
        if day_f - last_contact_day[c] < 1.0 or len(contact_days) >= 3:
            suppression = "FREQUENCY_CAPPED"
        elif day_f - last_order_day[c] < 0.5:
            suppression = "POST_PURCHASE_SUPPRESS"
        eligible = suppression is None
        delivered = arm if (eligible and arm != "none") else "none"

        # ---- how deep the discount is, given how the hour is trading ------
        # A fixed 20% note on every hour of a nine-month window is a pricing
        # decision nobody would defend. Depth moves against demand: a slow hour
        # buys volume with margin, a hot hour does not need to. The band is
        # capped at the guardrail so no generated decision is one the live
        # policy would refuse to make.
        # The same function the live policy calls, imported rather than
        # reimplemented. A generator and a policy that each carry their own copy
        # of a pricing rule will drift, and the first symptom is a demo whose
        # numbers cannot be traced back to the data they were fitted on.
        deliv_pct, _, _ = pol.discount_depth(arm_cfg[delivered]["discount_pct"], float(lift))

        uplift = ARM_EFFECT[delivered](disc_uplift[c], due, deliv_pct)
        p_arm = float(np.clip(p_base + uplift, 0.001, 0.985))
        bought = u_mag[i] < p_arm

        if delivered != "none":
            last_contact_day[c] = day_f
            contact_days.append(day_f)

        # ---- format and flavour choice -----------------------------------
        mag_sku = None; mag_qty = 0; substituted = False; want_idx = None
        if bought:
            # ---- flavour first, format second -----------------------------
            # The order matters. Choosing the box first and letting its flavour
            # fall out of the format is what produced the earlier artefact: a
            # pizza basket looked like it wanted classic when what it actually
            # wanted was a six-count. Taste is decided on its own terms here,
            # and the format question is asked afterwards.
            w = np.asarray(flavour_pref[c], dtype=float).copy()
            heat_dev = (heat - 0.62) * 2.0
            w = w * np.clip([1.0 + HEAT_FLAVOUR_BETA * cat.HEAT_FLAVOUR_TILT[f] * heat_dev
                             for f in cat.FLAVOURS], 0.15, None)
            if pair_w:
                peak = max(pair_w.values())
                w = w * np.array([1.0 + PAIR_FLAVOUR_TILT * (pair_w.get(f, 0.0) / peak)
                                  for f in cat.FLAVOURS])
            cum = np.cumsum(w)
            f = cat.FLAVOURS[int(np.searchsorted(cum, u_flav[i] * cum[-1]))]
            if delivered == "flavour_discovery":
                # Nudge toward something they have not bought before.
                unseen = [j for j, fl in enumerate(cat.FLAVOURS) if flavour_counts[c, j] == 0]
                if unseen:
                    f = cat.FLAVOURS[unseen[int(u_flav[i] * len(unseen)) % len(unseen)]]

            # ---- how much ------------------------------------------------
            # Units, not just yes/no. Warm weather, a spicy plate and more
            # people at the table each add volume; a heavy plate removes it.
            q = (1.0 + 0.55 * (people - 1))
            q *= (1.0 + HEAT_QTY_BETA * (heat - 0.62))
            q *= (1.0 + SPICE_QTY_BETA * b_spice)
            q *= (1.0 + RICH_QTY_BETA * (b_rich - 0.45))
            q = float(np.clip(q, 0.6, 6.0))

            # ---- singles or a box ----------------------------------------
            pack_score = (pack_bias[c] + 0.28 * (people - 1) / 4.0 + 0.22 * gb
                          + 0.16 * max(0.0, q - 2.0) + 0.30 * (u_pack[i] - 0.5))
            if delivered == "multipack_value":
                pack_score += 0.25
            want_pack = (people >= 4 and pack_score > 0.58) or \
                        (people >= 3 and pack_score > 0.50) or pack_score > 0.80
            if want_pack:
                # The box in the flavour already chosen. Format answers "how
                # many people", flavour answers "what do they want" - and the
                # two questions no longer contaminate each other.
                want_idx, mag_qty = cat.MAGNUM_SKUS.index(PACK_FOR_FLAVOUR[f]), 1
            else:
                want_idx = flavour_to_mag[f]
                mag_qty = int(np.clip(round(q), 1, 6))

            # ---- availability: substitute rather than fail (§4.2, §10.4) ---
            if stock[a, want_idx] < mag_qty:
                order_pref = np.argsort(-(MAG_POPULARITY * (stock[a] >= mag_qty)))
                alt = [j for j in order_pref if stock[a, j] >= mag_qty]
                if alt:
                    want_idx = int(alt[0]); substituted = True
                else:
                    bought = False

        if bought:
            mag_sku = cat.MAGNUM_SKUS[want_idx]
            stock[a, want_idx] -= mag_qty
            sold_today[a, want_idx] += mag_qty
            sold_this_hour[a, want_idx] += mag_qty
            line.append((mag_sku, mag_qty, delivered != "none" or not direct))
            last_mag_day[c] = day_f
            mag_purchases[c] += 1
            units_bought[c] += mag_qty * int(mag_units[want_idx])
            if want_idx in pack_idx:
                pack_counts[c] += 1
            fl = cat.PRODUCT_BY_ID[mag_sku]["flavour"]
            if fl in cat.FLAVOURS:
                flavour_counts[c, cat.FLAVOURS.index(fl)] += 1

        # A decision is logged whether or not anything is bought. Logging only
        # the baskets that happened would condition the record on the outcome -
        # a dessert-led session that buys nothing would disappear entirely, and
        # every arm that lifts purchase would inflate its own denominator.
        contact_cost = arm_cfg[delivered]["contact_cost"]
        oid = None
        discount = 0.0
        net_margin = -contact_cost

        if line:
            order_no += 1
            oid = "ORD-%07d" % order_no
            ts = cfg.SIM_START + timedelta(hours=int(hi), minutes=int(rng.integers(0, 60)))
            subtotal = 0.0
            margin = 0.0
            for sku, qty, rec in line:
                p = cat.PRODUCT_BY_ID[sku]
                subtotal += p["price"] * qty
                margin += p["unit_margin"] * qty
                items.append((oid, sku, p["category"], qty, p["price"],
                              round(p["unit_margin"], 4), rec))
            if bought and delivered == "voucher20":
                discount = round(cat.PRODUCT_BY_ID[mag_sku]["price"] * mag_qty * deliv_pct, 2)
            elif bought and delivered == "multipack_value" and mag_sku in cat.MAGNUM_PACKS:
                discount = round(cat.PRODUCT_BY_ID[mag_sku]["price"] * mag_qty * deliv_pct, 2)
            service_fee = round(subtotal * SERVICE_FEE_RATE, 2)
            total = round(subtotal - discount + DELIVERY_FEE + service_fee, 2)
            net_margin = round(margin - discount - contact_cost, 4)
            last_order_day[c] = day_f
            spend_total[c] += total
            orders.append((oid, s_id[i], cust["customer_id"].values[c], s_store[i], s_state[i],
                           ts, "delivered", round(subtotal, 2), discount, DELIVERY_FEE,
                           service_fee, total, round(margin, 4), net_margin, len(line), people,
                           "direct" if direct else "attachment", bool(bought),
                           mag_sku, int(mag_qty), bool(substituted)))
        else:
            ts = cfg.SIM_START + timedelta(hours=int(hi))

        # ---- decision log (§4.3) ------------------------------------------
        # The decision log carries the features that were OBSERVABLE at decision
        # time, so a policy can be fitted and evaluated from this table alone
        # without reaching into the generator's internals. p_base / p_with_arm
        # are generator ground truth and live in `ground_truth`, not here.
        basket_value = round(sum(cat.PRODUCT_BY_ID[sk]["price"] * q for sk, q, _ in line), 2)
        offers.append(("DEC-%08d" % (i + 1), s_id[i], cust["customer_id"].values[c], ts, oid,
                       "ctx-%s-%05d" % (s_store[i].lower(), hi),
                       arm_cfg[arm]["offer_id"], arm, delivered,
                       eligible, delivered != "none", suppression,
                       round(deliv_pct, 4), contact_cost, discount,
                       bool(bought), mag_sku, int(mag_qty),
                       round(float(mag_margin[want_idx]) * mag_qty, 4) if bought else 0.0,
                       net_margin,
                       # --- decision-time features ---
                       tr["clusters"][c], round(due, 4), round(float(anom), 2),
                       round(float(cols["heat"][a, hi]), 4), bool(in_game),
                       round(float(abs_idx), 4), round(float(gb), 3),
                       "direct" if direct else "attachment", people, basket_value,
                       round(b_spice, 4), round(b_rich, 4), top_basket_pair,
                       round(min(99.0, day_f - last_order_day[c]), 3), len(contact_days),
                       s_state[i], s_store[i], int(hi % 24),
                       POLICY_VERSION))

        truth.append((s_id[i], cust["customer_id"].values[c], round(p_base, 6), round(p_arm, 6),
                      round(uplift, 6), round(disc_uplift[c], 6), arm, delivered, bool(eligible),
                      bool(bought), round(due, 4), round(float(anom), 2), bool(in_game), people,
                      "direct" if direct else "attachment", round(float(abs_idx), 4)))

        if (i + 1) % 50000 == 0:
            log("  ... %s sessions, %s orders (%.1fs)" % (f"{i+1:,}", f"{order_no:,}", time.time() - t0))

    advance_to(cfg.HOURS)

    orders_df = pd.DataFrame(orders, columns=[
        "order_id", "session_id", "customer_id", "store_id", "state", "ordered_at", "status",
        "subtotal", "discount", "delivery_fee", "service_fee", "total", "gross_margin",
        "net_margin", "n_lines", "people_inferred", "intent_class", "has_magnum",
        "magnum_sku", "magnum_qty", "was_substituted"])
    items_df = pd.DataFrame(items, columns=[
        "order_id", "sku_id", "category", "quantity", "unit_price", "unit_margin", "was_recommended"])
    offers_df = pd.DataFrame(offers, columns=[
        "decision_id", "session_id", "customer_id", "decided_at", "order_id", "context_id",
        "offer_id", "arm_assigned", "arm_delivered", "eligible", "shown", "suppression_reason",
        "discount_pct", "contact_cost", "discount_value", "converted", "magnum_sku",
        "magnum_qty", "magnum_margin", "order_net_margin",
        "cluster", "due_ratio", "temp_anomaly_f", "heat_pull", "in_game_window",
        "absolute_index", "group_bias", "intent_class", "people_inferred", "basket_value",
        "basket_spice", "basket_richness", "basket_pair_flavour",
        "days_since_last_order", "contacts_prior_7d", "state", "store_id", "hour",
        "policy_version"])
    # Decision-level reward: what the Magnum decision itself earned, after the
    # discount it funded and the cost of making contact. This is the number the
    # offline policy comparison is scored on.
    offers_df["decision_reward"] = (offers_df["magnum_margin"]
                                    - offers_df["discount_value"]
                                    - offers_df["contact_cost"]).round(4)
    truth_df = pd.DataFrame(truth, columns=[
        "session_id", "customer_id", "p_magnum_base", "p_magnum_with_arm", "true_arm_uplift",
        "true_voucher_uplift", "arm_assigned", "arm_delivered", "eligible", "bought_magnum", "due_ratio",
        "temp_anomaly_f", "in_game_window", "people_true", "intent_true", "absolute_index"])
    inv_df = pd.DataFrame(inv_rows, columns=[
        "snapshot_time", "store_id", "sku_id", "on_hand", "reserved", "inbound", "waste", "is_stockout"])

    state = {"last_mag_day": last_mag_day, "last_order_day": last_order_day,
             "mag_purchases": mag_purchases, "units_bought": units_bought,
             "flavour_counts": flavour_counts, "pack_counts": pack_counts,
             "spend_total": spend_total, "stock": stock, "sold_hist": sold_hist,
             "stockout_hours": stockout_hours, "last_contact_day": last_contact_day}
    return orders_df, items_df, offers_df, truth_df, inv_df, state


# ==========================================================================
# 5. Reorder candidates (§4.5)
# ==========================================================================

def build_notifications(rng, cust, tr, state):
    n = cfg.N_CUSTOMERS
    cadence = tr["cadence"]
    last = state["last_mag_day"]
    horizon_start = float(cfg.DAYS)
    # Days from the end of the window until this household is next due.
    due_at = last + cadence
    days_out = due_at - horizon_start
    # Discrete-time hazard over the next seven days, from the cadence baseline.
    z = (0.0 - days_out) / np.maximum(1.5, cadence * 0.35)
    prob_7d = np.clip(1.0 / (1.0 + np.exp(-z)) * 0.92 + 0.03, 0.01, 0.97)

    pref = tr["cluster_idx"]
    pref_hour = np.array([cx.TIME_WINDOW_BY_ID[
        max(pf.CLUSTERS[i]["window_weights"], key=pf.CLUSTERS[i]["window_weights"].get)
    ]["peak_hour"] for i in pref])

    candidate_offset = np.clip(np.round(days_out), 0, 14).astype(int)
    candidate_time = [cfg.SIM_END + timedelta(days=int(candidate_offset[i]), hours=int(pref_hour[i]))
                      for i in range(n)]

    action = np.where(prob_7d > 0.72, "reminder",
             np.where(prob_7d > 0.45, "multipack_value",
             np.where(prob_7d > 0.22, "flavour_discovery", "hold")))
    suppression = np.full(n, None, dtype=object)
    recent_purchase = (horizon_start - last) < 1.5
    suppression[recent_purchase] = "POST_PURCHASE_SUPPRESS"
    no_consent = ~cust["consent_marketing"].values
    suppression[no_consent] = "NO_MARKETING_CONSENT"
    capped = (horizon_start - state["last_contact_day"]) < 1.0
    suppression[capped & (suppression == None)] = "FREQUENCY_CAPPED"   # noqa: E711
    action = np.where(suppression != None, "hold", action)             # noqa: E711

    return pd.DataFrame({
        "customer_id": cust["customer_id"].values,
        "peer_cluster": cust["peer_cluster"].values,
        "candidate_time": candidate_time,
        "days_until_due": np.round(days_out, 2),
        "probability_7d": np.round(prob_7d, 4),
        "action": action,
        "suppression_reason": suppression,
        "last_purchase_day": np.round(last, 2),
        "cadence_days": np.round(cadence, 2),
        "generated_at": cfg.SIM_END,
        "policy_version": POLICY_VERSION,
    })


# ==========================================================================
# 6. Baseline demand forecast (§6.2 "seasonal hourly baseline x multipliers")
# ==========================================================================

def build_forecasts(rng, contexts, orders, items, inv):
    """Forecast runs at weekly origins inside the window, plus one live snapshot.

    Every origin only ever uses sales that had already happened when it ran. An
    origin that borrowed the full-window rate would be scoring a forecast that
    had read the answer, and the accuracy numbers would be quietly flattering.
    """
    mag_items = items[items["category"] == "magnum"].merge(
        orders[["order_id", "store_id", "day_idx"]], on="order_id", how="left")

    # Expanding per-store/SKU sales and per-store demand-index exposure, both
    # indexed by day, so an origin can look strictly backwards.
    units_by_day = (mag_items.groupby(["store_id", "sku_id", "day_idx"])["quantity"].sum()
                    .unstack(fill_value=0).reindex(columns=range(cfg.DAYS), fill_value=0)
                    .cumsum(axis=1))
    contexts = contexts.copy()
    contexts["day_idx"] = ((contexts["timestamp"] - cfg.SIM_START).dt.total_seconds() // 86400).astype(int)
    idx_by_day = (contexts.groupby(["store_id", "day_idx"])["absolute_index"].sum()
                  .unstack(fill_value=0.0).reindex(columns=range(cfg.DAYS), fill_value=0.0)
                  .cumsum(axis=1))
    global_units = mag_items.groupby("sku_id")["quantity"].sum()
    global_idx = float(contexts["absolute_index"].sum())
    # Chain-wide units per unit-of-index-hour. Both numerator and denominator
    # must span the same set of stores; dividing the index by the store count
    # while leaving units chain-wide inflates the cold-start prior tenfold.
    prior_rate = {sku: float(global_units.get(sku, 0)) / max(1.0, global_idx)
                  for sku in cat.MAGNUM_SKUS}

    def rate_at(store_id, sku_id, day):
        """Units per unit-of-index-hour using only days before `day`.

        This is an expanding average, not a trailing window. Trailing windows of
        21, 42 and 63 days were all tested and all lost - 0.819, 0.808 and 0.801
        WAPE at the store-day grain against 0.786 for expanding. The season is
        already carried by `absolute_index`, so the rate itself is close to
        season-neutral and every day of extra history only cuts variance.
        """
        d = max(0, day - 1)
        try:
            u = float(units_by_day.loc[(store_id, sku_id), d])
            x = float(idx_by_day.loc[store_id, d])
        except KeyError:
            return prior_rate.get(sku_id, 0.05)
        if x < 24.0 or u < 3.0:
            # Too little history to trust: fall back to the chain-wide prior,
            # which is what a real cold-start store would also have to do.
            return prior_rate.get(sku_id, 0.05)
        return u / x

    ctx_by_key = {}
    for r in contexts.itertuples():
        ctx_by_key[(r.store_id, r.timestamp)] = r
    inv_lookup = {}
    for r in inv.itertuples():
        inv_lookup[(r.store_id, r.sku_id, r.snapshot_time)] = int(r.on_hand)

    origins = []
    d = 0
    while d < cfg.DAYS:
        ts = cfg.SIM_START + timedelta(days=int(d), hours=cfg.FORECAST_ORIGIN_HOUR)
        if ts + timedelta(hours=cfg.FORECAST_HORIZON_HOURS) <= cfg.SIM_END:
            origins.append((d, ts, "backtest"))
        d += cfg.FORECAST_ORIGIN_EVERY_DAYS
    origins.append((cfg.DAYS, cfg.SIM_END, "live"))

    rows = []
    for day, generated_at, kind in origins:
        for area in cat.AREAS:
            store_id = cat.STORE_BY_AREA[area["area_id"]]["store_id"]
            src = ctx_by_key.get((store_id, generated_at))
            if src is None:
                src = ctx_by_key.get((store_id, generated_at - timedelta(hours=1)))
            if src is None:
                continue
            ctx = cx.resolve(day=src.day, time_window="dinner", season=src.season,
                             weather=src.weather, game_day=bool(src.game_day),
                             event=src.event, activity=src.activity,
                             area_id=area["area_id"], hour=int(src.hour))
            hours = cx.snapshot_hours(ctx, cfg.FORECAST_HORIZON_HOURS)
            for sku in cat.MAGNUM_SKUS:
                rate = rate_at(store_id, sku, day)
                on_hand = inv_lookup.get((store_id, sku, generated_at), 0)
                for h in hours:
                    mu = max(0.02, rate * h["absolute_index"])
                    # Negative-binomial style spread: variance above the mean, which
                    # is what hourly retail demand actually looks like.
                    sd = math.sqrt(mu * 1.8)
                    rows.append((
                        generated_at,
                        generated_at + timedelta(hours=int(h["offset"])),
                        h["offset"], kind, store_id, area["state"], sku,
                        round(max(0.0, mu - 1.2816 * sd), 3), round(mu, 3),
                        round(mu + 1.2816 * sd, 3),
                        round(h["demand_index"], 4), round(h["absolute_index"], 4),
                        h["temperature_f"], bool(h["in_game_window"]),
                        int(on_hand),
                    ))
    log("forecast origins: %d backtest + 1 live" % (len(origins) - 1))
    return pd.DataFrame(rows, columns=[
        "generated_at", "target_hour", "offset", "origin_kind", "store_id", "state", "sku_id",
        "p10", "p50", "p90", "demand_index", "absolute_index", "temperature_f",
        "in_game_window", "on_hand_at_generation"])


# ==========================================================================
# 7. Event stream (§8.4)
# ==========================================================================

QUERIES_DIRECT = ["magnum", "ice cream", "ice cream bar", "magnum almond", "chocolate ice cream",
                  "frozen dessert", "magnum bars", "dessert", "ice cream near me"]
QUERIES_ATTACH = ["pizza", "large pizza", "wings", "chicken over rice", "italian hero",
                  "cheeseburger", "halal", "late night food", "delivery near me", "fries"]


def build_events(rng, sessions, orders, items, offers, target=None):
    target = target or cfg.TARGET_EVENTS
    n = len(sessions)
    sid = sessions["session_id"].values
    cid = sessions["customer_id"].values
    t0 = sessions["start_time"].values
    ctxid = np.array(["ctx-%s-%05d" % (s.lower(), h) for s, h in
                      zip(sessions["store_id"].values, sessions["hour_idx"].values)])
    arm = sessions["offer_arm_assigned"].values
    pol = np.full(n, POLICY_VERSION)
    ctx_by_session = dict(zip(sid, ctxid))
    arm_by_session = dict(zip(sid, arm))

    frames = []

    def frame(mask_or_idx, etype, offset_s, query=None, sku=None, rank=None, banner=None, cart=None):
        idx = mask_or_idx
        k = len(idx)
        if k == 0:
            return
        frames.append(pd.DataFrame({
            "event_time": t0[idx] + np.timedelta64(int(offset_s), "s"),
            "session_id": sid[idx], "customer_id": cid[idx], "context_id": ctxid[idx],
            "event_type": etype,
            "query": query if query is not None else np.full(k, None),
            "sku_id": sku if sku is not None else np.full(k, None),
            "rank": rank if rank is not None else np.full(k, np.nan),
            "banner_id": banner if banner is not None else np.full(k, None),
            "cart_id": cart if cart is not None else np.full(k, None),
            "policy_version": pol[idx], "experiment_arm": arm[idx],
        }))

    all_idx = np.arange(n)
    inst = sessions["instrumented"].values
    inst_idx = all_idx[inst]
    frame(all_idx, "session_started", 0)
    frame(inst_idx, "context_applied", 11)

    order_sessions = orders["session_id"].values
    order_pos = pd.Series(np.arange(n), index=sid)
    o_all = order_pos.reindex(order_sessions).values.astype(int)
    o_keep = inst[o_all]
    o_idx = o_all[o_keep]
    orders_i = orders[o_keep]

    is_attach = (orders_i["intent_class"].values == "attachment")
    attach_map = np.zeros(n, dtype=bool)
    attach_map[o_idx] = is_attach

    s_idx = inst_idx[rng.random(len(inst_idx)) < 0.86]
    q = np.where(attach_map[s_idx],
                 rng.choice(QUERIES_ATTACH, size=len(s_idx)),
                 rng.choice(QUERIES_DIRECT, size=len(s_idx)))
    frame(s_idx, "search_submitted", 18, query=q)

    clicked = s_idx[rng.random(len(s_idx)) < 0.52]
    frame(clicked, "product_clicked", 34, rank=rng.integers(1, 6, size=len(clicked)))

    shown = offers[offers["shown"].values]
    b_all = order_pos.reindex(shown["session_id"].values).values.astype(int)
    b_keep = inst[b_all]
    b_idx = b_all[b_keep]
    b_offer = shown["offer_id"].values[b_keep]
    frame(b_idx, "banner_impression", 22, banner=b_offer)
    bc = rng.random(len(b_idx)) < 0.19
    frame(b_idx[bc], "banner_clicked", 40, banner=b_offer[bc])

    coup = orders_i[orders_i["discount"].values > 0]["session_id"].values
    frame(order_pos.reindex(coup).values.astype(int), "coupon_applied", 88)

    it = items.merge(orders[["order_id", "session_id"]], on="order_id", how="left")
    a_all = order_pos.reindex(it["session_id"].values).values.astype(int)
    a_keep = inst[a_all]
    a_idx = a_all[a_keep]
    frame(a_idx, "add_to_cart", 55, sku=it["sku_id"].values[a_keep],
          cart=("CART-" + it["order_id"].astype(str)).values[a_keep])

    rm = rng.random(len(a_idx)) < 0.07
    frame(a_idx[rm], "remove_from_cart", 62)
    frame(o_idx, "cart_viewed", 70)
    frame(o_idx, "recommendation_impression", 73)
    frame(o_idx[orders_i["has_magnum"].values], "recommendation_accepted", 79)
    frame(o_idx, "checkout_demo_clicked", 96)

    built = pd.concat(frames, ignore_index=True)
    # Top up to the documented volume with ranked result impressions rather than
    # emitting one row per impression, which would dwarf every other event type.
    remaining = max(0, target - len(built))
    if remaining:
        per = 3
        pick = rng.choice(inst_idx, size=int(np.ceil(remaining / per)), replace=True)
        pick = np.repeat(pick, per)[:remaining]
        ranks = np.tile(np.arange(1, per + 1), int(np.ceil(remaining / per)))[:remaining]
        skus = rng.choice([p["sku_id"] for p in cat.PRODUCTS], size=remaining)
        built = pd.concat([built, pd.DataFrame({
            "event_time": t0[pick] + np.timedelta64(26, "s"),
            "session_id": sid[pick], "customer_id": cid[pick], "context_id": ctxid[pick],
            "event_type": "result_impression", "query": None, "sku_id": skus,
            "rank": ranks, "banner_id": None, "cart_id": None,
            "policy_version": pol[pick], "experiment_arm": arm[pick],
        })], ignore_index=True)

    built = built.sort_values("event_time", kind="mergesort").reset_index(drop=True)
    built.insert(0, "event_id", ["EVT-%09d" % (i + 1) for i in range(len(built))])
    return built


# ==========================================================================
# 8. Temporal split, quality report and writers
# ==========================================================================

FIT_END_DAY = int(cfg.DAYS * 0.72)     # fit       : first 72% of the window
CAL_END_DAY = int(cfg.DAYS * 0.86)     # calibrate : next 14%, holdout is the last 14%
                          # holdout    : day 72-83


def split_for_day(day_idx):
    return np.where(day_idx < FIT_END_DAY, "fit",
                    np.where(day_idx < CAL_END_DAY, "calibrate", "holdout"))


def quality_report(customers, contexts, sessions, orders, items, offers, truth,
                   inv, notif, forecasts, events):
    mag_orders = orders[orders["has_magnum"]]
    nonsupp = offers[offers["eligible"].values]
    arm_rates = (nonsupp.groupby("arm_assigned")["converted"].agg(["mean", "count"])
                 .rename(columns={"mean": "attach_rate", "count": "decisions"}))
    ctrl = float(arm_rates.loc["none", "attach_rate"]) if "none" in arm_rates.index else float("nan")
    arm_rates["observed_uplift_pp"] = (arm_rates["attach_rate"] - ctrl) * 100

    true_by_arm = (truth[truth["eligible"].values]
                   .groupby("arm_assigned")["true_arm_uplift"].mean() * 100)

    inv_last = inv[inv["snapshot_time"] == inv["snapshot_time"].max()]
    hot = sessions.merge(orders[["session_id", "has_magnum"]], on="session_id", how="left")

    rep = {
        "generator_version": GENERATOR_VERSION,
        "policy_version": POLICY_VERSION,
        "seed": cfg.SEED,
        "market": {"region": cat.REGION, "states": cat.STATES, "currency": "USD",
                   "temperature_unit": "F"},
        "window": {"start": cfg.SIM_START.isoformat(), "end": cfg.SIM_END.isoformat(),
                   "weeks": cfg.WEEKS, "days": cfg.DAYS, "hours": cfg.HOURS},
        "row_counts": {
            "customers": int(len(customers)), "stores": len(cat.STORES),
            "products": len(cat.PRODUCTS), "contexts": int(len(contexts)),
            "sessions": int(len(sessions)), "orders": int(len(orders)),
            "order_items": int(len(items)), "inventory": int(len(inv)),
            "offers": int(len(offers)), "notifications": int(len(notif)),
            "forecasts": int(len(forecasts)), "events": int(len(events)),
            "ground_truth": int(len(truth)),
        },
        "funnel": {
            "session_to_order_rate": round(len(orders) / len(sessions), 4),
            "magnum_attach_rate": round(float(orders["has_magnum"].mean()), 4),
            "attach_rate_meal_led": round(float(
                orders[orders["intent_class"] == "attachment"]["has_magnum"].mean()), 4),
            "attach_rate_dessert_led": round(float(
                orders[orders["intent_class"] == "direct"]["has_magnum"].mean()), 4),
            "avg_order_total": round(float(orders["total"].mean()), 2),
            "avg_lines_per_order": round(float(orders["n_lines"].mean()), 2),
            "substitution_rate": round(float(mag_orders["was_substituted"].mean()), 4),
            "instrumented_session_share": round(float(sessions["instrumented"].mean()), 4),
        },
        "randomisation": {
            "arm_share": {k: round(v, 4) for k, v in
                          sessions["offer_arm_assigned"].value_counts(normalize=True).items()},
            "suppression_rate": round(float(offers["suppression_reason"].notna().mean()), 4),
            "mean_decision_reward_by_arm": {
                k: round(float(v), 4) for k, v in
                offers[offers["eligible"].values].groupby("arm_assigned")["decision_reward"].mean().items()},
            "observed_uplift_pp": {k: round(float(v), 3) for k, v in
                                   arm_rates["observed_uplift_pp"].items()},
            "true_uplift_pp": {k: round(float(v), 3) for k, v in true_by_arm.items()},
        },
        "inventory": {
            "stockout_hour_share": round(float(inv["is_stockout"].mean()), 4),
            "avg_on_hand_final": round(float(inv_last["on_hand"].mean()), 2),
            "total_waste_units": int(inv["waste"].sum()),
        },
        "splits": {k: int(v) for k, v in sessions["split"].value_counts().items()},
        "checks": [],
    }

    def check(name, ok, detail):
        rep["checks"].append({"check": name, "pass": bool(ok), "detail": detail})

    check("no null customer on a session", sessions["customer_id"].notna().all(), "")
    check("every order maps to a session",
          orders["session_id"].isin(sessions["session_id"]).all(), "")
    check("every order item maps to an order",
          items["order_id"].isin(orders["order_id"]).all(), "")
    check("on-hand never negative", bool((inv["on_hand"] >= 0).all()), "")
    check("voucher arm has the largest true uplift",
          float(true_by_arm.get("voucher20", 0)) == float(true_by_arm.max()),
          "voucher %.2f pp" % float(true_by_arm.get("voucher20", 0)))
    check("decision log carries no ground-truth column",
          not any(c in offers.columns for c in
                  ("p_base", "p_with_arm", "true_arm_uplift", "true_voucher_uplift")), "")
    check("observed and true uplift agree within 1.5pp for the voucher arm",
          abs(float(arm_rates["observed_uplift_pp"].get("voucher20", 0)) -
              float(true_by_arm.get("voucher20", 0))) < 1.5,
          "observed %.2f vs true %.2f" % (
              float(arm_rates["observed_uplift_pp"].get("voucher20", 0)),
              float(true_by_arm.get("voucher20", 0))))
    hot_cut = truth["temp_anomaly_f"].quantile(0.75)
    cold_cut = truth["temp_anomaly_f"].quantile(0.25)
    hot_attach = float(truth[truth["temp_anomaly_f"] >= hot_cut]["bought_magnum"].mean())
    cold_attach = float(truth[truth["temp_anomaly_f"] <= cold_cut]["bought_magnum"].mean())
    check("hot hours attach more than cold hours", hot_attach > cold_attach,
          "%.1f%% hot vs %.1f%% cold" % (100 * hot_attach, 100 * cold_attach))
    check("stockouts occur but stay under 12% of store-SKU-hours",
          0.0 < float(inv["is_stockout"].mean()) < 0.12,
          "%.2f%%" % (100 * float(inv["is_stockout"].mean())))
    check("no ground-truth column leaks into an application table",
          not any(c in sessions.columns or c in orders.columns
                  for c in ("p_magnum_base", "true_arm_uplift", "true_voucher_uplift")), "")
    return rep


TABLES = ["customers", "stores", "products", "contexts", "sessions", "events", "orders",
          "order_items", "inventory", "offers", "notifications", "forecasts",
          "latent_traits", "ground_truth"]


def write_all(frames, report):
    os.makedirs(DATA, exist_ok=True)
    for name, df in frames.items():
        path = os.path.join(DATA, name + ".csv")
        df.to_csv(path, index=False)
        log("%-16s %9s rows  %7.1f MB" % (name, f"{len(df):,}",
                                          os.path.getsize(path) / 1e6))
    db = os.path.join(DATA, "magnum.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    for name, df in frames.items():
        df.to_sql(name, con, index=False)
    idx = [
        "CREATE INDEX ix_sessions_customer ON sessions(customer_id)",
        "CREATE INDEX ix_sessions_time ON sessions(start_time)",
        "CREATE INDEX ix_orders_customer ON orders(customer_id)",
        "CREATE INDEX ix_orders_session ON orders(session_id)",
        "CREATE INDEX ix_items_order ON order_items(order_id)",
        "CREATE INDEX ix_events_session ON events(session_id)",
        "CREATE INDEX ix_events_type ON events(event_type)",
        "CREATE INDEX ix_inventory_store_sku ON inventory(store_id, sku_id)",
        "CREATE INDEX ix_inventory_time ON inventory(snapshot_time)",
        "CREATE INDEX ix_contexts_store_time ON contexts(store_id, timestamp)",
        "CREATE INDEX ix_offers_session ON offers(session_id)",
        "CREATE INDEX ix_forecasts_store_sku ON forecasts(store_id, sku_id)",
    ]
    for stmt in idx:
        con.execute(stmt)
    con.commit()
    con.close()
    log("sqlite            %7.1f MB  %s" % (os.path.getsize(db) / 1e6, db))
    with open(os.path.join(DATA, "data_quality.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)


def main():
    t0 = time.time()
    rng = np.random.default_rng(cfg.SEED)
    print("Magnum Commerce POC - synthetic data generator")
    print("  market %s | seed %d | %d weeks to %s\n" % (
        cat.REGION, cfg.SEED, cfg.WEEKS, cfg.SIM_END.date()))

    log("1/8 customers and latent traits")
    customers, traits, tr = build_customers(rng)

    log("2/8 hourly store context")
    contexts, grid = build_contexts(rng)

    log("3/8 sessions")
    sessions = build_sessions(rng, customers, tr, grid)

    log("4/8 simulation walk (orders, baskets, inventory, decisions)")
    orders, items, offers, truth, inv, state = simulate(rng, customers, tr, sessions, grid)

    sessions["split"] = split_for_day(sessions["day_idx"].values)
    orders = orders.merge(sessions[["session_id", "split", "day_idx"]], on="session_id", how="left")
    truth = truth.merge(sessions[["session_id", "split"]], on="session_id", how="left")

    log("5/8 reorder candidates")
    notif = build_notifications(rng, customers, tr, state)

    log("6/8 baseline demand forecast")
    forecasts = build_forecasts(rng, contexts, orders, items, inv)

    log("7/8 event stream")
    events = build_events(rng, sessions, orders, items, offers)

    log("8/8 quality report and write")
    stores = pd.DataFrame(cat.STORES)
    products = pd.DataFrame(cat.PRODUCTS)
    products["tags"] = products["tags"].apply(lambda x: "|".join(x))
    products["search_terms"] = products["search_terms"].apply(lambda x: "|".join(x))
    products["pairs"] = products["pairs"].apply(lambda x: "|".join(x))

    sessions_out = sessions.drop(columns=["customer_idx", "area_idx"])
    report = quality_report(customers, contexts, sessions, orders, items, offers, truth,
                            inv, notif, forecasts, events)
    frames = {
        "customers": customers, "stores": stores, "products": products,
        "contexts": contexts, "sessions": sessions_out, "events": events,
        "orders": orders, "order_items": items, "inventory": inv, "offers": offers,
        "notifications": notif, "forecasts": forecasts,
        "latent_traits": traits, "ground_truth": truth,
    }
    write_all(frames, report)

    print("\n  funnel   %s sessions -> %s orders (%.1f%%), Magnum attach %.1f%%" % (
        f"{len(sessions):,}", f"{len(orders):,}",
        100 * len(orders) / len(sessions), 100 * orders["has_magnum"].mean()))
    print("  uplift   observed %s" % report["randomisation"]["observed_uplift_pp"])
    print("           true     %s" % report["randomisation"]["true_uplift_pp"])
    print("  stock    %.2f%% of store-SKU-hours out of stock" %
          (100 * report["inventory"]["stockout_hour_share"]))
    failed = [c for c in report["checks"] if not c["pass"]]
    print("  checks   %d/%d passed%s" % (
        len(report["checks"]) - len(failed), len(report["checks"]),
        "" if not failed else "  FAILED: " + ", ".join(c["check"] for c in failed)))
    print("\n  done in %.1fs" % (time.time() - t0))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
