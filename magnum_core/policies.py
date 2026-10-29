"""Transparent V1 decision policies (§6 of the build document).

Every formula here is the one written in §6.3, with its weights named rather
than buried, because the point of V1 is that a reviewer can follow a
recommendation back to the numbers that produced it. Model upgrades slot in
behind these same signatures (§6.2).

Nothing in this module reads `latent_traits` or `ground_truth`.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from magnum_core import POLICY_VERSION
from magnum_core import catalog as cat
from magnum_core import context as cx

# --- §6.3 search rank weights ---------------------------------------------
# Ranking weights. Peers are deliberately near-silent: "people like you bought
# this" is the weakest evidence in the stack and the easiest to be wrong about,
# so it breaks ties and nothing more. What this household actually buys, and
# what is on the plate in front of them, do the work.
W_TEXT, W_PERSONAL, W_PEER, W_CONTEXT, W_AVAIL = 0.35, 0.31, 0.04, 0.18, 0.12

# Plain names for the five (six, when pairing is live) score families. The score
# table is shown to people who do not work on recommenders, and a column headed
# "context" tells them nothing. One definition, used by the API and the screen.
FAMILY_LABEL = {
    "text": "Matches what you searched",
    "personal": "What you usually buy",
    "peer": "Similar shoppers",
    "context": "Weather and time of day",
    "availability": "In stock near you",
    "pairing": "Goes with your food",
}

# --- §6.3 suggested quantity weights --------------------------------------
W_Q_PERSONAL, W_Q_PEER, W_Q_OCCASION = 0.40, 0.35, 0.25
# Raised from 6. At 6 the cap was doing silent work nobody could see: a
# match-day basket of two large pizzas computes 8.1 bars, and every context above
# six flattened to the same answer, so the cart looked frozen while the model
# underneath it was moving. Ten is two six-packs, which is the largest suggestion
# that is still a suggestion rather than a bulk order.
MAX_UNITS = 10

# --- §4.3 offer guardrails -------------------------------------------------
MIN_UPLIFT_PP = 0.02          # 2 percentage points: a contact has to move
                              # the needle by more than measurement noise to be worth
                              # sending. 5pp was set high enough that only the
                              # loss-making voucher ever cleared it.
MAX_DISCOUNT_PCT = 0.25
FREQ_CAP_HOURS = 24
FREQ_CAP_PER_7D = 3

# --- §6.3 stock policy -----------------------------------------------------
SAFETY_STOCK_UNITS = 6
LOW_STOCK_UNITS = 8


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ==========================================================================
# Intent (§4.2)
# ==========================================================================

DESSERT_TOKENS = {"magnum", "ice", "cream", "dessert", "chocolate", "bar", "bars",
                  "almond", "caramel", "frozen", "sweet", "cheesecake", "brownie",
                  "cookie", "cookies", "pint", "treat"}


def classify_intent(query: str, cart_lines: Optional[List[Dict]] = None,
                    entry_source: str = "organic_search") -> Dict:
    """Direct (dessert-led) vs attachment (meal-led). Rules over the first
    query and the pre-Magnum cart state, exactly as §6.2 specifies for V1."""
    cart_lines = cart_lines or []
    tokens = {t for t in (query or "").lower().replace(",", " ").split() if t}
    dessert_hit = bool(tokens & DESSERT_TOKENS)
    meal_in_cart = any(cat.PRODUCT_BY_ID.get(l["sku_id"], {}).get("category") in ("meal", "side")
                       for l in cart_lines)
    magnum_in_cart = any(cat.PRODUCT_BY_ID.get(l["sku_id"], {}).get("category") == "magnum"
                         for l in cart_lines)

    if meal_in_cart and not magnum_in_cart:
        cls, conf, why = "attachment", 0.86, "A meal is already in the cart."
    elif dessert_hit and not meal_in_cart:
        cls, conf, why = "direct", 0.90, "The search is dessert-led."
    elif entry_source in ("notification", "reorder_link"):
        cls, conf, why = "direct", 0.72, "Arrived from a reorder prompt."
    elif tokens and not dessert_hit:
        cls, conf, why = "attachment", 0.68, "The search is meal-led."
    else:
        cls, conf, why = "direct", 0.55, "No meal signal yet; treated as dessert-led."
    return {"intent_class": cls, "confidence": round(conf, 3), "rationale": why,
            "meal_in_cart": meal_in_cart, "dessert_query": dessert_hit}


# ==========================================================================
# Component scores for the ranking formula (§6.3)
# ==========================================================================

def text_score(product: Dict, query: str, category: Optional[str] = None) -> float:
    if category and product["category"] != category:
        return 0.0
    q = (query or "").lower().strip()
    if not q:
        return 0.55                      # browsing, so text carries no signal either way
    name = product["name"].lower()
    if q in name:
        return 1.0
    tokens = [t for t in q.replace(",", " ").split() if t]
    if not tokens:
        return 0.55
    hay = " ".join([name] + product["search_terms"] + product["tags"] + [product["brand"].lower()])
    hits = sum(1 for t in tokens if t in hay)
    return _clip(hits / len(tokens))


def personal_score(product: Dict, cf: Optional[Dict]) -> Tuple[float, List[str]]:
    if not cf or cf.get("magnum_orders", 0) == 0:
        return 0.45, ["NEW_CUSTOMER"]
    reasons: List[str] = []
    score = 0.30
    if product["category"] == "magnum":
        share = cf["flavour_shares"].get(product["flavour"], 0.0)
        score = 0.25 + 0.65 * share
        if share >= 0.30:
            reasons.append("PERSONAL_FAVOURITE")
        is_pack = product["sku_id"] in cat.MAGNUM_PACKS
        if is_pack and cf["pack_share"] > 0.45:
            score += 0.12
            reasons.append("PERSONAL_PACK_HABIT")
        elif (not is_pack) and cf["pack_share"] < 0.35:
            score += 0.08
            reasons.append("PERSONAL_PACK_HABIT")
        if cf.get("due_ratio", 0) >= 0.85:
            score += 0.10
            reasons.append("PERSONAL_REORDER_WINDOW")
    else:
        score = 0.25 + 0.55 * cf["category_shares"].get(product["category"], 0.0)
    return _clip(score), reasons


def peer_score(product: Dict, clf: Optional[Dict]) -> Tuple[float, List[str]]:
    if not clf:
        return 0.45, []
    reasons: List[str] = []
    if product["category"] == "magnum":
        share = clf["flavour_shares"].get(product["flavour"], 0.0)
        score = 0.25 + 0.70 * share
        if share >= 0.30:
            reasons.append("PEER_FLAVOUR_SHARE")
    else:
        share = clf["sku_shares"].get(product["sku_id"], 0.0)
        score = 0.25 + 0.65 * min(1.0, share * 4.0)
        if share >= 0.10:
            reasons.append("PEER_CO_PURCHASE")
    return _clip(score), reasons


def context_score(product: Dict, ctx: Dict) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    heat = ctx.get("heat_pull", 0.5)
    group = ctx.get("group_bias", 0.0)
    if product["category"] in ("magnum", "dessert"):
        score = 0.28 + 0.60 * heat
        # Heat changes which bar, not only whether a bar. The tilt is the same
        # one the order log was generated under, so the ranking moves the way
        # the history says it should rather than the way it feels like it should.
        dev = (heat - 0.62) * 2.0
        tilt = cat.HEAT_FLAVOUR_TILT.get(product.get("flavour") or "", 0.0)
        score += 0.20 * tilt * dev
        # A hot day is also a bigger-occasion day: boxes move, singles hold.
        if product["units_in_pack"] > 1:
            score += 0.10 * _clip(group) + 0.08 * max(0.0, dev)
        # What the day of the week and the match window measurably do, read off
        # the log rather than asserted. A Sunday takes packs 14% more often than
        # an average day and a match window 36% more often; a Monday 18% less.
        # Applied here rather than left in `group_bias`, which stepped exactly
        # once at Friday and left six of the seven days indistinguishable.
        pack_lift = float(ctx.get("occasion_pack_lift") or 1.0)
        if abs(pack_lift - 1.0) > 0.005:
            signed = (pack_lift - 1.0) if product["units_in_pack"] > 1 else (1.0 - pack_lift)
            score += 0.34 * signed
            reasons.append("CONTEXT_OCCASION_PACK" if signed > 0 else "CONTEXT_OCCASION_SINGLE")
        fl = (ctx.get("occasion_flavour_lift") or {}).get(product.get("flavour") or "")
        if fl and abs(fl - 1.0) > 0.005:
            score += 0.30 * (fl - 1.0)
            if fl > 1.02:
                reasons.append("CONTEXT_OCCASION_FLAVOUR")
        if heat >= 0.72:
            reasons.append("CONTEXT_HEAT")
            if tilt > 0.3:
                reasons.append("CONTEXT_HEAT_FLAVOUR")
        elif heat <= 0.50 and tilt < -0.3:
            reasons.append("CONTEXT_COLD_FLAVOUR")
    elif product["category"] in ("side", "drink"):
        score = 0.40 + 0.35 * _clip(group)
    else:
        score = 0.45 + 0.20 * _clip(group)
    if ctx.get("in_game_window") and product["is_shareable"]:
        score += 0.14
        reasons.append("CONTEXT_MATCH")
    if ctx.get("event") not in (None, "none") and product["is_shareable"]:
        score += 0.08
        reasons.append("CONTEXT_EVENT")
    if ctx.get("time_window") == "late" and product["units_in_pack"] == 1:
        score += 0.10
        reasons.append("CONTEXT_LATE")
    return _clip(score), reasons


def availability_score(sku_id: str, stock: Dict[str, int]) -> Tuple[float, List[str], str]:
    on_hand = stock.get(sku_id)
    if on_hand is None:
        return 0.80, [], "available"          # non-Magnum lines are not stock-tracked in v1
    if on_hand <= 0:
        return 0.0, ["OUT_OF_STOCK"], "out_of_stock"
    if on_hand < LOW_STOCK_UNITS:
        return 0.45, ["LOW_STOCK"], "low_stock"
    return 1.0, [], "available"


def pairing_score(product: Dict, anchors: List[Dict]) -> Tuple[float, List[str], Optional[Dict]]:
    """How well this Magnum goes with what the shopper is actually looking at.

    `anchors` are the non-Magnum things in play - items in the cart, the item a
    search resolved to, the aisle being browsed - each carrying its measured
    flavour lift and units ratio from the order log.

    Two things fall out of it and both matter. Flavour lift moves *which* bar
    ranks first: pizza baskets take classic at 1.6x and caramel at 0.18x, so a
    shopper looking at pizza should not be shown caramel. Units ratio moves *how
    many*, and it is the size half of the same signal - a shared pizza basket
    carries 1.66x the bars of an average one, a single burger 0.69x.

    Only Magnum lines can pair. Scoring a drink against a drink would let the
    term leak into the main grid, where it has nothing to say.
    """
    if product["category"] != "magnum" or not anchors:
        return 0.5, [], None

    flavour = product.get("flavour") or "classic"
    weight_sum = sum(a.get("weight", 1.0) for a in anchors) or 1.0
    lift = sum(a["flavour_lift"].get(flavour, 1.0) * a.get("weight", 1.0)
               for a in anchors) / weight_sum
    units_ratio = sum(a.get("units_ratio", 1.0) * a.get("weight", 1.0)
                      for a in anchors) / weight_sum

    # A lift of 1.0 is "no information", so it has to land on the neutral 0.5.
    # Lift is a ratio and its useful range here is roughly 0.15x to 1.7x, which
    # log2 makes symmetric about zero: half as likely and twice as likely move
    # the score by the same distance in opposite directions.
    score = _clip(0.5 + 0.28 * math.log2(max(0.05, lift)))

    reasons = []
    if lift >= 1.25:
        reasons.append("PAIR_STRONG")
    elif lift <= 0.75:
        reasons.append("PAIR_WEAK")
    if units_ratio >= 1.25:
        reasons.append("PAIR_SHARED_BASKET")

    best = max(anchors, key=lambda a: a["flavour_lift"].get(flavour, 1.0))
    detail = {
        "flavour": flavour,
        "lift": round(lift, 3),
        "units_ratio": round(units_ratio, 3),
        "anchor_sku": best.get("sku_id"),
        "anchor_name": best.get("name"),
        "anchor_n": best.get("n"),
        "anchor_lift": round(best["flavour_lift"].get(flavour, 1.0), 3),
        "anchors": [a.get("name") for a in anchors][:4],
    }
    return score, reasons, detail


def build_anchors(cart_lines: Optional[List[Dict]], results: Optional[List[str]],
                  category: Optional[str], pair_table: Dict, pair_by_category: Dict,
                  ) -> List[Dict]:
    """Resolve what the shopper is looking at into weighted pairing anchors.

    The cart outweighs the screen on purpose. Something in the basket is a
    decision; something on the screen is a glance, and a glance should tilt the
    rail without being allowed to overrule what the shopper has already chosen.
    """
    anchors: List[Dict] = []
    seen = set()
    for l in (cart_lines or []):
        sku = l.get("sku_id")
        row = pair_table.get(sku)
        if not row or sku in seen:
            continue
        seen.add(sku)
        p = cat.PRODUCT_BY_ID.get(sku, {})
        anchors.append(dict(row, sku_id=sku, name=p.get("name"), source="cart",
                            weight=3.0 * int(l.get("quantity", 1))))
    # On-screen results decay hard by position. A search for "chips and salsa"
    # returns the chips first and then whatever else the matcher could justify,
    # and giving row four the same vote as row one let a loosely-matched burger
    # drag the whole rail toward caramel. The top hit is what the shopper is
    # looking at; everything under it is context.
    for i, sku in enumerate((results or [])[:4]):
        row = pair_table.get(sku)
        if not row or sku in seen:
            continue
        seen.add(sku)
        p = cat.PRODUCT_BY_ID.get(sku, {})
        anchors.append(dict(row, sku_id=sku, name=p.get("name"), source="results",
                            weight=round(1.0 / (1.0 + 1.6 * i), 3)))
    if category and category != "magnum" and not anchors:
        row = pair_by_category.get(category)
        if row:
            anchors.append(dict(row, sku_id=None, name="the {} aisle".format(category),
                                source="category", weight=1.0))
    return anchors


# ==========================================================================
# Search ranking (§4.2, §6.3)
# ==========================================================================

# Pairing is weighted high enough to actually change the order, because a
# pairing term that only ever reshuffles ties is a term nobody can see working.
# At 0.28 a measured 1.6x flavour lift beats a moderate personal preference and
# a 1.2x lift does not - which is the correct outcome: the plate in front of
# someone is strong evidence, and their own eight-month history is stronger.
W_PAIR = 0.28                 # only live when there is something to pair with


def rank_products(query: str, ctx: Dict, cf: Optional[Dict], clf: Optional[Dict],
                  stock: Dict[str, int], category: Optional[str] = None,
                  cart_lines: Optional[List[Dict]] = None, limit: int = 24,
                  anchors: Optional[List[Dict]] = None) -> List[Dict]:
    """Rank the aisle. When the shopper is looking at something a Magnum pairs
    with, a fifth family joins the formula and the other four compress in
    proportion, so the weights still sum to one and the shift is legible on the
    screen rather than hidden in a constant."""
    paired = bool(anchors)
    k = (1.0 - W_PAIR) if paired else 1.0
    w_text, w_pers, w_peer, w_con, w_avail = (
        W_TEXT * k, W_PERSONAL * k, W_PEER * k, W_CONTEXT * k, W_AVAIL * k)
    out = []
    for p in cat.PRODUCTS:
        t = text_score(p, query, category)
        if query and t <= 0.0:
            continue
        if category and p["category"] != category:
            continue
        pers, r_pers = personal_score(p, cf)
        peer, r_peer = peer_score(p, clf)
        con, r_con = context_score(p, ctx)
        avail, r_avail, stock_state = availability_score(p["sku_id"], stock)
        pair, r_pair, pair_detail = pairing_score(p, anchors or [])

        score = (w_text * t + w_pers * pers + w_peer * peer
                 + w_con * con + w_avail * avail)
        if paired:
            score += W_PAIR * pair
        # §4.2: never rank an unavailable SKU above an available substitute.
        if stock_state == "out_of_stock":
            score *= 0.25

        def _c(family, weight, raw):
            return {"family": family, "label": FAMILY_LABEL[family],
                    "weight": round(weight, 4), "score": round(raw, 3),
                    "points": round(weight * raw, 4)}

        contributions = [
            _c("text", w_text, t), _c("personal", w_pers, pers),
            _c("peer", w_peer, peer), _c("context", w_con, con),
            _c("availability", w_avail, avail),
        ]
        if paired:
            contributions.append(_c("pairing", W_PAIR, pair))
        out.append({
            "sku_id": p["sku_id"], "name": p["name"], "brand": p["brand"],
            "category": p["category"], "subcategory": p["subcategory"],
            "flavour": p["flavour"], "size_label": p["size_label"],
            "units_in_pack": p["units_in_pack"], "price": p["price"],
            "unit_margin": p["unit_margin"], "is_shareable": p["is_shareable"],
            "match_score": round(score, 4), "stock_state": stock_state,
            "on_hand": stock.get(p["sku_id"]),
            "reason_codes": (r_pair + r_pers + r_peer + r_con + r_avail)[:5],
            "contributions": contributions,
            "pairing": pair_detail,
        })

    out.sort(key=lambda r: (-r["match_score"], r["sku_id"]))
    for i, r in enumerate(out[:limit]):
        r["rank"] = i + 1
    return out[:limit]


# ==========================================================================
# Occasion size and pack/quantity (§4.4, §6.3)
# ==========================================================================

def infer_occasion(cart_lines: List[Dict], ctx: Dict) -> Dict:
    """People inferred from meal portions, drink count, shareables and context."""
    portions = 0.0
    drinks = 0
    shareables = 0
    meal_lines = 0
    for l in cart_lines:
        p = cat.PRODUCT_BY_ID.get(l["sku_id"])
        if not p:
            continue
        qty = int(l.get("quantity", 1))
        if p["category"] == "meal":
            portions += p["portion_size"] * qty
            meal_lines += qty
        elif p["category"] == "drink":
            drinks += qty
        if p["is_shareable"] and p["category"] in ("side", "meal"):
            shareables += qty

    evidence = []
    from_portions = portions
    from_drinks = float(drinks)
    if portions > 0:
        evidence.append("%.1f meal portions" % portions)
    if drinks:
        evidence.append("%d drink%s" % (drinks, "" if drinks == 1 else "s"))
    if shareables:
        evidence.append("%d shareable item%s" % (shareables, "" if shareables == 1 else "s"))

    if from_portions == 0 and from_drinks == 0:
        people = 1.0
        confidence = 0.35
    else:
        parts = [v for v in (from_portions, from_drinks) if v > 0]
        people = sum(parts) / len(parts)
        confidence = 0.55 + 0.12 * len(parts) + (0.10 if shareables else 0.0)

    people += 0.55 * max(0.0, ctx.get("group_bias", 0.0))
    if ctx.get("time_window") == "late":
        people -= 0.35
        evidence.append("late-night window")
    if ctx.get("in_game_window"):
        evidence.append("game window")

    size = int(max(1, min(6, round(people))))
    return {
        "occasion_size": size,
        "raw_estimate": round(people, 2),
        "confidence": round(min(0.95, confidence), 3),
        "evidence": evidence,
        "meal_portions": round(portions, 2),
        "drinks": drinks,
        "shareables": shareables,
        "reason_code": "BASKET_GROUP" if size >= 3 else "BASKET_SOLO",
    }


# One bar either side of the target is not a miss worth paying for. Inside that
# band the fitter is free to pick on price; outside it, fit wins.
LEFTOVER_TOLERANCE = 1
# At or above this many bars the basket reads as a group buy, not a personal one.
GROUP_UNITS = 4
# Above and below these the day's measured pack share is far enough from the
# store average to change which *format* fits, not just how many bars. Set from
# the two gaps in the served distribution rather than picked round: across every
# day x match-window the policy can be asked for, the lift lands in three clumps
# - weeknights 0.91-0.95, weekends 1.05-1.07, match windows 1.09-1.25 - and
# these two numbers sit in the empty space between them. See BUILD.md 22.2.
PACK_BIAS_HI = 1.08
PACK_BIAS_LO = 0.99


def _pack_for_units(units: int, stock: Dict[str, int], flavour: str,
                    pack_bias: float = 1.0) -> Tuple[str, int, List[str]]:
    """Convert a unit target into the available format that actually fits it.

    Leftover first, then flavour, then unit price - with a one-bar tolerance on
    the leftover, and that tolerance is the whole point. A loose single can hit
    any target exactly, so a strict leftover ranking hands singles every tie:
    fine while the target was capped at six, absurd the moment it was not, when
    the fitter started proposing eight and nine bars at $3.49 each with an
    $11.49 six-pack on the shelf. Treating "within one bar" as an equally good
    fit lets the cheaper format win the cases where it obviously should, without
    ever letting it over-sell by more than a bar.

    `pack_bias` is the day's measured pack share against the store average, and
    it moves that tolerance rather than the target. The distinction matters: the
    log says a match-night basket takes a *box* 1.36x as often as an average one,
    which is a statement about format, not about how many bars people eat - the
    size signal is already in the target. Widening the tolerance for multipacks
    on those nights lets the box win a fit it would otherwise lose by a bar, and
    narrowing it on a quiet Monday hands the same fit back to the single. Without
    this the pack-share half of the occasion profile never reached the basket at
    all: it moved the ranking on the rail and stopped there.
    """
    best = None
    for sku in cat.MAGNUM_SKUS:
        p = cat.PRODUCT_BY_ID[sku]
        per = p["units_in_pack"]
        # Both the pack count below and the one above, not just the nearest.
        # Rounding alone never offers three boxes for a target of seven, so the
        # only format that could hit it exactly was the loose single - which is
        # how a group target came back as seven bars at $3.49 with a box on the
        # shelf. Costing both candidates lets the box compete for the target it
        # is actually the right answer to.
        for qty in sorted({max(1, units // per), max(1, -(-units // per))}):
            delivered = qty * per
            over = max(0, delivered - units)
            short = max(0, units - delivered)
            on_hand = stock.get(sku, 0)
            if on_hand < qty:
                continue
            # The day's pack share does not change how many bars are wanted -
            # that is already in the target - it changes how much slack a box is
            # allowed in reaching it, and the slack is deliberately asymmetric.
            # A pack night earns a box the right to over-deliver by two and none
            # at all to under-deliver, because the whole finding is that these
            # baskets go bigger. A quiet night takes the over-delivery back. A
            # symmetric widening does the opposite of what it looks like: it lets
            # the cheapest box undershoot a group target and win on unit price.
            tol_over, tol_short = LEFTOVER_TOLERANCE, LEFTOVER_TOLERANCE
            if per > 1:
                if pack_bias >= PACK_BIAS_HI:
                    tol_over, tol_short = LEFTOVER_TOLERANCE + 1, 0
                elif pack_bias <= PACK_BIAS_LO:
                    tol_over = 0
            leftover = over + short
            fit = 0 if (over <= tol_over and short <= tol_short) else leftover
            flavour_penalty = 0 if p["flavour"] == flavour else 1
            unit_price = p["price"] / per
            # Below the group threshold a shopper is buying for themselves and
            # the flavour is the point, so it outranks price. Above it they are
            # buying for a table, and price per bar starts to matter more than
            # which of their own flavours it is - which is also what the log
            # says: pack share climbs with basket size regardless of flavour.
            # Without this the fitter would rather sell nine loose bars of the
            # favourite than three boxes.
            key = ((fit, unit_price, flavour_penalty, leftover) if units >= GROUP_UNITS
                   else (fit, flavour_penalty, unit_price, leftover))
            if best is None or key < best[0]:
                best = (key, sku, qty, delivered)
    if best is None:
        return "", 0, ["OUT_OF_STOCK"]
    _, sku, qty, delivered = best
    reasons = []
    if cat.PRODUCT_BY_ID[sku]["units_in_pack"] > 1:
        reasons.append("PACK_VALUE")
    if cat.PRODUCT_BY_ID[sku]["flavour"] != flavour:
        reasons.append("SUBSTITUTE")
    return sku, qty, reasons


def recommend_pack(cart_lines: List[Dict], ctx: Dict, cf: Optional[Dict],
                   clf: Optional[Dict], stock: Dict[str, int],
                   anchors: Optional[List[Dict]] = None) -> Dict:
    """q* = constrained_round(0.40 personal + 0.35 peer + 0.25 occasion)  (§6.3)

    `anchors` carry what the basket is built around. They move two things: the
    flavour, because a pizza basket takes classic 1.6x more often than average
    and a burger basket takes caramel 1.5x more often, and the size, because a
    shared pizza carries 1.66x the bars of an average basket while a single
    burger carries 0.69x. Both are measured off the order log, and both are
    ratios applied to the household's own numbers rather than replacements for
    them - somebody who only ever buys white chocolate is not handed classic
    because they ordered a pizza.
    """
    occ = infer_occasion(cart_lines, ctx)
    personal_avg = float(cf["avg_units"]) if cf and cf.get("magnum_orders", 0) > 0 else 0.0
    peer_avg = float(clf["avg_units"]) if clf else 1.6
    occasion_units = float(occ["occasion_size"])

    if personal_avg > 0:
        q_raw = (W_Q_PERSONAL * personal_avg + W_Q_PEER * peer_avg + W_Q_OCCASION * occasion_units)
        weights_used = {"personal": W_Q_PERSONAL, "peer": W_Q_PEER, "occasion": W_Q_OCCASION}
    else:
        # No personal history: redistribute that weight onto peer and occasion
        # rather than scoring the household as if it buys nothing.
        w_peer = W_Q_PEER + W_Q_PERSONAL * 0.5
        w_occ = W_Q_OCCASION + W_Q_PERSONAL * 0.5
        q_raw = w_peer * peer_avg + w_occ * occasion_units
        weights_used = {"personal": 0.0, "peer": round(w_peer, 3), "occasion": round(w_occ, 3)}

    # The basket's own pull on size, before rounding. A shared meal genuinely
    # moves this: it is the same units_ratio the rail uses, so the cart and the
    # rail cannot disagree about how big this occasion is.
    units_ratio = 1.0
    if anchors:
        wt = sum(a.get("weight", 1.0) for a in anchors) or 1.0
        units_ratio = sum(a.get("units_ratio", 1.0) * a.get("weight", 1.0)
                          for a in anchors) / wt
        q_raw *= units_ratio

    # The hour itself moves the size, and until now it did not.
    #
    # The generator encodes this directly - quantity scales with heat, with the
    # occasion and with how many people the basket reads as - but the serving
    # policy was blind to all three, so a match-day basket in 93 degree heat
    # recommended exactly the same number of bars as the same basket on a cold
    # Tuesday. That is the policy under-fitting its own training data, not a
    # presentation problem. Betas are the generator's, halved: the log is one
    # store's worth of evidence and the policy should lean on it, not lunge.
    heat = float(ctx.get("heat_pull") or 0.62)
    group_bias = float(ctx.get("group_bias") or 0.0)
    ctx_terms: List[Dict] = []
    ctx_mult = 1.0

    def _ctx_term(code, label, mult, detail):
        nonlocal ctx_mult
        if abs(mult - 1.0) < 0.005:
            return
        ctx_mult *= mult
        ctx_terms.append({"code": code, "label": label,
                          "multiplier": round(mult, 3), "detail": detail})

    _ctx_term("CONTEXT_HEAT_QTY", "Heat", 1.0 + Q_HEAT_BETA * (heat - 0.62),
              "{:.0f}°F. Frozen dessert baskets get bigger as the temperature "
              "climbs, not just more frequent.".format(ctx.get("temperature_f", 0)))
    # Day of week and the match window, measured. Both arrive pre-combined as a
    # single bars lift, so the term is one multiplier with the slices that built
    # it named underneath rather than a stack of hand-set constants.
    occ_lift = float(ctx.get("occasion_bars_lift") or 1.0)
    if abs(occ_lift - 1.0) > 0.005:
        names = " and ".join(t["label"].lower() for t in (ctx.get("occasion_terms") or [])) or "this slot"
        _ctx_term("CONTEXT_OCCASION_QTY", "Day and occasion", occ_lift,
                  "Measured on the order log: %s baskets carry %.2f\u00d7 the bars of "
                  "an average one." % (names, occ_lift))
    _ctx_term("CONTEXT_GROUP_QTY", "Group hour", 1.0 + Q_GROUP_BETA * group_bias,
              "Shareable plates are running {:.0f}% above normal in this hour, "
              "which reads as more people at the table.".format(group_bias * 100.0))
    if float(ctx.get("rain_in") or 0.0) > 0.05:
        _ctx_term("CONTEXT_RAIN_QTY", "Rain", 1.0 + Q_RAIN_BETA,
                  "{:.2f} in of rain. Wet nights skew to smaller, solo "
                  "orders.".format(ctx.get("rain_in") or 0.0))
    q_before_ctx = q_raw
    q_raw *= ctx_mult

    units_target = int(max(1, min(MAX_UNITS, round(q_raw))))

    base_shares: Dict[str, float] = {}
    flavour_reason = "PEER_FLAVOUR_SHARE"
    if cf and cf.get("flavour_shares"):
        base_shares = dict(cf["flavour_shares"])
        flavour_reason = "PERSONAL_FAVOURITE"
    elif clf and clf.get("flavour_shares"):
        base_shares = dict(clf["flavour_shares"])
    if not base_shares:
        base_shares = {"classic": 1.0}

    flavour_scores = dict(base_shares)
    pair_pull: Dict[str, float] = {}
    if anchors:
        wt = sum(a.get("weight", 1.0) for a in anchors) or 1.0
        for f in set(list(base_shares) + ["classic", "almond", "caramel", "white"]):
            lift = sum(a["flavour_lift"].get(f, 1.0) * a.get("weight", 1.0)
                       for a in anchors) / wt
            pair_pull[f] = round(lift, 3)
            # Multiplicative, so the household's own mix stays the base and the
            # basket tilts it. A flavour they never buy has a share near zero and
            # no lift can promote it out of nowhere.
            flavour_scores[f] = base_shares.get(f, 0.02) * lift

    flavour = max(flavour_scores, key=flavour_scores.get)
    if pair_pull and flavour != max(base_shares, key=base_shares.get):
        flavour_reason = "PAIR_FLAVOUR_SWITCH"
    elif pair_pull and pair_pull.get(flavour, 1.0) >= 1.2:
        flavour_reason = "PAIR_FLAVOUR_CONFIRMED"

    pack_bias = float(ctx.get("occasion_pack_lift") or 1.0)
    sku, qty, pack_reasons = _pack_for_units(units_target, stock, flavour, pack_bias)
    reasons = [occ["reason_code"], flavour_reason] + pack_reasons
    if pack_bias >= PACK_BIAS_HI:
        reasons.append("CART_FORMAT_PACK_NIGHT")
    elif pack_bias <= PACK_BIAS_LO:
        reasons.append("CART_FORMAT_SINGLE_NIGHT")
    reasons += [t["code"] for t in ctx_terms]
    if ctx.get("in_game_window"):
        reasons.append("CONTEXT_MATCH")
    if ctx.get("heat_pull", 0) >= 0.72:
        reasons.append("CONTEXT_HEAT")
    if cf and cf.get("due_ratio", 0) >= 0.85:
        reasons.append("PERSONAL_REORDER_WINDOW")

    p = cat.PRODUCT_BY_ID.get(sku)
    alternatives = []
    for alt in cat.MAGNUM_SKUS:
        if alt == sku or stock.get(alt, 0) <= 0:
            continue
        ap = cat.PRODUCT_BY_ID[alt]
        alternatives.append({
            "sku_id": alt, "name": ap["name"], "price": ap["price"],
            "units_in_pack": ap["units_in_pack"],
            "unit_price": round(ap["price"] / ap["units_in_pack"], 2),
            "on_hand": stock.get(alt, 0),
        })
    alternatives.sort(key=lambda a: a["unit_price"])

    return {
        "sku_id": sku or None,
        "name": p["name"] if p else None,
        "price": p["price"] if p else None,
        "units_in_pack": p["units_in_pack"] if p else None,
        "quantity": qty,
        "units_delivered": (p["units_in_pack"] * qty) if p else 0,
        "units_target": units_target,
        "q_raw": round(q_raw, 3),
        "q_before_context": round(q_before_ctx, 3),
        "context_multiplier": round(ctx_mult, 3),
        "context_terms": ctx_terms,
        "pairing": ({"units_ratio": round(units_ratio, 3),
                     "flavour_pull": pair_pull,
                     "chosen_flavour": flavour,
                     "base_flavour": max(base_shares, key=base_shares.get),
                     "base_shares": {k: round(v, 4) for k, v in base_shares.items()},
                     "anchors": [{"sku_id": a.get("sku_id"), "name": a.get("name"),
                                  "n": a.get("n"), "units_ratio": a.get("units_ratio"),
                                  "top_flavour": a.get("top_flavour")} for a in anchors]}
                    if anchors else None),
        "inputs": {"personal_avg_units": round(personal_avg, 2),
                   "peer_avg_units": round(peer_avg, 2),
                   "occasion_units": occasion_units,
                   "weights": weights_used},
        "occasion": occ,
        "reason_codes": reasons[:5],
        "alternatives": alternatives[:3],
        "policy_version": POLICY_VERSION,
    }


# ==========================================================================
# Offer decisioning (§4.3, §6.4)
# ==========================================================================

# `label` is a *template*. Depth is decided per hour, so a fixed "20% off" would
# have sat next to an actual 13% on the same card - the kind of small, visible
# contradiction that costs you the room. `{pct}` is filled from the depth that
# was actually chosen.
OFFER_LIBRARY = [
    {"arm": "voucher20", "offer_id": "MAGNUM20", "label": "{pct}% off any Magnum",
     "discount_pct": 0.20, "contact_cost": 0.05, "min_basket": 0.0, "applies_to": "any"},
    {"arm": "multipack_value", "offer_id": "PACKVALUE", "label": "{pct}% off a multipack",
     "discount_pct": 0.08, "contact_cost": 0.05, "min_basket": 15.0, "applies_to": "multipack"},
    {"arm": "flavour_discovery", "offer_id": "TRYNEW", "label": "Try a flavor you have not had",
     "discount_pct": 0.00, "contact_cost": 0.03, "min_basket": 0.0, "applies_to": "any"},
    {"arm": "reminder", "offer_id": "REORDER", "label": "Your usual, one tap away",
     "discount_pct": 0.00, "contact_cost": 0.02, "min_basket": 0.0, "applies_to": "any"},
]


# How much the hour itself is allowed to move the size. These mirror the terms
# the generator writes into the log (heat and group both scale quantity there),
# taken at roughly half strength: the policy should follow the evidence without
# out-running it.
Q_HEAT_BETA = 0.45
# Retired: the match window's effect on size is now read off the log as part of
# `occasion_bars_lift` rather than asserted here. Kept as a named zero so the
# history of the number is visible instead of silently vanishing.
Q_GAME_BETA = 0.0
Q_GROUP_BETA = 0.18
Q_RAIN_BETA = -0.10


def size_phrase(rec: Dict) -> str:
    """"3 bars" / "a 3-pack (3 bars)". One definition, because the push copy, the
    suggestion card and the cart all quote the same size and must not disagree."""
    units = int(rec.get("units_delivered") or 0)
    qty = int(rec.get("quantity") or 1)
    pack = int(rec.get("units_in_pack") or 1)
    if pack > 1:
        return ("{} × {}-pack ({} bars)".format(qty, pack, units) if qty > 1
                else "a {}-pack ({} bars)".format(pack, units))
    return "{} bars".format(units) if units != 1 else "1 bar"


# Asymmetric for the same reason the conditions term is: a quiet slot has to be
# bought, a busy one only has to be not-overpaid. Leaning equally hard both ways
# would be tidier and would describe a business nobody runs.
SLOT_BETA_QUIET = 0.30
SLOT_BETA_BUSY = 0.10


# Soft bounds. Same limits as the clamps they replaced, without the flat spot
# past the edge - see the docstring on discount_depth.
SLACK_LIMIT = 0.45
SLOT_LIMIT = 1.2
MIN_DISCOUNT_PCT = 0.04
# Where the depth curve starts bending away from the 25% cap. Set to the
# standard note itself, so the soft cap is the *exact* identity right up to an
# unadjusted 20% and the last five points are stretched over an unbounded input:
# two very slow hours then stay in the order the model put them in instead of
# both printing 25%. Landing it exactly here rather than a little below is what
# keeps the generator byte-identical - it calls discount_depth on the same base
# rates, and a knee at 0.18 turned an unadjusted 20% into 19.7% and would have
# shifted the log on the next regeneration for no gain. Softening from the floor
# instead - the first version of this - is what a soft cap looks like when
# nobody checks the middle: it turned that same unadjusted 20% into 15.2%.
SOFT_CAP_KNEE = MAX_DISCOUNT_PCT * 0.8


def _soft_cap(x: float, lo: float, hi: float, knee: float = SOFT_CAP_KNEE) -> float:
    """Hold x inside [lo, hi) monotonically, without a flat spot at either end.

    `lo` is a plain floor - there is no structure in a negative discount worth
    preserving. Between `lo` and `knee` this is the identity. Above `knee` the
    exponential approaches `hi` and never arrives, so two depths that would both
    have clamped come out distinguishable and in the right order.
    """
    if x <= lo:
        return lo
    if x <= knee:
        return x
    span = hi - knee
    return knee + span * (1.0 - math.exp(-(x - knee) / span))


def discount_depth(base_pct: float, demand_index: float,
                   slot_index: float = 1.0) -> Tuple[float, Optional[str], Dict]:
    """How deep the discount should be, given how the hour is actually trading.

    A flat 20% note on every hour of the year is a pricing decision nobody would
    defend out loud. When demand is soft the discount has to buy the volume;
    when the store is already busy, paying for orders that were coming anyway is
    pure margin donated.

    Two separate questions, priced separately, because they answer to different
    things and a reviewer needs to see which one moved:

    * **Conditions** - `demand_index`, how this hour is trading against the same
      hour under ordinary conditions. Weather, the match, a street festival.
    * **The slot** - `slot_index`, how busy this day and hour are in the first
      place. Saturday dinner against Tuesday lunch. This term was missing
      entirely, and its absence was visible: `demand_index` divides the day back
      out by construction, so every day of the week priced identically. The two
      are disjoint by construction, so adding them counts nothing twice.

    The slot term is logarithmic because the index is multiplicative - twice as
    busy should read as one step whichever end of the range it happens at.

    Every bound in here is a *soft* bound, and that is the whole reason this
    function was revisited. Hard clamps have the same range and throw away
    everything past the edge: with `min(0.45, ...)` on the slack and
    `min(MAX_DISCOUNT_PCT, ...)` on the result, a cool Tuesday afternoon and a
    rainy Wednesday midnight both saturated and printed the identical 23.3%
    coupon, for two households, on two conditions with nothing in common. `tanh`
    and the exponential soft-cap below hold exactly the same limits - the slack
    never leaves +/-0.45, the depth never reaches MAX_DISCOUNT_PCT - while
    staying strictly monotone, so the ordering survives all the way out. Inside
    the ordinary range both are near-identity and nothing measurable changes.
    """
    if base_pct <= 0.0:
        return 0.0, None, {}
    slack = SLACK_LIMIT * math.tanh((1.0 - demand_index) / SLACK_LIMIT)
    # Asymmetric on purpose. A discount exists to buy volume that was not coming
    # anyway, so soft demand is leaned on hard; strong demand is backed away from
    # gently, because even on a busy night there is a tail of price-sensitive
    # shoppers a shallow note still converts. Symmetry here would be tidier and
    # would describe a business nobody runs.
    beta = 2.2 if slack > 0 else 0.85
    cond_adj = beta * slack
    slot_pressure = 0.0
    if slot_index > 0:
        doublings = math.log(slot_index) / math.log(2.0)
        slot_pressure = SLOT_LIMIT * math.tanh(doublings / SLOT_LIMIT)
    slot_adj = -(SLOT_BETA_BUSY if slot_pressure > 0 else SLOT_BETA_QUIET) * slot_pressure
    raw = base_pct * (1.0 + cond_adj + slot_adj)
    pct = _soft_cap(raw, MIN_DISCOUNT_PCT, MAX_DISCOUNT_PCT)
    code = None
    if pct > base_pct * 1.08:
        code = "OFFER_DEEPER_SLOW_DEMAND"
    elif pct < base_pct * 0.92:
        code = "OFFER_TRIMMED_BUSY_DEMAND"
    parts = {
        "conditions": round(cond_adj, 4),
        "slot": round(slot_adj, 4),
        "slot_index": round(slot_index, 4),
        "slot_code": ("OFFER_TRIMMED_BUSY_SLOT" if slot_adj < -0.02
                      else "OFFER_DEEPER_QUIET_SLOT" if slot_adj > 0.02 else None),
    }
    return round(pct, 4), code, parts


# How far the depth may move for the household in front of us, on top of what
# the hour already decided. Deliberately smaller than the demand term: the hour
# is measured off thousands of orders, one household is measured off a few dozen.
HH_CADENCE_BETA = 0.34
HH_PRICE_BETA = 0.30
HH_PRICE_MID = 0.35


def household_depth(pct: float, cf: Optional[Dict]) -> Tuple[float, Optional[str]]:
    """Move the depth for the household, not just for the hour.

    Two things about a household change what a coupon is worth spending on them,
    and both are read off their own order log rather than assumed. How far past
    their own rhythm they have drifted: a household three weeks late on a
    twelve-day cadence is drifting away, and buying that trip back is worth more
    than shaving a point off the note. And how they have historically bought:
    somebody who has paid full price for two years does not need to be paid to
    come back, and discounting them is margin donated to a decision they had
    already made.

    Both terms are continuous rather than banded. A threshold would mean two
    households a day apart in their cadence saw prices four points apart, which
    is not a difference either of them did anything to earn. The direction is
    always named, so the number on the banner can be defended line by line.
    """
    if pct <= 0.0 or not cf:
        return round(pct, 4), None
    due = float(cf.get("due_ratio") or 0.0)
    resp = float(cf.get("discount_response") or 0.0)
    # Clamped asymmetrically: being very overdue keeps mattering for a while,
    # being early stops mattering once they are clearly not lapsing.
    cadence_term = HH_CADENCE_BETA * max(-0.60, min(1.00, due - 1.0))
    price_term = HH_PRICE_BETA * max(-0.35, min(0.45, resp - HH_PRICE_MID))
    terms = [
        (cadence_term, "OFFER_DEEPER_LAPSED" if cadence_term > 0 else "OFFER_TRIMMED_EARLY"),
        (price_term, "OFFER_DEEPER_PRICE_LED" if price_term > 0 else "OFFER_TRIMMED_FULL_PRICE"),
    ]
    adj = cadence_term + price_term
    # Same soft cap as the hour's term uses, and for the same reason: two
    # households whose adjusted depth would both have clamped at 25% are not the
    # same household, and the banner should not say they are.
    out = _soft_cap(pct * (1.0 + adj), MIN_DISCOUNT_PCT, MAX_DISCOUNT_PCT)
    if abs(out - pct) < 0.004:
        return round(pct, 4), None
    # Name the term that actually carried the move, not the one that happened to
    # be checked first.
    code = max(terms, key=lambda t: abs(t[0]))[1]
    return round(out, 4), code


def decide_offer(ctx: Dict, cf: Optional[Dict], clf: Optional[Dict], stock: Dict[str, int],
                 uplift_table: Dict[str, Dict[str, float]], recommended_sku: Optional[str],
                 basket_value: float = 0.0, cluster: str = "", consent: bool = True,
                 contacts_24h: int = 0, contacts_7d: int = 0,
                 hours_since_order: float = 999.0,
                 channel: str = "push") -> Dict:
    """Rank candidate offers on expected incremental margin, then apply the
    guardrails. Restraint is the expected outcome, not a failure mode.

    `channel` matters because the guardrails are not all the same kind of rule.
    Consent, the frequency cap and the post-purchase window all exist to stop us
    interrupting somebody - they are rules about *contacting* a person. A price
    shown to a shopper who is already on the page, already holding a basket, is
    not a contact: nobody is being interrupted and no contact is being paid for.
    Applying the contact rules there meant a household who ordered four hours ago
    browsed the whole store at full price for no reason anybody could defend, and
    it made the on-site banner disagree with the suggestion card next to it. The
    economic guardrails - minimum uplift, margin, the discount cap - apply on
    both channels, because those are rules about the money.
    """
    candidates = []
    onsite = channel == "onsite"
    demand_index = float(ctx.get("demand_index") or 1.0)
    hard_block = None
    if onsite:
        hard_block = None
    elif not consent:
        hard_block = "NO_MARKETING_CONSENT"
    elif contacts_24h >= 1 or contacts_7d >= FREQ_CAP_PER_7D:
        hard_block = "FREQUENCY_CAPPED"
    elif hours_since_order < 12:
        hard_block = "POST_PURCHASE_SUPPRESS"

    rec = cat.PRODUCT_BY_ID.get(recommended_sku) if recommended_sku else None
    for off in OFFER_LIBRARY:
        reasons = []
        eligible = True
        fail = None
        target_sku = recommended_sku
        if off["applies_to"] == "multipack":
            packs = [s for s in cat.MAGNUM_PACKS if stock.get(s, 0) > 0]
            # Prefer a pack in a flavour the household already buys before
            # defaulting to whatever is on the shelf.
            fav = max((cf or {}).get("flavour_shares", {}).items(),
                      key=lambda kv: kv[1], default=(None, 0))[0]
            packs.sort(key=lambda s: (cat.PRODUCT_BY_ID[s].get("flavour") != fav,
                                      -stock.get(s, 0)))
            target_sku = packs[0] if packs else None
        if not target_sku or stock.get(target_sku, 0) <= 0:
            eligible, fail = False, "OUT_OF_STOCK"
        elif basket_value < off["min_basket"]:
            eligible, fail = False, "BASKET_BELOW_MINIMUM"

        uplift = uplift_table.get(off["arm"], {}).get(cluster,
                 uplift_table.get(off["arm"], {}).get("__all__", 0.0))
        # Depth first, because everything downstream depends on it: a deeper
        # note moves more people AND costs more margin, and the ranking has to
        # see both halves of that trade at the same time.
        pct, depth_code, depth_parts = discount_depth(
            off["discount_pct"], demand_index, float(ctx.get("slot_index") or 1.0))
        # The hour set the depth; the household adjusts it. Order matters - the
        # uplift has to be scaled by the depth the shopper will actually see.
        pct, hh_code = household_depth(pct, cf)
        if off["discount_pct"] > 0.0:
            uplift *= pct / off["discount_pct"]
            if depth_code:
                reasons.append(depth_code)
            if hh_code:
                reasons.append(hh_code)
            if depth_parts.get("slot_code"):
                reasons.append(depth_parts["slot_code"])
        p = cat.PRODUCT_BY_ID.get(target_sku) if target_sku else None
        unit_margin = p["unit_margin"] if p else 0.0
        price = p["price"] if p else 0.0
        discount_value = price * pct
        # EIC(a) = uplift x margin-kept - discount paid on the lift - cost of contact
        contact_cost = 0.0 if onsite else off["contact_cost"]
        expected_margin = uplift * (unit_margin - discount_value) - contact_cost

        # This floor stays on both channels, and the reason is worth recording
        # because dropping it looks right and is not. It reads like a contact
        # rule - do not interrupt somebody unless you will move them - and by
        # that argument it has no business gating an on-site price. But it is
        # also the only thing standing between the ranking and a zero-discount
        # arm: with no contact cost to pay, "try a flavour you have not had"
        # scores a higher expected margin than any voucher, every hour of the
        # week, because it costs nothing and still moves ~1.8% of people. Relax
        # the floor on-site and the system stops discounting altogether. That is
        # arguably the correct economic answer and it is certainly not a
        # guardrail to remove as a side effect of a pricing change.
        if eligible and uplift < MIN_UPLIFT_PP:
            eligible, fail = False, "OFFER_UPLIFT_BELOW_THRESHOLD"
        elif eligible and expected_margin <= 0:
            eligible, fail = False, "OFFER_MARGIN_NEGATIVE"
        elif eligible and pct > MAX_DISCOUNT_PCT:
            eligible, fail = False, "OFFER_DISCOUNT_CAP"
        elif eligible:
            reasons.append("OFFER_MARGIN_OK")

        candidates.append({
            "arm": off["arm"], "offer_id": off["offer_id"],
            "label": off["label"].replace("{pct}", str(int(round(pct * 100)))),
            "target_sku": target_sku, "discount_pct": pct,
            "base_discount_pct": off["discount_pct"],
            "depth_reason": depth_code,
            "depth_parts": depth_parts,
            "household_depth_reason": hh_code,
            "discount_value": round(discount_value, 2),
            "contact_cost": contact_cost,
            "predicted_uplift_pp": round(uplift * 100, 3),
            "expected_incremental_margin": round(expected_margin, 4),
            "eligible": bool(eligible and not hard_block),
            "failed_rule": hard_block or fail,
            "reason_codes": reasons,
        })

    viable = [c for c in candidates if c["eligible"]]
    viable.sort(key=lambda c: -c["expected_incremental_margin"])
    top_reasons: List[str] = []
    if viable:
        chosen = viable[0]
        action = "show_offer" if chosen["discount_pct"] > 0 else "show_recommendation"
        suppression = None
        top_reasons.append("OFFER_MARGIN_OK")
        runner = viable[1] if len(viable) > 1 else None
        blocked_voucher = next((c for c in candidates
                                if c["arm"] == "voucher20" and not c["eligible"]), None)
        if blocked_voucher and blocked_voucher["failed_rule"] == "OFFER_MARGIN_NEGATIVE":
            # Worth saying out loud: the arm with the biggest measured lift was
            # rejected because the discount costs more than the lift returns.
            top_reasons.append("OFFER_DISCOUNT_NOT_NEEDED")
        if runner:
            top_reasons.append("OFFER_RANKED_BY_MARGIN")
    else:
        chosen = None
        action = "suppress" if hard_block else "show_recommendation"
        suppression = hard_block or (
            "OFFER_MARGIN_NEGATIVE"
            if any(c["failed_rule"] == "OFFER_MARGIN_NEGATIVE" for c in candidates)
            else "OFFER_UPLIFT_BELOW_THRESHOLD")
        top_reasons.append(suppression)

    return {
        "action": action,
        "offer": chosen,
        "suppression_reason": suppression,
        "reason_codes": top_reasons,
        "candidates": candidates,
        "channel": channel,
        "guardrails": {
            "min_uplift_pp": MIN_UPLIFT_PP * 100,
            "max_discount_pct": MAX_DISCOUNT_PCT * 100,
            "frequency_cap": "1 per %dh, %d per 7d" % (FREQ_CAP_HOURS, FREQ_CAP_PER_7D),
            "contacts_24h": contacts_24h, "contacts_7d": contacts_7d,
        },
        "policy_version": POLICY_VERSION,
    }


# ==========================================================================
# Reorder timing (§4.5)
# ==========================================================================

def reorder_candidate(cf: Dict, ctx: Dict, consent: bool = True,
                      contacts_24h: int = 0, contacts_7d: int = 0) -> Dict:
    cadence = max(2.0, float(cf.get("cadence_days") or 12.0))
    days_since = float(cf.get("days_since_magnum") if cf.get("days_since_magnum") is not None else cadence)
    days_out = cadence - days_since
    # Discrete-time hazard around the household's own cadence.
    z = -days_out / max(1.5, cadence * 0.35)
    p7 = _clip(1.0 / (1.0 + math.exp(-z)) * 0.92 + 0.03, 0.01, 0.97)

    hour = int(cf.get("usual_hour") or 20)
    offset_days = int(max(0, min(14, round(days_out))))

    reasons = ["PERSONAL_REORDER_WINDOW"]
    if ctx.get("heat_pull", 0) >= 0.72:
        p7 = _clip(p7 * 1.08, 0.01, 0.97)
        reasons.append("CONTEXT_HEAT")
    if ctx.get("in_game_window"):
        reasons.append("CONTEXT_MATCH")

    suppression = None
    if not consent:
        suppression = "NO_MARKETING_CONSENT"
    elif days_since < 1.5:
        suppression = "POST_PURCHASE_SUPPRESS"
    elif contacts_24h >= 1 or contacts_7d >= FREQ_CAP_PER_7D:
        suppression = "FREQUENCY_CAPPED"

    if suppression:
        action = "hold"
    elif p7 > 0.72:
        action = "reminder"
    elif p7 > 0.45:
        action = "multipack_value"
    elif p7 > 0.22:
        action = "flavour_discovery"
    else:
        action = "hold"

    return {
        "days_until_due": round(days_out, 2),
        "candidate_offset_days": offset_days,
        "candidate_hour": hour,
        "probability_7d": round(p7, 4),
        "action": action,
        "suppression_reason": suppression,
        "cadence_days": round(cadence, 2),
        "days_since_purchase": round(days_since, 2),
        "reason_codes": reasons if not suppression else [suppression],
        "policy_version": POLICY_VERSION,
    }


# ==========================================================================
# Demand forecast and stock action (§4.6, §6.3)
# ==========================================================================

# --------------------------------------------------------------------------
# Flavour response (§4.6a)
# --------------------------------------------------------------------------
# The store-and-SKU rate says how much of a flavour a shelf sells per unit of
# demand index. On its own that is a constant, which means every flavour rides
# exactly the same hourly curve and the mix is frozen: a flavour that is 30% of
# the shelf at 6am is still 30% of it at the 8pm peak. That is not what the
# order log says. Flavour is chosen at a different moment than the decision to
# buy ice cream at all - who is ordering at 11pm is not who is ordering at 2pm,
# and what they reach for differs.
#
# So each flavour carries an hour-of-day shape and a heat response on top of
# the shared demand curve. The shapes below are read off the hour histogram of
# magnum lines by flavour, rounded to something a human can read:
#
#   classic  - the default. Flat, mildly favoured in the hot middle of the day
#              when people want the one they already know.
#   almond   - an evening bar. Rises through dinner, peaks with the 8-10pm slot.
#   caramel  - the late one. Its share is small at noon and largest after 11pm.
#   white    - daytime and heat-driven. The strongest temperature response of
#              the four, and the first to fade once the sun is down.
#
# The shapes are deliberately means-preserving over a full day (each averages
# ~1.0), so this re-ranks the mix hour to hour without inflating or deflating
# total demand for the store.
FLAVOUR_HOUR_SHAPE: Dict[str, List[float]] = {
    #        0    1    2    3    4    5    6    7    8    9   10   11
    "classic": [0.82, 0.78, 0.75, 0.75, 0.80, 0.90, 1.00, 1.05, 1.08, 1.10, 1.14, 1.20,
                1.26, 1.28, 1.24, 1.18, 1.10, 1.04, 1.00, 0.98, 0.96, 0.94, 0.90, 0.86],
    #       12   13   14   15   16   17   18   19   20   21   22   23
    "almond": [0.72, 0.66, 0.62, 0.60, 0.62, 0.68, 0.74, 0.78, 0.82, 0.86, 0.90, 0.94,
               0.98, 1.00, 1.02, 1.06, 1.14, 1.26, 1.40, 1.48, 1.46, 1.32, 1.10, 0.88],
    "caramel": [1.44, 1.34, 1.18, 1.00, 0.86, 0.74, 0.66, 0.62, 0.60, 0.62, 0.66, 0.70,
                0.74, 0.78, 0.82, 0.86, 0.90, 0.94, 1.00, 1.08, 1.20, 1.36, 1.50, 1.52],
    "white": [0.62, 0.58, 0.56, 0.58, 0.66, 0.80, 0.96, 1.12, 1.26, 1.38, 1.46, 1.52,
              1.54, 1.50, 1.42, 1.30, 1.16, 1.02, 0.90, 0.80, 0.74, 0.70, 0.66, 0.62],
}

# Extra units per flavour for every degree F above 72, as a multiplier on the
# hour shape. White chocolate moves most with heat, caramel least - a caramel
# bar at midnight sells the same whether it is 70 or 90 outside.
FLAVOUR_HEAT_SLOPE: Dict[str, float] = {
    "classic": 0.006, "almond": 0.004, "caramel": 0.001, "white": 0.011,
}

HEAT_BASE_F = 72.0


def flavour_modifier(flavour: Optional[str], hour: int, temperature_f: float) -> float:
    """How much of this hour's demand goes to this flavour, relative to a
    flavour with no preference at all. 1.0 for an unknown flavour, so a new SKU
    degrades to the shared curve rather than to zero."""
    shape = FLAVOUR_HOUR_SHAPE.get(flavour or "")
    if not shape:
        return 1.0
    heat = 1.0 + FLAVOUR_HEAT_SLOPE.get(flavour or "", 0.0) * (float(temperature_f) - HEAT_BASE_F)
    return max(0.15, shape[int(hour) % 24] * max(0.5, heat))


def forecast_series(rate: float, ctx: Dict, horizon: int = 48,
                    flavour: Optional[str] = None) -> List[Dict]:
    """Seasonal hourly baseline x context multipliers - the V1 demand model.

    Pass `flavour` to layer that flavour's own hour-of-day and heat response on
    top; omit it for the shape the store sells as a whole."""
    out = []
    for h in cx.snapshot_hours(ctx, horizon):
        mu = max(0.02, rate * h["absolute_index"]
                 * flavour_modifier(flavour, h["hour"], h["temperature_f"]))
        sd = math.sqrt(mu * 1.8)
        out.append({
            "offset": h["offset"], "hour": h["hour"], "day": h["day"],
            "p10": round(max(0.0, mu - 1.2816 * sd), 3),
            "p50": round(mu, 3),
            "p90": round(mu + 1.2816 * sd, 3),
            "demand_index": h["demand_index"],
            "absolute_index": h["absolute_index"],
            "slot_index": h["slot_index"],
            "temperature_f": h["temperature_f"],
            "in_game_window": h["in_game_window"],
            "timestamp": h.get("timestamp"),
        })
    return out


def stock_action(series: List[Dict], on_hand: int, inbound: int, ctx: Dict,
                 transfer_lead_minutes: int = 75,
                 safety_stock: Optional[int] = None) -> Dict:
    """gap = available + inbound_before_peak - forecast_p90 - safety_stock

    Safety stock scales with the hour it is protecting rather than sitting at a
    flat number. A fixed six units is most of a dark-store shelf: it marked
    every SKU at risk during a snowstorm, when the honest answer was that
    nobody was buying ice cream that afternoon.
    """
    peak = cx.peak_window(series)
    upto = max(1, peak["offset"] + 1)
    if safety_stock is None:
        busiest = max((h["p50"] for h in series[:upto]), default=0.0)
        safety_stock = int(max(2, math.ceil(1.25 * busiest)))
    p90_to_peak = sum(h["p90"] for h in series[:upto])
    p50_to_peak = sum(h["p50"] for h in series[:upto])
    available = int(on_hand)
    gap = available + int(inbound) - p90_to_peak - safety_stock

    if gap < 0:
        status = "stockout_risk"
    elif available - p50_to_peak < safety_stock:
        status = "watch"
    else:
        status = "healthy"

    action_qty = 0
    if gap < 0:
        action_qty = int(math.ceil(abs(gap) / 6.0) * 6)      # transfer rounding, 6-unit cases

    lead_h = transfer_lead_minutes / 60.0
    needed_by_offset = max(0, peak["offset"] - lead_h)

    return {
        "status": status,
        "on_hand": available,
        "inbound": int(inbound),
        "safety_stock": safety_stock,
        "forecast_p50_to_peak": round(p50_to_peak, 2),
        "forecast_p90_to_peak": round(p90_to_peak, 2),
        "gap": round(gap, 2),
        "action": "transfer" if action_qty else "none",
        "action_units": action_qty,
        "peak": peak,
        "needed_by_offset_hours": round(needed_by_offset, 1),
        "transfer_lead_minutes": transfer_lead_minutes,
        "reason_codes": ["LOW_STOCK"] if status != "healthy" else [],
    }
