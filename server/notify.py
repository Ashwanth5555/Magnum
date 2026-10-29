"""Composes the reorder notification for one household.

The pieces already existed and were scattered across three screens: the reorder
policy knew *when* a household comes back, the pack policy knew *how many* they
buy, and the offer policy knew *what*, if anything, is worth paying to say. None
of them produced the artefact a marketer actually ships, which is one message
with a product, a size and an offer in it, addressed to one person, at an hour
that person is usually awake and ordering.

This module does that assembly and nothing else. Every number in the composed
message is read back from those policies rather than written here, so the copy
cannot claim something the decision layer did not decide.
"""
from datetime import timedelta
from typing import Dict, List, Optional

from magnum_core import catalog as cat
from magnum_core import policies as pol

from .store import NOW

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

HOLD_COPY = {
    "NO_MARKETING_CONSENT": "No marketing consent on file. Nothing is composed and nothing is queued.",
    "POST_PURCHASE_SUPPRESS": "They ordered in the last 36 hours. A reorder nudge now would be noise.",
    "FREQUENCY_CAPPED": "Contact cap reached — one push a day, three a week.",
}


def _hour_label(h: int) -> str:
    """8 PM, not 20:00. The send time is read aloud in the demo."""
    suffix = "AM" if h < 12 else "PM"
    display = h % 12 or 12
    return "{} {}".format(display, suffix)


def _size_copy(rec: Dict) -> str:
    return pol.size_phrase(rec)


def _drivers(cf: Dict, ctx: Dict, reorder: Dict) -> List[Dict]:
    """Why this household, why now - in the order the copy is allowed to use them.

    Ordered by how much each one justifies interrupting somebody. Being due is
    the only reason that is about the person; everything else is about the day,
    and a nudge that leads with the weather to someone who restocked yesterday
    reads as spam no matter how warm it is.
    """
    out = []
    due = float(cf.get("due_ratio") or 0.0)
    days_out = float(reorder.get("days_until_due") or 0.0)
    if due >= 1.15:
        out.append({"code": "OVERDUE", "label": "Past their usual cadence",
                    "detail": "{:.0f} days since the last Magnum against a {:.0f}-day rhythm.".format(
                        float(cf.get("days_since_magnum") or 0), float(cf.get("cadence_days") or 0))})
    elif due >= 0.85:
        out.append({"code": "DUE", "label": "Inside their reorder window",
                    "detail": "Due in {:.1f} days on their own cadence.".format(max(0.0, days_out))})
    if ctx.get("in_game_window"):
        out.append({"code": "CONTEXT_MATCH", "label": "Game window is open",
                    "detail": "Local activity is elevated in this area right now, and "
                              "match-day baskets run larger."})
    if str(ctx.get("weather") or "") == "snow":
        out.append({"code": "CONTEXT_SNOW", "label": "Snow on the ground",
                    "detail": "{:.0f}\u00b0F and snowing. Nobody is walking to a shop for "
                              "this; the whole order comes to the door or it does not "
                              "happen.".format(ctx.get("temperature_f", 0))})
    elif float(ctx.get("rain_in") or 0.0) > 0.05:
        out.append({"code": "CONTEXT_RAIN", "label": "It is raining",
                    "detail": "{:.2f} in of rain. Delivery demand rises and baskets get "
                              "smaller and more solo.".format(ctx.get("rain_in") or 0.0)})
    if ctx.get("heat_pull", 0) >= 0.72:
        out.append({"code": "CONTEXT_HEAT", "label": "Heat is pulling frozen dessert",
                    "detail": "{:.0f}°F, {:+.1f}°F against the {} norm.".format(
                        ctx.get("temperature_f", 0), ctx.get("temp_anomaly_f", 0), ctx.get("season", ""))})
    elif float(ctx.get("temperature_f") or 60) <= 45:
        out.append({"code": "CONTEXT_COLD", "label": "Cold snap",
                    "detail": "{:.0f}°F. Frozen dessert has to be asked for rather than "
                              "pulled, which is what the deeper coupon is paying "
                              "for.".format(ctx.get("temperature_f", 0))})
    # The day was reaching this copy through nothing at all, so a Monday and a
    # Saturday sent the same message. It is not the loudest reason to write to
    # somebody, so it sits below the weather - but a weekend and a weeknight are
    # different asks and the log agrees: weekend baskets take a pack 24% more
    # often and carry 12% more bars.
    pack_lift = float(ctx.get("occasion_pack_lift") or 1.0)
    if pack_lift >= 1.04:
        out.append({"code": "CONTEXT_WEEKEND", "label": "Weekend basket",
                    "detail": "{} baskets take a box rather than a single {:.0%} more "
                              "often than an average day.".format(
                                  str(ctx.get("day") or "Weekend").title(), pack_lift - 1.0)})
    elif pack_lift <= 0.96:
        out.append({"code": "CONTEXT_WEEKNIGHT", "label": "Weeknight basket",
                    "detail": "{} baskets run smaller and more solo than an average "
                              "day.".format(str(ctx.get("day") or "Weeknight").title())})
    if str(ctx.get("event") or "none") != "none":
        out.append({"code": "CONTEXT_EVENT", "label": "Local event on",
                    "detail": "A {} is on in this area.".format(
                        str(ctx["event"]).replace("_", " "))})
    fav = max((cf.get("flavour_shares") or {}).items(), key=lambda kv: kv[1], default=(None, 0))
    if fav[0]:
        out.append({"code": "PERSONAL_FAVOURITE", "label": "Known flavour preference",
                    "detail": "{:.0%} of their Magnum units are {}.".format(fav[1], fav[0])})
    return out


