"""Magnum Now - decision API.

Nine product endpoints (section 8.3), a set of analysis endpoints behind
/api/analysis, and a read-only data explorer. Every product endpoint returns
reason codes alongside its numbers: a recommendation the reviewer cannot
interrogate is not evidence of anything.
"""
from __future__ import annotations

import os
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from magnum_core import (POLICY_VERSION, FORECAST_VERSION, GENERATOR_VERSION,  # noqa: E402
                         CURRENCY, SEED)
from magnum_core import catalog as cat          # noqa: E402
from magnum_core import context as cx           # noqa: E402
from magnum_core import policies as pol         # noqa: E402
from magnum_core import profiles as pf          # noqa: E402
from magnum_core import reasons as rsn          # noqa: E402
from generator import config as gcfg            # noqa: E402

from .store import (get_store, store_if_built, BROWSABLE, HELD_OUT_TABLES,  # noqa: E402
                    _con, NOW)
from . import notify as ntf  # noqa: E402
from . import analysis                                              # noqa: E402
from . import impact                                                 # noqa: E402
from . import customer as cust                                       # noqa: E402

UBER_ADAPTER_ENABLED = os.environ.get("UBER_ADAPTER_ENABLED", "false").lower() == "true"

app = FastAPI(title="Magnum Now decision API", version=POLICY_VERSION)
# The UI is served from this same origin, so the browser never issues a
# cross-origin request and this middleware is doing nothing in the normal path.
# It stays for the one case that still needs it - a developer running Vite on
# :5173 against this API - and it is scoped to exactly that, rather than left
# open to every origin on the internet on something we intend to deploy.
_CORS_ORIGINS = [o for o in os.environ.get(
    "MAGNUM_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])

EVENT_SINK: deque = deque(maxlen=500)      # in-memory; the golden log is never written to


@app.on_event("startup")
def _warm():
    """Build the features and pre-compute the analysis panels off the request
    path, so the first click on a tab is not the first read of the log."""
    import threading

    def run():
        get_store()
        for fn in (analysis.overview, analysis.uplift, analysis.policy_eval,
                   analysis.forecast_accuracy, analysis.demand_drivers,
                   analysis.stockouts, analysis.validation):
            try:
                fn()
            except Exception:
                pass

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# contracts
# ---------------------------------------------------------------------------
class ContextSel(BaseModel):
    day: str = "friday"
    time_window: str = "dinner"
    season: str = "summer"
    weather: str = "hot"
    game_day: bool = True
    event: str = "none"
    activity: str = "high"
    area_id: str = "upper-east-side"
    hour: Optional[int] = None


class CartLine(BaseModel):
    sku_id: str
    quantity: int = 1


class SearchReq(BaseModel):
    query: str = ""
    category: Optional[str] = None
    customer_id: Optional[str] = None
    context: ContextSel = Field(default_factory=ContextSel)
    cart: List[CartLine] = Field(default_factory=list)
    limit: int = 24
    # The Magnum rail is ranked independently of the query and the category
    # filter, so it never goes empty while the shopper browses drinks.
    magnum_rail: int = 2


class CartReq(BaseModel):
    customer_id: Optional[str] = None
    context: ContextSel = Field(default_factory=ContextSel)
    cart: List[CartLine] = Field(default_factory=list)


class OfferReq(BaseModel):
    customer_id: Optional[str] = None
    context: ContextSel = Field(default_factory=ContextSel)
    cart: List[CartLine] = Field(default_factory=list)
    recommended_sku: Optional[str] = None
    override_contacts_7d: Optional[int] = None
    override_consent: Optional[bool] = None
    # The guardrail panel drives these so a reviewer can watch restraint switch
    # on and off without waiting for a household's real recency to change.
    override_hours_since_order: Optional[float] = None


class EventIn(BaseModel):
    event_type: str
    session_id: Optional[str] = None
    customer_id: Optional[str] = None
    context_id: Optional[str] = None
    query: Optional[str] = None
    sku_id: Optional[str] = None
    rank: Optional[int] = None
    banner_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class EventsReq(BaseModel):
    events: List[EventIn]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
# How hard the serving policy leans on a measured occasion lift. Half, on the
# same principle as every other borrowed coefficient in this system: the log is
# one network's worth of evidence and the policy should lean on it, not lunge.
OCCASION_PULL = 0.5


def _ctx(sel: ContextSel) -> Dict:
    ctx = cx.resolve(day=sel.day, time_window=sel.time_window, season=sel.season,
                     weather=sel.weather, game_day=sel.game_day, event=sel.event,
                     activity=sel.activity, area_id=sel.area_id, hour=sel.hour)
    _add_occasion(ctx)
    return ctx


def _add_occasion(ctx: Dict) -> None:
    """Attach what the day of the week and the match window measurably do.

    The day was reaching the ranking through exactly one two-step function
    (`group_bias` steps once at Friday) and reaching the price not at all, so six
    of the seven days were interchangeable. The log has a great deal more to say
    than that. `Store.occasion_profile` measures, per day and for the match
    window, how often a basket takes a pack rather than a single, how many bars
    come home, and which flavours over-index — each as a lift against the same
    quantity over the whole log.

    Day and match window overlap (match windows cluster on particular days), so
    the two are combined in *deviations from 1.0* rather than multiplied, which
    would count the overlap twice.
    """
    prof = getattr(get_store(), "occasion_profile", None)
    ctx["occasion_terms"] = []
    ctx["occasion_pack_lift"] = 1.0
    ctx["occasion_bars_lift"] = 1.0
    ctx["occasion_flavour_lift"] = {}
    if not prof:
        return

    slices = []
    day = prof["by_day"].get(int(ctx.get("day_of_week") or 0))
    if day:
        slices.append((day, "OCCASION_DAY", str(ctx.get("day") or "").title(),
                       "%s baskets, measured across %s of them." % (
                           str(ctx.get("day") or "this day").title(), "{:,}".format(day["n"]))))
    if ctx.get("in_game_window") and prof["game"]["n"]:
        slices.append((prof["game"], "OCCASION_MATCH", "Match window",
                       "Baskets placed while a game is on, measured across "
                       "{:,} of them.".format(prof["game"]["n"])))

    pack = bars = 1.0
    flav: Dict[str, float] = {}
    for sl, code, label, detail in slices:
        pack += (sl["pack_lift"] - 1.0) * OCCASION_PULL
        bars += (sl["bars_lift"] - 1.0) * OCCASION_PULL
        for f, v in sl["flavour_lift"].items():
            flav[f] = flav.get(f, 1.0) + (v - 1.0) * OCCASION_PULL
        top = max(sl["flavour_lift"].items(), key=lambda kv: kv[1], default=(None, 1.0))
        ctx["occasion_terms"].append({
            "code": code, "label": label, "detail": detail,
            "pack_lift": sl["pack_lift"], "bars_lift": sl["bars_lift"],
            "top_flavour": top[0], "top_flavour_lift": top[1], "n": sl["n"],
        })
    ctx["occasion_pack_lift"] = round(pack, 4)
    ctx["occasion_bars_lift"] = round(bars, 4)
    ctx["occasion_flavour_lift"] = {f: round(v, 4) for f, v in flav.items()}


def _who(customer_id: Optional[str]):
    st = get_store()
    cf = st.features(customer_id) if customer_id else None
    clf = st.cluster(cf["peer_cluster"]) if cf else None
    return st, cf, clf


def _lines(cart: List[CartLine]) -> List[Dict]:
    return [{"sku_id": l.sku_id, "quantity": int(l.quantity)} for l in cart]


def _basket_value(lines: List[Dict]) -> float:
    return round(sum(cat.PRODUCT_BY_ID[l["sku_id"]]["price"] * l["quantity"]
                     for l in lines if l["sku_id"] in cat.PRODUCT_BY_ID), 2)


def _decorate(reason_codes: List[str]) -> List[Dict]:
    return rsn.explain_all(reason_codes)



# Query chips, one per dish worth searching for. The word is what a shopper
# would actually type; the SKU behind it is what gives the chip its character,
# so the ordering is derived from the catalogue rather than hand-maintained.
SUGGEST_SEEDS = [
    ("pizza", "MEA-PIZ-L"), ("pepperoni", "MEA-PIZ-P"), ("wings", "MEA-WNG-8"),
    ("chicken over rice", "MEA-HAL-1"), ("burger", "MEA-BUR-B"), ("hero", "MEA-HER-I"),
    ("chips and salsa", "SID-CHP-S"), ("mozzarella sticks", "SID-MOZ-6"),
    ("garlic knots", "SID-KNO-6"), ("fries", "SID-FRY-1"),
    ("ice cream", None), ("magnum", None),
]


def _season_note(season: str, di: float) -> str:
    """One line on why coupons are generous or stingy right now."""
    s = (season or "").title() or "This season"
    if di >= 1.15:
        return ("%s peak — demand is doing the selling, so coupons go shallow or "
                "disappear entirely." % s)
    if di <= 0.95:
        return ("%s lull — orders are running below normal, so the coupon goes deeper "
                "to move the stock." % s)
    return "%s, trading around normal — the coupon sits near its usual depth." % s


def _coupon_view(decision: Optional[Dict], ctx: Dict) -> Dict:
    """The coupon in a shopper's words, or an honest account of why there is none.

    A discount that appears, moves and vanishes without saying why reads as a bug
    or as arbitrary pricing. And the interesting half of this system is the half
    that declines to discount, so the absence needs copy every bit as much as the
    presence does.
    """
    di = float(ctx.get("demand_index") or 1.0)
    season = str(ctx.get("season") or "")
    trading = "orders are running {:.0f}% {} normal for this hour".format(
        abs(di - 1.0) * 100.0, "above" if di >= 1.0 else "below")
    note = _season_note(season, di)
    off = (decision or {}).get("offer")
    # Every branch below gets to name the slot it is deciding in. A price that
    # stays the same across two different nights is a defensible answer; a price
    # whose *explanation* is byte-identical across two different nights just
    # looks like the screen ignored the change. The number can hold still. The
    # sentence has to move.
    when = "{} {}".format(str(ctx.get("day") or "This day").title(),
                          str(ctx.get("time_window_label") or ctx.get("time_window") or "")).strip()
    occ_bits = [t["label"].lower() for t in (ctx.get("occasion_terms") or [])]
    occ_phrase = " and ".join(occ_bits) if occ_bits else when.lower()

    if off and float(off.get("discount_pct") or 0) > 0:
        base = float(off.get("base_discount_pct") or off["discount_pct"])
        dr = off.get("depth_reason")
        # Each of these three lines is one *component* of the depth, not a claim
        # about where it ended up - the label already says that. Writing them as
        # verdicts ("held at the usual 20%") put a sentence next to a 17% coupon
        # that flatly contradicted it, because two later terms had moved the
        # number after this one was decided.
        if dr == "OFFER_DEEPER_SLOW_DEMAND":
            why = ("The hour pushes it below the usual {:.0f}% — {}, so the coupon has "
                   "to buy the volume.".format(base * 100.0, trading))
        elif dr == "OFFER_TRIMMED_BUSY_DEMAND":
            why = ("The hour trims it from the usual {:.0f}% — {}, so we are not paying "
                   "for orders that were coming anyway.".format(base * 100.0, trading))
        else:
            why = ("The hour leaves it near the usual {:.0f}% — {}.".format(
                base * 100.0, trading))
        parts = off.get("depth_parts") or {}
        slot = {
            "OFFER_TRIMMED_BUSY_SLOT": ("{} {} is one of the busier slots of the week "
                                        "in its own right, which trims it further."),
            "OFFER_DEEPER_QUIET_SLOT": ("{} {} is one of the quieter slots of the week, "
                                        "so the coupon goes deeper again."),
        }.get(parts.get("slot_code"))
        if slot:
            slot = slot.format(str(ctx.get("day") or "This day").title(),
                               str(ctx.get("time_window_label") or ctx.get("time_window") or ""))
        hh = {
            "OFFER_DEEPER_LAPSED": ("They are past their own reorder rhythm, so this one "
                                    "goes deeper to win the trip back."),
            "OFFER_TRIMMED_EARLY": ("They are ahead of their own rhythm — already coming "
                                    "back, so the note stays light."),
            "OFFER_TRIMMED_FULL_PRICE": ("This household mostly pays full price, so we do "
                                         "not spend much buying a decision they were "
                                         "already making."),
            "OFFER_DEEPER_PRICE_LED": ("This household buys on offer more often than most, "
                                       "so the note is the part that does the work."),
        }.get(off.get("household_depth_reason"))
        return {"has_coupon": True, "kind": "discount", "label": off.get("label"),
                "code": off.get("offer_id"), "discount_pct": off.get("discount_pct"),
                "base_discount_pct": base, "saving": off.get("discount_value"),
                "why": why, "slot": slot, "who": hh,
                "depth_parts": parts, "season_note": note}

    if off:
        return {"has_coupon": True, "kind": "no_discount", "label": off.get("label"),
                "code": off.get("offer_id"), "discount_pct": 0.0,
                "base_discount_pct": 0.0, "saving": 0.0,
                "why": ("No money off on {}. This household buys at full price, so a "
                        "discount would spend margin it was never going to "
                        "need.".format(when)),
                "slot": ("What moves instead is the pick itself — {} baskets are what "
                         "ranked this one to the top.".format(occ_phrase)),
                "who": None, "depth_parts": {}, "season_note": note}

    reason = (decision or {}).get("suppression_reason") or ""
    why = {
        "NO_MARKETING_CONSENT": "No coupon — no marketing consent on file.",
        "FREQUENCY_CAPPED": "No coupon — this household has hit its contact cap.",
        "POST_PURCHASE_SUPPRESS": "No coupon — they ordered in the last few hours.",
        "OFFER_MARGIN_NEGATIVE": ("No coupon on {} — {}, so every arm costs more in "
                                  "discount than it returns in extra "
                                  "orders.".format(when, trading)),
        "OFFER_UPLIFT_BELOW_THRESHOLD": (
            "No coupon on {} — {}. At that level the shallow price this hour can "
            "afford would not move this household enough to pay for "
            "itself.".format(when, trading)),
    }.get(reason, "No coupon — nothing on the shelf clears the margin bar right now.")
    return {"has_coupon": False, "kind": "none",
            "label": "No coupon · {}".format(when),
            "code": None,
            "discount_pct": 0.0, "base_discount_pct": 0.0, "saving": 0.0,
            "why": why,
            "slot": ("The pick and the size are still moving — {} baskets are what "
                     "put this one first.".format(occ_phrase)),
            "who": None, "depth_parts": {},
            "season_note": note}


SUGGEST_SEEDS = [
    ("pizza", "MEA-PIZ-L"), ("pepperoni pizza", "MEA-PIZ-P"), ("wings", "MEA-WNG-8"),
    ("chicken over rice", "MEA-HAL-1"), ("burger", "MEA-BUR-B"), ("italian hero", "MEA-HER-I"),
    ("chips and salsa", "SID-CHP-S"), ("mozzarella sticks", "SID-MOZ-6"),
    ("garlic knots", "SID-KNO-6"), ("fries", "SID-FRY-1"),
    ("ice cream", None), ("magnum", None),
]


def _suggest_score(p: Optional[Dict], ctx: Dict, fav: Optional[str],
                   cf: Optional[Dict] = None, clf: Optional[Dict] = None) -> Dict:
    """Score one seed against the hour, and keep the arithmetic that produced it.

    Every term is kept rather than collapsed into a number, because the chip has
    to be able to say why it is where it is. A suggestion that cannot explain
    itself is just a shortcut.
    """
    heat = float(ctx.get("heat_pull") or 0.6)
    group = float(ctx.get("group_bias") or 0.0)
    game = bool(ctx.get("in_game_window"))
    rain = float(ctx.get("rain_in") or 0.0)
    late = int(ctx.get("hour") or 18) >= 21
    terms: List[Dict] = []

    def add(label, points, detail):
        if abs(points) >= 0.01:
            terms.append({"label": label, "points": round(points, 3), "detail": detail})

    if p is None:
        base = 0.55 + 0.70 * (heat - 0.62)
        add("Heat", 0.70 * (heat - 0.62),
            "{:.0f}°F — frozen dessert searches climb with the temperature.".format(
                ctx.get("temperature_f", 0)))
        return {"score": base, "terms": terms}

    spice = float(p.get("spice") or 0.0)
    share = 1.0 if p.get("is_shareable") else 0.0
    score = 0.40
    v = 0.55 * spice * max(0.0, heat - 0.45) * 2.0
    score += v
    add("Spice in the heat", v,
        "{:.0f}°F and this is a hot dish — spicy food sells harder in the heat, and "
        "it pulls a cold dessert with it.".format(ctx.get("temperature_f", 0)))
    v = 0.45 * share * group
    score += v
    add("Group ordering", v,
        "The occasion reads as a group — shareable plates run {:.0f}% above "
        "normal.".format(group * 100.0))
    if game:
        v = 0.35 * share
        score += v
        add("Match day", v,
            "The game window is open. Baskets built for a match run larger, so the "
            "size recommendation moves up with them.")
    if rain > 0.02:
        v = 0.22 * (1.0 - share)
        score += v
        add("Rain", v,
            "{:.2f} in of rain — delivery skews to smaller, solo orders.".format(rain))
    if late:
        v = 0.20 * (1.0 - abs(float(p.get("portion_size") or 1.0) - 1.2) / 2.0)
        score += v
        add("Late hour", v, "Past 9 PM the smaller plates take over.")
    # The household's own weight. This used to be a rounding term, which meant
    # three very different households were shown the same two chips on a hot
    # night - the weather drowned out the person. The point of the panel is that
    # it is *their* panel, so their history has to be able to move the order.
    pairs = p.get("pairs") or []
    fav_share = float((cf or {}).get("flavour_shares", {}).get(fav or "", 0.0))
    if fav and pairs:
        if pairs[0] == fav:
            v = 0.55 + 0.45 * fav_share
            score += v
            add("Previously paired", v,
                "This dish's strongest partner is {}, and {:.0%} of the Magnum units "
                "this household buys are {}.".format(fav, fav_share, fav))
        elif fav in pairs:
            v = 0.28 + 0.22 * fav_share
            score += v
            add("Previously paired", v,
                "This dish pairs with {}, which is this household's top flavour at "
                "{:.0%} of their units.".format(fav, fav_share))
    elif fav and not pairs:
        score -= 0.18
        add("No pairing history", -0.18,
            "Nothing in the log links this dish to a Magnum flavour, so it cannot "
            "argue for one.")

    # What they actually order. A household whose basket is 60% mains should not
    # be led with a side, however well that side scores on the weather.
    csh = (cf or {}).get("category_shares") or {}
    ccat = p.get("category")
    if csh and ccat:
        share = float(csh.get(ccat, 0.0))
        v = 0.85 * (share - 0.22)
        score += v
        add("What they order", v,
            "{:.0%} of everything this household buys is from the {} aisle.".format(
                share, ccat))

    # What households like this one actually put in the basket, measured off the
    # order log rather than read out of a generator parameter. Kept deliberately
    # small: peers inform, they do not decide.
    shares = ((clf or {}).get("sku_shares") or {}) if clf else {}
    if shares and p.get("sku_id") in shares:
        share = float(shares[p["sku_id"]])
        v = 1.20 * (share - 0.09)
        score += v
        add("Similar shoppers", v,
            "This dish is {:.1%} of everything households like this one order.".format(share))
    return {"score": score, "terms": terms}


def _suggestions(ctx: Dict, cf: Optional[Dict], clf: Optional[Dict],
                 limit: int = 7) -> List[Dict]:
    """What to offer as a next search, ordered by the hour rather than by habit.

    These chips are shortcuts and nothing more - the worked answer, with a size
    and a coupon on it, belongs on the rail where the shopper is looking. What a
    chip still owes is the reason it is where it is: a shopper who has typed
    nothing has given the system almost no signal, so the order of this row is
    the clearest statement it makes about what it thinks is going on, and it has
    to move when any of that moves.
    """
    fav = None
    if cf:
        shares = cf.get("flavour_shares") or {}
        if shares:
            fav = max(shares, key=lambda k: shares[k])

    out = []
    for word, sku in SUGGEST_SEEDS:
        p = cat.PRODUCT_BY_ID.get(sku) if sku else None
        r = _suggest_score(p, ctx, fav, cf, clf)
        terms = sorted(r["terms"], key=lambda t: -t["points"])
        out.append({"query": word, "sku_id": sku,
                    "score": round(r["score"], 4),
                    "why": terms[0]["label"] if terms else "Popular here",
                    "why_detail": terms[0]["detail"] if terms else "",
                    "factors": terms})
    out.sort(key=lambda r: (-r["score"], r["query"]))
    for i, r in enumerate(out[:limit]):
        r["rank"] = i + 1
    return out[:limit]


def _signals(ctx: Dict, cf: Optional[Dict]) -> List[Dict]:
    """The terms currently pushing the ranking around, each with its direction
    and the size of its push. These are read off the resolved context and the
    household features - nothing is estimated here that the ranker does not
    already use."""
    out: List[Dict] = []

    def add(code, label, value, effect, detail):
        out.append({"code": code, "label": label, "value": value,
                    "effect": round(effect, 3),
                    "direction": "up" if effect > 0 else ("down" if effect < 0 else "flat"),
                    "detail": detail})

    heat = ctx["heat_pull"]
    add("CONTEXT_HEAT", "Temperature", "%d°F" % round(ctx["temperature_f"]),
        (heat - 0.62) * 2.6,
        "Frozen dessert affinity scales with absolute heat, not just the anomaly.")
    if abs(ctx["temp_anomaly_f"]) >= 4:
        add("CONTEXT_ANOMALY", "Vs seasonal norm",
            "%+.1f°F" % ctx["temp_anomaly_f"], ctx["temp_anomaly_f"] / 20.0,
            "Unusual for the season, which moves demand on top of the level.")
    if ctx["in_game_window"]:
        add("CONTEXT_GAME", "Game window", "live", 0.60,
            "Shareable formats and multipacks are pulled up inside the window.")
    if ctx["is_weekend"]:
        add("CONTEXT_WEEKEND", "Weekend", ctx["day"], 0.20, "Larger baskets, later peak.")
    if ctx["event"] != "none":
        ev = cx.EVENT_BY_ID[ctx["event"]]
        add("CONTEXT_EVENT", "Occasion", ev["label"], ev["group_bias"],
            "Group bias raises inferred head count, which raises pack rank.")
    w = cx.WEATHER_BY_ID[ctx["weather"]]
    if w["multiplier"] != 1.0:
        add("CONTEXT_WEATHER", "Weather", w["label"], w["multiplier"] - 1.0,
            "Weather multiplier on the shared demand model.")
    a = cx.ACTIVITY_BY_ID[ctx["activity"]]
    if a["multiplier"] != 1.0:
        add("CONTEXT_ACTIVITY", "Area activity", a["label"], a["multiplier"] - 1.0,
            "Neighborhood footfall for this hour.")
    if cf:
        top = sorted(cf["flavour_shares"].items(), key=lambda kv: -kv[1])[:1]
        if top:
            add("PERSONAL_FLAVOUR", "Household flavour", top[0][0],
                top[0][1], "%.0f%% of this household's Magnum orders." % (top[0][1] * 100))
        if cf["due_ratio"] >= 0.85:
            add("PERSONAL_DUE", "Reorder due", "%.2f× cadence" % cf["due_ratio"],
                min(0.5, cf["due_ratio"] - 0.85), "Past the household's own rhythm.")
    return out


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    # Deliberately `store_if_built`, not `get_store`: this has to answer while
    # the first build is still running. Calling `get_store` here made health
    # queue behind the build - the one request that most needs to reply during
    # a cold start was the one that could not.
    st = store_if_built()
    if st is None or not st.ready:
        return {"status": "loading", "policy_version": POLICY_VERSION, "loaded_in_s": None}
    return {"status": "ok", "policy_version": POLICY_VERSION,
            "loaded_in_s": round(st.loaded_in, 2)}


@app.get("/api/meta")
def meta():
    st = get_store()
    con = _con()
    counts = {t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in BROWSABLE}
    con.close()
    return {
        "product": "Magnum Now",
        "disclaimer": ("Uber Eats-inspired reference build. Not an Uber product, not "
                       "affiliated with or endorsed by Uber. All data is synthetic."),
        "market": cat.REGION, "states": cat.STATES, "currency": CURRENCY,
        "policy_version": POLICY_VERSION, "forecast_version": FORECAST_VERSION,
        "generator_version": GENERATOR_VERSION, "seed": SEED,
        "window": {"start": gcfg.SIM_START.isoformat(), "end": gcfg.SIM_END.isoformat(),
                   "weeks": gcfg.WEEKS, "days": gcfg.DAYS},
        "now": NOW.isoformat(),
        "row_counts": counts,
        "held_out_tables": sorted(HELD_OUT_TABLES),
        "uplift_fit_rows": st.uplift_fit_rows,
        "feature_flags": {"uber_adapter_enabled": UBER_ADAPTER_ENABLED},
        "quality": st.quality.get("checks", []),
    }


@app.get("/api/catalog")
def catalog():
    return {
        "products": cat.PRODUCTS, "categories": cat.CATEGORIES,
        "stores": cat.STORES, "areas": cat.AREAS,
        "magnum_skus": cat.MAGNUM_SKUS, "pack_units": cat.PACK_UNITS,
    }


@app.get("/api/reasons")
def reason_vocabulary():
    return {"reasons": [{"code": k, **v} for k, v in rsn.REASONS.items()]}


@app.get("/api/context/options")
def context_options():
    return {
        "days": cx.DAYS, "time_windows": cx.TIME_WINDOWS, "seasons": cx.SEASONS,
        "weather": cx.WEATHER, "events": cx.EVENTS, "activity": cx.ACTIVITY,
        "areas": cat.AREAS,
        "plausible_weather": {s["id"]: cx.plausible_weather(s["id"]) for s in cx.SEASONS},
    }


# ---------------------------------------------------------------------------
# 1. demo profiles
# ---------------------------------------------------------------------------
@app.get("/api/demo/profiles")
def demo_profiles():
    st = get_store()
    out = []
    for p in pf.DEMO_PROFILES:
        cf = st.features(p["customer_id"])
        if not cf:
            continue
        clf = st.cluster(cf["peer_cluster"])
        top = sorted(cf["flavour_shares"].items(), key=lambda kv: -kv[1])[:2]
        out.append({
            **p,
            "features": cf,
            "cluster": {"id": clf["cluster_id"], "name": clf["name"], "short": clf["short"],
                        "customers": clf["customers"], "attach_rate": clf["attach_rate"],
                        "avg_units": clf["avg_units"], "peak_hour": clf["peak_hour"]},
            "top_flavours": [{"flavour": k, "share": v} for k, v in top],
            "contacts_7d": int(st.contacts_7d.get(p["customer_id"], 0)),
        })
    return {"profiles": out, "guest": {"customer_id": None, "display_name": "Guest",
                                       "note": "No history: quantity falls back to peer and occasion."}}


# ---------------------------------------------------------------------------
# 2. context
# ---------------------------------------------------------------------------
@app.post("/api/context/resolve")
def context_resolve(sel: ContextSel):
    ctx = _ctx(sel)
    st = get_store()
    drivers = []
    if ctx["heat_pull"] >= 0.72:
        drivers.append({"code": "CONTEXT_HEAT", "weight": round((ctx["heat_pull"] - 0.62) * 2.6, 2)})
    if ctx["in_game_window"]:
        drivers.append({"code": "CONTEXT_GAME", "weight": 0.60})
    if ctx["is_weekend"]:
        drivers.append({"code": "CONTEXT_WEEKEND", "weight": 0.20})
    if ctx["event"] != "none":
        drivers.append({"code": "CONTEXT_EVENT", "weight": cx.EVENT_BY_ID[ctx["event"]]["group_bias"]})
    if ctx["weather"] in ("rain", "snow", "cool"):
        drivers.append({"code": "CONTEXT_COLD", "weight": round(cx.WEATHER_BY_ID[ctx["weather"]]["multiplier"] - 1, 2)})
    return {
        "context": ctx,
        "store": cat.STORE_BY_AREA.get(sel.area_id),
        "drivers": [{**d, **rsn.explain(d["code"])} for d in drivers],
        "hours": cx.snapshot_hours(ctx, 48),
        "peak": cx.peak_window(cx.snapshot_hours(ctx, 48)),
        "stock_snapshot_at": st.inventory_time,
    }


# ---------------------------------------------------------------------------
# 3. search
# ---------------------------------------------------------------------------
def _pairing_summary(anchors, st) -> Optional[Dict]:
    """What the pairing term is currently keyed to, in words the screen can use."""
    if not anchors:
        return None
    base = getattr(st, "pair_base", {}) or {}
    mix = base.get("flavour_mix", {})
    pulled = {}
    tot = sum(a.get("weight", 1.0) for a in anchors) or 1.0
    for f in mix:
        pulled[f] = round(sum(a["flavour_lift"].get(f, 1.0) * a.get("weight", 1.0)
                              for a in anchors) / tot, 3)
    top = max(pulled, key=pulled.get) if pulled else None
    units = round(sum(a.get("units_ratio", 1.0) * a.get("weight", 1.0)
                      for a in anchors) / tot, 3)
    return {
        "active": True,
        "weight": pol.W_PAIR,
        "anchors": [{"sku_id": a.get("sku_id"), "name": a.get("name"),
                     "source": a.get("source"), "n": a.get("n"),
                     "top_flavour": a.get("top_flavour"),
                     "top_lift": a.get("top_lift"),
                     "units_ratio": a.get("units_ratio")} for a in anchors],
        "flavour_pull": pulled,
        "top_flavour": top,
        "top_lift": pulled.get(top),
        "units_ratio": units,
        "baseline_units": base.get("avg_units"),
        "baskets": sum(a.get("n", 0) or 0 for a in anchors),
    }


@app.post("/api/search")
def search(req: SearchReq):
    t0 = time.time()
    ctx = _ctx(req.context)
    st, cf, clf = _who(req.customer_id)
    stock = st.store_stock(ctx["store_id"])
    lines = _lines(req.cart)
    # Rank the aisle first with no pairing term - it decides what the shopper is
    # actually looking at, and the anchors are read off that. Pairing the grid to
    # itself would be circular; the grid answers the query, the rail answers the
    # grid.
    ranked = pol.rank_products(req.query, ctx, cf, clf, stock, category=req.category,
                               cart_lines=lines, limit=req.limit)
    for r in ranked:
        r["reasons"] = _decorate(r.get("reason_codes", []))
    intent = pol.classify_intent(req.query, lines, ctx)

    # Only what the shopper actually asked for counts as an anchor. An
    # unfiltered browse of the whole aisle is not "looking at" anything, and
    # letting the first four rows of it anchor the rail meant a shopper who had
    # typed nothing still got pizza-flavoured logic off whichever drinks happened
    # to sort high.
    looking = bool(req.query) or bool(req.category and req.category != "magnum")
    on_screen = [r["sku_id"] for r in ranked if r["category"] != "magnum"] if looking else []
    anchors = pol.build_anchors(lines, on_screen, req.category,
                                st.pair_table, st.pair_by_category)

    # The rail is the same ranker with the text term stood down: whatever the
    # shopper is looking at, this is what the system would place for Magnum in
    # this context, for this household, right now.
    rail = pol.rank_products("", ctx, cf, clf, stock, category="magnum",
                             cart_lines=lines, limit=req.magnum_rail, anchors=anchors)
    for r in rail:
        r["reasons"] = _decorate(r.get("reason_codes", []))
        # The rail is ranked with no query, so the text term is a constant and
        # would win "top driver" every time. The interesting question is which
        # of the *discriminating* families put this SKU where it is.
        top = max((c for c in r["contributions"] if c["family"] != "text"),
                  key=lambda c: c["points"])
        r["top_driver"] = top["family"]
        r["top_driver_label"] = top.get("label", top["family"])
        r["top_driver_points"] = top["points"]
        r["in_results"] = any(x["sku_id"] == r["sku_id"] for x in ranked)
        # The price the shopper would actually meet, decided per row. The rail is
        # the surface they are looking at, so the discount belongs on it rather
        # than waiting for the cart - and it is the same decision the cart makes,
        # through the same function, so the two cannot disagree.
        r["coupon"] = _coupon_view(
            pol.decide_offer(ctx, cf, clf, stock, st.uplift_table, r["sku_id"],
                             basket_value=_basket_value(lines),
                             cluster=(cf or {}).get("peer_cluster", ""),
                             channel="onsite"),
            ctx)

    return {
        "context_id": ctx["context_id"], "context": ctx,
        "intent": intent,
        "magnum_live": rail,
        "signals": _signals(ctx, cf),
        "results": ranked,
        "weights": {"text": pol.W_TEXT, "personal": pol.W_PERSONAL, "peer": pol.W_PEER,
                    "context": pol.W_CONTEXT, "availability": pol.W_AVAIL},
        "rail_weights": (rail[0]["contributions"] if rail else []),
        "suggestions": _suggestions(ctx, cf, clf),
        "pairing": _pairing_summary(anchors, st),
        "personalised": cf is not None,
        "policy_version": POLICY_VERSION,
        "latency_ms": round((time.time() - t0) * 1000, 1),
    }


# ---------------------------------------------------------------------------
# 4. cart quantity recommendation
# ---------------------------------------------------------------------------
@app.post("/api/cart/recommend")
def cart_recommend(req: CartReq):
    t0 = time.time()
    ctx = _ctx(req.context)
    st, cf, clf = _who(req.customer_id)
    stock = st.store_stock(ctx["store_id"])
    lines = _lines(req.cart)
    anchors = pol.build_anchors(lines, [], None, st.pair_table, st.pair_by_category)
    rec = pol.recommend_pack(lines, ctx, cf, clf, stock, anchors=anchors)
    rec["reasons"] = _decorate(rec.get("reason_codes", []))
    rec["pairing_summary"] = _pairing_summary(anchors, st)
    rec["basket_value"] = _basket_value(lines)
    rec["context_id"] = ctx["context_id"]
    rec["latency_ms"] = round((time.time() - t0) * 1000, 1)
    rec["policy_version"] = POLICY_VERSION
    return rec


# ---------------------------------------------------------------------------
# 5. offer decision
# ---------------------------------------------------------------------------
@app.post("/api/offers/decide")
def offers_decide(req: OfferReq):
    t0 = time.time()
    ctx = _ctx(req.context)
    st, cf, clf = _who(req.customer_id)
    stock = st.store_stock(ctx["store_id"])
    lines = _lines(req.cart)
    consent = req.override_consent if req.override_consent is not None else (
        bool(cf["consent_marketing"]) if cf else True)
    c7 = req.override_contacts_7d if req.override_contacts_7d is not None else int(
        st.contacts_7d.get(req.customer_id, 0)) if req.customer_id else 0
    c24 = int(st.contacts_24h.get(req.customer_id, 0)) if req.customer_id else 0
    if req.override_contacts_7d is not None:
        c24 = 0
    hours_since = 999.0
    if cf and cf.get("last_order_at"):
        hours_since = (NOW - datetime.fromisoformat(cf["last_order_at"])).total_seconds() / 3600.0
    if req.override_hours_since_order is not None:
        hours_since = float(req.override_hours_since_order)

    d = pol.decide_offer(ctx, cf, clf, stock, st.uplift_table, req.recommended_sku,
                         basket_value=_basket_value(lines),
                         cluster=(cf or {}).get("peer_cluster", ""),
                         consent=consent, contacts_24h=c24, contacts_7d=c7,
                         hours_since_order=hours_since, channel="onsite")
    d["reasons"] = _decorate(d.get("reason_codes", []))
    # The same plain-language coupon block the suggestion cards use, so the cart
    # and the panel cannot describe the same decision two different ways.
    d["coupon"] = _coupon_view(d, ctx)
    for c in d.get("candidates", []):
        c["reasons"] = _decorate(c.get("reason_codes", []))
    d["guardrails"] = {"min_uplift_pp": round(pol.MIN_UPLIFT_PP * 100, 2),
                       "max_discount_pct": round(pol.MAX_DISCOUNT_PCT * 100, 1),
                       "freq_cap_per_7d": pol.FREQ_CAP_PER_7D, "freq_cap_hours": pol.FREQ_CAP_HOURS,
                       "contacts_24h": c24, "contacts_7d": c7, "consent": consent,
                       "hours_since_order": round(hours_since, 1),
                       "post_purchase_window_hours": 12}
    d["context_id"] = ctx["context_id"]
    d["policy_version"] = POLICY_VERSION
    d["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return d


# ---------------------------------------------------------------------------
# 6. reorder
# ---------------------------------------------------------------------------
@app.get("/api/reorder/{customer_id}")
def reorder(customer_id: str, day: str = "friday", time_window: str = "dinner",
            season: str = "summer", weather: str = "hot", game_day: bool = True,
            event: str = "none", activity: str = "high",
            area_id: str = "upper-east-side"):
    st, cf, clf = _who(customer_id)
    if not cf:
        raise HTTPException(404, "unknown customer")
    ctx = _ctx(ContextSel(day=day, time_window=time_window, season=season, weather=weather,
                          game_day=game_day, event=event, activity=activity, area_id=area_id))
    r = pol.reorder_candidate(cf, ctx, consent=bool(cf["consent_marketing"]),
                              contacts_24h=int(st.contacts_24h.get(customer_id, 0)),
                              contacts_7d=int(st.contacts_7d.get(customer_id, 0)))
    r["reasons"] = _decorate(r.get("reason_codes", []))
    r["customer"] = {k: cf[k] for k in ("display_name", "peer_cluster", "cadence_days",
                                        "days_since_magnum", "due_ratio", "usual_hour",
                                        "magnum_orders", "avg_units")}
    r["policy_version"] = POLICY_VERSION
    return r


# ---------------------------------------------------------------------------
# 7. forecast + stock action
# ---------------------------------------------------------------------------
@app.post("/api/notify")
def notify(req: OfferReq):
    """The reorder push for one household: when to send, what to put in it, how
    many, and which offer rides along. Assembled from the same three policies
    the storefront uses - nothing here is a second opinion."""
    t0 = time.time()
    ctx = _ctx(req.context)
    st, cf, clf = _who(req.customer_id)
    if not cf:
        raise HTTPException(404, "unknown customer")
    stock = st.store_stock(ctx["store_id"])
    consent = req.override_consent if req.override_consent is not None else bool(cf["consent_marketing"])
    c7 = req.override_contacts_7d if req.override_contacts_7d is not None else int(
        st.contacts_7d.get(req.customer_id, 0))
    c24 = 0 if req.override_contacts_7d is not None else int(st.contacts_24h.get(req.customer_id, 0))
    hours_since = 999.0
    if cf.get("last_order_at"):
        hours_since = (NOW - datetime.fromisoformat(cf["last_order_at"])).total_seconds() / 3600.0
    if req.override_hours_since_order is not None:
        hours_since = float(req.override_hours_since_order)

    out = ntf.compose(st, cf, clf, ctx, stock, consent, c24, c7, hours_since)
    out["customer"] = {"customer_id": cf["customer_id"], "display_name": cf["display_name"],
                       "peer_cluster": cf["peer_cluster"], "home_area": cf["home_area"],
                       "consent_marketing": bool(cf["consent_marketing"])}
    out["guardrails"] = {"contacts_24h": c24, "contacts_7d": c7,
                         "freq_cap_per_7d": pol.FREQ_CAP_PER_7D,
                         "hours_since_order": round(hours_since, 1), "consent": consent}
    out["context_id"] = ctx["context_id"]
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return out


@app.get("/api/forecast")
def forecast(store_id: str = "ST-01", sku_id: Optional[str] = None, horizon: int = 48,
             day: str = "friday", time_window: str = "dinner", season: str = "summer",
             weather: str = "hot", game_day: bool = True, event: str = "none",
             activity: str = "high"):
    st = get_store()
    store = cat.STORE_BY_ID.get(store_id)
    if not store:
        raise HTTPException(404, "unknown store")
    ctx = _ctx(ContextSel(day=day, time_window=time_window, season=season, weather=weather,
                          game_day=game_day, event=event, activity=activity,
                          area_id=store["area_id"]))
    skus = [sku_id] if sku_id else cat.MAGNUM_SKUS
    stock = st.store_stock(store_id)
    inbound = st.inbound.get(store_id, {})
    series_by_sku, actions, total = {}, [], []
    for sku in skus:
        s = pol.forecast_series(st.rate(store_id, sku), ctx, horizon,
                                flavour=cat.PRODUCT_BY_ID[sku]["flavour"])
        series_by_sku[sku] = s
        act = pol.stock_action(s, stock.get(sku, 0), inbound.get(sku, 0), ctx,
                               transfer_lead_minutes=store["transfer_lead_minutes"])
        act["reasons"] = _decorate(act.get("reason_codes", []))
        actions.append({"sku_id": sku, "name": cat.PRODUCT_BY_ID[sku]["name"], **act})
        if not total:
            total = [dict(h) for h in s]
        else:
            for a, b in zip(total, s):
                a["p10"] += b["p10"]; a["p50"] += b["p50"]; a["p90"] += b["p90"]
    for h in total:
        h["p10"] = round(h["p10"], 2); h["p50"] = round(h["p50"], 2); h["p90"] = round(h["p90"], 2)
    return {
        "store": store, "context": ctx, "horizon": horizon,
        "peak": cx.peak_window(total),
        "total": total, "by_sku": series_by_sku, "actions": actions,
        "stock": stock, "inbound": inbound,
        "snapshot_at": st.inventory_time,
        "forecast_version": FORECAST_VERSION,
        "risk_count": sum(1 for a in actions if a["status"] == "stockout_risk"),
        "watch_count": sum(1 for a in actions if a["status"] == "watch"),
    }


@app.get("/api/forecast/network")
def forecast_network(day: str = "friday", time_window: str = "dinner", season: str = "summer",
                     weather: str = "hot", game_day: bool = True, event: str = "none",
                     activity: str = "high", horizon: int = 48):
    """One row per store: the demand desk's opening view."""
    st = get_store()
    rows = []
    for store in cat.STORES:
        ctx = _ctx(ContextSel(day=day, time_window=time_window, season=season, weather=weather,
                              game_day=game_day, event=event, activity=activity,
                              area_id=store["area_id"]))
        stock = st.store_stock(store["store_id"])
        inbound = st.inbound.get(store["store_id"], {})
        risk = watch = 0
        p90_peak = 0.0
        on_hand = 0
        for sku in cat.MAGNUM_SKUS:
            s = pol.forecast_series(st.rate(store["store_id"], sku), ctx, horizon,
                                    flavour=cat.PRODUCT_BY_ID[sku]["flavour"])
            a = pol.stock_action(s, stock.get(sku, 0), inbound.get(sku, 0), ctx,
                                 transfer_lead_minutes=store["transfer_lead_minutes"])
            risk += a["status"] == "stockout_risk"
            watch += a["status"] == "watch"
            p90_peak += a["forecast_p90_to_peak"]
            on_hand += stock.get(sku, 0)
        rows.append({
            "store_id": store["store_id"], "name": store["name"], "area_id": store["area_id"],
            "state": store["state"], "city": store["city"],
            "lat": cat.AREA_BY_ID[store["area_id"]]["lat"],
            "lon": cat.AREA_BY_ID[store["area_id"]]["lon"],
            "density": store["density"], "transfer_lead_minutes": store["transfer_lead_minutes"],
            "on_hand": on_hand, "p90_to_peak": round(p90_peak, 1),
            "risk_skus": int(risk), "watch_skus": int(watch),
            "demand_index": ctx["demand_index"], "absolute_index": ctx["absolute_index"],
            "temperature_f": ctx["temperature_f"],
            "status": "stockout_risk" if risk else ("watch" if watch else "healthy"),
        })
    rows.sort(key=lambda r: (-r["risk_skus"], -r["watch_skus"], -r["p90_to_peak"]))
    return {"stores": rows, "generated_for": {"day": day, "time_window": time_window,
                                              "season": season, "weather": weather,
                                              "game_day": game_day, "event": event,
                                              "activity": activity}}


@app.get("/api/inventory/{store_id}")
def inventory(store_id: str):
    st = get_store()
    stock = st.store_stock(store_id)
    if not stock:
        raise HTTPException(404, "unknown store")
    return {"store_id": store_id, "snapshot_at": st.inventory_time,
            "lines": [{"sku_id": k, "name": cat.PRODUCT_BY_ID[k]["name"], "on_hand": v,
                       "inbound": st.inbound.get(store_id, {}).get(k, 0),
                       "low": v <= pol.LOW_STOCK_UNITS} for k, v in stock.items()]}


# ---------------------------------------------------------------------------
# 8. events
# ---------------------------------------------------------------------------
@app.post("/api/events")
def post_events(req: EventsReq):
    ts = datetime.utcnow().isoformat() + "Z"
    for e in req.events:
        EVENT_SINK.appendleft({"received_at": ts, **e.model_dump(exclude_none=True)})
    return {"accepted": len(req.events), "buffered": len(EVENT_SINK),
            "note": "Buffered in memory. The generated log is read-only."}


@app.get("/api/events/recent")
def recent_events(limit: int = 40):
    return {"events": list(EVENT_SINK)[:limit], "buffered": len(EVENT_SINK)}


# ---------------------------------------------------------------------------
# 9. reset
# ---------------------------------------------------------------------------
@app.post("/api/demo/reset")
def demo_reset():
    st = get_store()
    EVENT_SINK.clear()
    return {**st.reset(), "seed": SEED,
            "note": "Stock restored to the golden snapshot; event buffer cleared."}


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------
@app.get("/api/impact")
def api_impact(recovery: float = Query(impact.DEFAULT_RECOVERY, ge=0.0, le=1.0),
               scale: float = Query(1.0, ge=0.1, le=200.0)):
    """What a month, a quarter and half a year of running this add up to."""
    return impact.compute(recovery=recovery, scale=scale)


@app.get("/api/analysis/overview")
def a_overview():
    return analysis.overview()


@app.get("/api/analysis/uplift")
def a_uplift(split: str = Query("all", pattern="^(all|fit|calibrate|holdout)$")):
    return analysis.uplift(split)


@app.get("/api/analysis/policy-eval")
def a_policy():
    return analysis.policy_eval()


@app.get("/api/analysis/forecast-accuracy")
def a_forecast():
    return analysis.forecast_accuracy()


@app.get("/api/analysis/demand-drivers")
def a_drivers():
    return analysis.demand_drivers()


@app.get("/api/analysis/stockouts")
def a_stockouts():
    return analysis.stockouts()


@app.get("/api/analysis/validation")
def a_validation():
    return analysis.validation()


@app.get("/api/analysis/clusters")
def a_clusters():
    st = get_store()
    return {"clusters": list(st.cluster_features.values()),
            "definitions": pf.CLUSTERS}


# ---------------------------------------------------------------------------
# data explorer
# ---------------------------------------------------------------------------
@app.get("/api/data/tables")
def data_tables():
    con = _con()
    out = []
    for t in BROWSABLE:
        n = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % t)]
        out.append({"table": t, "rows": n, "columns": cols, "locked": False})
    for t in sorted(HELD_OUT_TABLES):
        n = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        out.append({"table": t, "rows": n, "columns": [], "locked": True,
                    "reason": ("Evaluation-only. Held out of the application so no ranking, "
                               "offer or forecast can be trained or scored on the answer.")})
    con.close()
    return {"tables": out}


@app.get("/api/data/table/{name}")
def data_table(name: str, limit: int = 50, offset: int = 0,
               order_by: Optional[str] = None, direction: str = "asc",
               q: Optional[str] = None, column: Optional[str] = None):
    if name in HELD_OUT_TABLES:
        raise HTTPException(403, "This table is evaluation-only and is not served to the application.")
    if name not in BROWSABLE:
        raise HTTPException(404, "unknown table")
    con = _con()
    cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % name)]
    where, params = "", []
    if q and column and column in cols:
        where = "WHERE CAST(%s AS TEXT) LIKE ?" % column
        params.append("%" + q + "%")
    order = ""
    if order_by and order_by in cols:
        order = "ORDER BY %s %s" % (order_by, "DESC" if direction.lower() == "desc" else "ASC")
    total = con.execute("SELECT COUNT(*) FROM %s %s" % (name, where), params).fetchone()[0]
    rows = con.execute("SELECT * FROM %s %s %s LIMIT ? OFFSET ?" % (name, where, order),
                       params + [min(500, limit), offset]).fetchall()
    con.close()
    return {"table": name, "columns": cols, "total": total, "limit": limit, "offset": offset,
            "rows": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# customer analytics (iteration 2)
# ---------------------------------------------------------------------------
@app.get("/api/customer/{customer_id}/analytics")
def customer_analytics(customer_id: str):
    t0 = time.time()
    out = cust.analytics(customer_id)
    if out is None:
        raise HTTPException(404, "unknown customer")
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return out


class SensitivityReq(BaseModel):
    customer_id: Optional[str] = None
    context: ContextSel = Field(default_factory=ContextSel)
    dimension: str = "weather"      # weather | time_window | event | day


@app.post("/api/context/sensitivity")
def context_sensitivity(req: SensitivityReq):
    """Hold everything fixed and sweep one gate.

    A single resolved context tells the reviewer what the system does now. It
    does not show that the system is actually reacting - for that you need the
    curve. This returns the whole response surface along one axis, using the
    same resolve/rank path the live screen uses, so the what-if strip cannot
    drift from the thing it is previewing.
    """
    t0 = time.time()
    st, cf, clf = _who(req.customer_id)
    base = _ctx(req.context)

    axes = {
        "weather": [(w["id"], w["label"]) for w in cx.WEATHER],
        "time_window": [(t["id"], t["label"]) for t in cx.TIME_WINDOWS],
        "event": [(e["id"], e["label"]) for e in cx.EVENTS],
        "day": [(d, d[:3].title()) for d in cx.DAYS],
    }
    if req.dimension not in axes:
        raise HTTPException(400, "dimension must be one of %s" % sorted(axes))

    rows = []
    for value, label in axes[req.dimension]:
        sel = req.context.model_copy(update={req.dimension: value})
        ctx = _ctx(sel)
        stock = st.store_stock(ctx["store_id"])
        top = pol.rank_products("", ctx, cf, clf, stock, category="magnum", limit=3)
        # Where the best Magnum SKU sits in the *whole* aisle is the number that
        # actually moves with weather. Within Magnum the context term lifts every
        # bar together, so the flavour order barely changes - saying otherwise
        # would be the demo lying about its own model.
        full = pol.rank_products("", ctx, cf, clf, stock, limit=len(cat.PRODUCTS))
        best = next((i + 1 for i, r in enumerate(full) if r["category"] == "magnum"), None)
        in_top5 = sum(1 for r in full[:5] if r["category"] == "magnum")
        rows.append({
            "magnum_best_rank": best,
            "magnum_in_top5": in_top5,
            "value": value, "label": label,
            "is_current": value == getattr(req.context, req.dimension),
            "demand_index": ctx["demand_index"],
            "absolute_index": ctx["absolute_index"],
            "temperature_f": ctx["temperature_f"],
            "heat_pull": ctx["heat_pull"],
            "in_game_window": ctx["in_game_window"],
            "top": [{"sku_id": r["sku_id"], "name": r["name"], "flavour": r["flavour"],
                     "score": r["match_score"]} for r in top],
            # Compared on absolute_index, not demand_index. demand_index is
            # measured against the neutral case *at the same hour*, so it
            # cancels the hour out - sweeping the time window on it would show
            # a flat line and claim the clock does not matter.
            "vs_current_pct": round(
                (ctx["absolute_index"] / base["absolute_index"] - 1) * 100, 1)
            if base["absolute_index"] else None,
        })

    return {
        "dimension": req.dimension,
        "base_context_id": base["context_id"],
        "base_demand_index": base["demand_index"],
        "base_absolute_index": base["absolute_index"],
        "rows": rows,
        "latency_ms": round((time.time() - t0) * 1000, 1),
    }


# ---------------------------------------------------------------------------
# uber adapter (flag off by default - section 9)
# ---------------------------------------------------------------------------
@app.get("/api/integrations/uber/status")
def uber_status():
    return {
        "enabled": UBER_ADAPTER_ENABLED,
        "mode": "sandbox_stub",
        "note": ("Adapter is a stub behind UBER_ADAPTER_ENABLED, off by default. No Uber "
                 "credentials, endpoints or trade dress are present in this build. Nothing "
                 "here calls an external service."),
        "capabilities": [
            {"name": "menu_sync", "direction": "outbound", "status": "not_implemented"},
            {"name": "store_status", "direction": "outbound", "status": "not_implemented"},
            {"name": "order_webhook", "direction": "inbound", "status": "not_implemented"},
        ],
    }


# ---------------------------------------------------------------------------
# the built UI, served by the API
# ---------------------------------------------------------------------------
# There is one application, and this makes that true at one address.
#
# Development runs two processes - Vite on 5173 for hot reload, this API on 8000
# - and Vite proxies /api to here. That is the right setup while building, but it
# left port 8000 answering 404 at its root, which reads like a second, broken
# application sitting next to the real one. It is not; there was simply nothing
# mounted there.
#
# Mounting the production build closes that. http://localhost:8000 now serves the
# whole product from a single process with no Node running, which is also what
# you want in front of a client: one URL, nothing to explain. 5173 stays the
# hot-reload view for whoever is editing the code.
#
# The mount is last on purpose. Every /api route above is registered first, so
# this can never shadow one.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

if _DIST.is_dir():
    @app.get("/", include_in_schema=False)
    def _index():
        return FileResponse(_DIST / "index.html")

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