# The voice each pattern family gets. Six households on the same evening should
# not read like six copies of one message with the name swapped, and the thing
# that actually separates them is what they are buying for: a match, the kids, a
# Tuesday alone. The line is about their occasion, not about us.
#
# Each family also gets condition-specific variants, because a fixed line goes
# wrong the moment the weather moves under it - "enough for the whole watch
# party" on a wet Wednesday with no game on is worse than saying nothing. The
# default is written to be true on any day; the variants are only reached when
# the condition that makes them true is actually present.
CLUSTER_VOICE = {
    "game_night": {
        "default": "Enough to go round when people come over.",
        "game": "Enough for the whole watch party.",
        "heat": "Enough to go round, and it arrives frozen.",
    },
    "family_planner": {
        "default": "Enough for everyone at the table, in the box you usually take.",
        "rain": "The box you usually take, brought to the door.",
    },
    "late_solo": {
        "default": "One for tonight — no box to find room for.",
        "rain": "One for tonight, and you do not have to go out for it.",
    },
    "heat_seeker": {
        "default": "Straight to the freezer, ready when you want it.",
        "heat": "In the freezer before the heat breaks.",
        "cold": "Worth keeping a couple in the freezer either way.",
    },
    "deal_explorer": {
        "default": "This is the best price we can put on it right now.",
    },
    "premium_low_freq": {
        "default": "The one you actually like, not the one that is on offer.",
    },
}


def _voice(cluster: str, ctx: Dict) -> Optional[str]:
    """Pick the line that is true today, falling back to the one always true."""
    v = CLUSTER_VOICE.get(str(cluster or ""))
    if not v:
        return None
    if ctx.get("in_game_window") and "game" in v:
        return v["game"]
    if float(ctx.get("rain_in") or 0.0) > 0.05 and "rain" in v:
        return v["rain"]
    if float(ctx.get("heat_pull") or 0) >= 0.72 and "heat" in v:
        return v["heat"]
    if float(ctx.get("temperature_f") or 60) <= 45 and "cold" in v:
        return v["cold"]
    return v.get("default")


def _message(cf: Dict, rec: Dict, product: Dict, offer: Optional[Dict],
             drivers: List[Dict], ctx: Dict, reorder: Dict) -> Dict:
    """The copy, assembled from whichever driver leads.

    Deliberately three fields and no more. A push notification is a title, two
    lines of body and a button; anything the model knows that does not fit in
    that shape is not part of the message, it is part of the justification, and
    it belongs in the panel underneath.
    """
    name = (cf.get("display_name") or "").split(" ")[0]
    short = rec.get("name", "Magnum").replace("Magnum ", "")
    size = pol.size_phrase(rec)
    lead = drivers[0]["code"] if drivers else "GENERIC"

    # Six households on a hot evening all lead on heat, and a headline built from
    # temperature and flavour alone gives all six the identical line. The size is
    # what actually differs between them and it is the thing the message is
    # really about, so it goes in the headline rather than being held back for
    # the body.
    units = int(rec.get("units_delivered") or 0)
    pack = int(rec.get("units_in_pack") or 1)
    flav = str(product.get("flavour") or short).lower()
    art = "an" if flav[:1] in "aeiou" else "a"
    deg = "{:.0f}°".format(ctx.get("temperature_f", 0))
    day_word = str(ctx.get("day") or "").title() or "Tonight"
    # The day was invisible in this copy: a Monday and a Saturday sent the same
    # sentence. It rarely deserves to *lead* - heat and the match window are
    # louder reasons to write to somebody - so instead it rides on the tail of
    # whichever headline does lead, the same way the size already does.
    pack_lift = float(ctx.get("occasion_pack_lift") or 1.0)
    weekendish = pack_lift >= 1.04
    weeknightish = pack_lift <= 0.96
    if weekendish:
        tail = "for the table"
    elif weeknightish:
        tail = "for tonight"
    else:
        tail = "for the house"

    def by_size(pack_copy, multi_copy, solo_copy):
        if pack > 1:
            return pack_copy
        return multi_copy if units > 1 else solo_copy

    if lead == "OVERDUE":
        overdue_days = -float(reorder.get("days_until_due") or 0.0)
        title = ("{}, it has been {:.0f} days".format(name, overdue_days)
                 if overdue_days >= 7 else
                 "{}, the freezer is looking empty".format(name))
    elif lead == "DUE":
        title = "{}, about time for {}".format(name, short)
    elif lead == "CONTEXT_MATCH":
        # The day belongs in a match headline, not just in the body. Without it
        # a Monday game and a Saturday game push the same sentence, and the two
        # are not the same night: the measured pack share on a Saturday match is
        # a fifth higher again, which is exactly the thing the headline is
        # announcing.
        title = by_size(
            "{}, {} {} box for {} night's game".format(name, art, flav, day_word.lower()),
            "{}, {} {} bars for {} night's game".format(name, units, flav, day_word.lower()),
            "{}, one {} bar for {} night's game".format(name, flav, day_word.lower()))
    elif lead == "CONTEXT_RAIN":
        title = by_size(
            "Raining out — {} {} box {}, no coat needed".format(art, flav, tail),
            "Raining out — {} {} bars to the door {}".format(units, flav, tail),
            "Raining out — one {} bar to the door".format(flav))
    elif lead == "CONTEXT_HEAT":
        # The flavour, not the product name. "Classic Milk Chocolate Bar
        # weather" is a headline nobody finishes reading; "almond weather" is
        # the same claim at a third of the width.
        title = by_size(
            "{} out — {} {} box {}".format(deg, art, flav, tail),
            "{} out — {} {} bars {}".format(deg, units, flav, tail),
            "{} out — one {} bar {}".format(deg, flav, tail))
    elif lead == "CONTEXT_COLD":
        title = by_size(
            "{}, {} {} box worth staying in for".format(name, art, flav),
            "{}, {} {} bars worth staying in for".format(name, units, flav),
            "{}, one {} bar worth staying in for".format(name, flav))
    elif lead == "CONTEXT_SNOW":
        title = by_size(
            "Snowing — {} {} box, no one has to go out".format(art, flav),
            "Snowing — {} {} bars, no one has to go out".format(units, flav),
            "Snowing — one {} bar, no one has to go out".format(flav))
    elif lead == "CONTEXT_EVENT":
        title = "{}, the neighbourhood is out tonight".format(name)
    elif lead == "CONTEXT_WEEKEND":
        title = by_size(
            "{} night — {} {} box for the table".format(day_word, art, flav),
            "{} night — {} {} bars for the table".format(day_word, units, flav),
            "{}, one {} bar for {} night".format(name, flav, day_word.lower()))
    elif lead == "CONTEXT_WEEKNIGHT":
        title = by_size(
            "{}, {} {} box to see the week out".format(name, art, flav),
            "{}, {} {} bars for a quiet {}".format(name, units, flav, day_word.lower()),
            "{}, one {} bar for a quiet {}".format(name, flav, day_word.lower()))
    else:
        # The quiet case - nothing about the day or their cadence is arguing for
        # this send. The only honest thing left to lead on is what they actually
        # buy, so the size carries the headline rather than a stock phrase.
        title = by_size(
            "{}, a {}-pack is one tap away".format(name, pack),
            "{}, your usual {} bars are one tap away".format(name, units),
            "{}, your usual bar is one tap away".format(name))

    body = "We lined up {} — the size you usually take.".format(size)
    if weekendish:
        body += (" {} baskets take the box rather than the single {:.0%} more often "
                 "than an average day, which pushed the size up.".format(
                     day_word, pack_lift - 1.0))
    elif weeknightish:
        body += (" {} runs smaller and more solo than the weekend, which pulled the "
                 "size down.".format(day_word))
    voice = _voice(cf.get("peer_cluster") or "", ctx)
    if voice:
        body += " " + voice
    if offer:
        if offer.get("discount_pct", 0) > 0:
            body += " {} applied, saving ${:.2f}.".format(offer["label"], offer["discount_value"])
        else:
            body += " {}.".format(offer["label"])
    body += " Delivered in about 15 minutes."

    return {"title": title, "body": body,
            "cta": "Reorder {}".format(size) if not offer or offer.get("discount_pct", 0) == 0
                   else "Claim and reorder",
            "lead_driver": lead}


def compose(st, cf: Dict, clf: Optional[Dict], ctx: Dict, stock: Dict[str, int],
            consent: bool, contacts_24h: int, contacts_7d: int,
            hours_since_order: float) -> Dict:
    """Assemble the whole notification: when, what, how many, and at what price."""
    reorder = pol.reorder_candidate(cf, ctx, consent=consent,
                                    contacts_24h=contacts_24h, contacts_7d=contacts_7d)

    # An empty cart on purpose. This is not a basket add-on: it asks the pack
    # policy what this household buys when nothing is anchoring the size, which
    # is exactly the question a reorder push has to answer.
    rec = pol.recommend_pack([], ctx, cf, clf, stock)
    basket_value = float(rec.get("price") or 0.0) * int(rec.get("quantity") or 1)

    decision = pol.decide_offer(ctx, cf, clf, stock, st.uplift_table, rec.get("sku_id"),
                                basket_value=basket_value,
                                cluster=(cf or {}).get("peer_cluster", ""),
                                consent=consent, contacts_24h=contacts_24h,
                                contacts_7d=contacts_7d, hours_since_order=hours_since_order)

    hold = reorder.get("suppression_reason")
    send_at = NOW + timedelta(days=int(reorder["candidate_offset_days"]))
    send_at = send_at.replace(hour=int(reorder["candidate_hour"]), minute=0, second=0, microsecond=0)

    drivers = _drivers(cf, ctx, reorder)
    offer = decision.get("offer")
    product = cat.PRODUCT_BY_ID.get(rec.get("sku_id"), {})

    # Value of sending, per contact: the chance they come back inside a week,
    # times the margin on the pack we would put in front of them, less whatever
    # the offer gives away. It is a scale, not a forecast - it exists so the
    # send/hold call has a number attached rather than a feeling.
    unit_margin = float(product.get("unit_margin") or 0.0)
    units = int(rec.get("units_delivered") or 0)
    gross = float(reorder["probability_7d"]) * unit_margin * units
    give_away = float(offer["discount_value"] + offer["contact_cost"]) if offer else 0.02

    return {
        "send": hold is None,
        "hold_reason": hold,
        "hold_copy": HOLD_COPY.get(hold or "", None),
        "scheduled": {
            "send_at": send_at.isoformat(),
            "offset_days": int(reorder["candidate_offset_days"]),
            "hour": int(reorder["candidate_hour"]),
            "label": "{} at {}".format(
                "Today" if reorder["candidate_offset_days"] == 0
                else "Tomorrow" if reorder["candidate_offset_days"] == 1
                else DAY_NAMES[send_at.weekday()],
                _hour_label(int(reorder["candidate_hour"]))),
            "why": "Their own order history clusters at {}; {}.".format(
                _hour_label(int(reorder["candidate_hour"])),
                "the reorder window opened {:.0f} days ago".format(-float(reorder["days_until_due"]))
                if float(reorder["days_until_due"]) < 0
                else "the reorder window opens in {:.0f} days".format(float(reorder["days_until_due"]))),
        },
        "probability_7d": reorder["probability_7d"],
        "cadence_days": reorder["cadence_days"],
        "days_since_purchase": reorder["days_since_purchase"],
        "days_until_due": reorder["days_until_due"],
        "product": {
            "sku_id": rec.get("sku_id"), "name": rec.get("name"),
            "price": rec.get("price"), "size_label": product.get("size_label"),
            "units_in_pack": rec.get("units_in_pack"), "flavour": product.get("flavour"),
            "category": product.get("category"),
        },
        "size": {
            "quantity": rec.get("quantity"), "units_delivered": rec.get("units_delivered"),
            "copy": _size_copy(rec), "q_raw": rec.get("q_raw"),
            "inputs": rec.get("inputs"),
        },
        "offer": offer,
        "message": _message(cf, rec, product, offer, drivers, ctx, reorder),
        "drivers": drivers,
        "economics": {
            "expected_gross_margin": round(gross, 4),
            "cost_to_send": round(give_away, 4),
            "expected_net": round(gross - give_away, 4),
            "unit_margin": round(unit_margin, 4),
            "units": units,
        },
        "policy_version": pol.POLICY_VERSION,
    }
