"""Decision reason codes (Appendix B of the build document).

Every recommendation, offer and stock action the application shows must be
explainable by these codes. The customer-facing string is deliberately hedged -
"suggested because", never "AI knows" (§7.4).
"""
from __future__ import annotations

from typing import Dict, List

REASONS: Dict[str, Dict[str, str]] = {
    "PERSONAL_FAVOURITE": {
        "label": "Your usual flavor",
        "customer": "You often choose this flavor.",
        "family": "personal"},
    "PERSONAL_REORDER_WINDOW": {
        "label": "About when you reorder",
        "customer": "This is close to your usual reorder time.",
        "family": "personal"},
    "PERSONAL_PACK_HABIT": {
        "label": "Matches your usual size",
        "customer": "You usually buy this size.",
        "family": "personal"},
    "PAIR_STRONG": {
        "label": "Goes with what you're ordering",
        "customer": "This flavor shows up often in baskets like yours.",
        "family": "pairing"},
    "PAIR_WEAK": {
        "label": "Less common with this order",
        "customer": "This flavor is a rarer match for what's in your basket.",
        "family": "pairing"},
    "PAIR_SHARED_BASKET": {
        "label": "Looks like a shared order",
        "customer": "Orders like this one usually need more than a single bar.",
        "family": "pairing"},
    "PAIR_FLAVOUR_SWITCH": {
        "label": "Matched to your meal",
        "customer": "We moved off your usual flavor to match what you're eating.",
        "family": "pairing"},
    "PAIR_FLAVOUR_CONFIRMED": {
        "label": "Your usual, and a good match",
        "customer": "Your usual flavor also happens to suit this meal.",
        "family": "pairing"},
    "PEER_CO_PURCHASE": {
        "label": "Common with this order",
        "customer": "Similar dinner baskets often include this product.",
        "family": "peer"},
    "PEER_FLAVOUR_SHARE": {
        "label": "Popular with similar shoppers",
        "customer": "Shoppers with similar patterns pick this flavor most.",
        "family": "peer"},
    "CONTEXT_HEAT_QTY": {
        "label": "Heat raises the count",
        "customer": "Hot weather makes baskets bigger, not just more frequent.",
        "family": "context"},
    "CONTEXT_MATCH_QTY": {
        "label": "Match day raises the count",
        "customer": "Baskets built around a game run larger.",
        "family": "context"},
    "CONTEXT_GROUP_QTY": {
        "label": "Group hour raises the count",
        "customer": "More people at the table means more bars.",
        "family": "context"},
    "CONTEXT_RAIN_QTY": {
        "label": "Rain lowers the count",
        "customer": "Wet nights skew to smaller, solo orders.",
        "family": "context"},
    "CONTEXT_HEAT": {
        "label": "Hot out",
        "customer": "Hot weather raises frozen-dessert demand.",
        "family": "context"},
    "CONTEXT_MATCH": {
        "label": "Game night",
        "customer": "Game-night baskets tend to include shareable treats.",
        "family": "context"},
    "CONTEXT_EVENT": {
        "label": "Local event",
        "customer": "A local event is raising group orders nearby.",
        "family": "context"},
    "CONTEXT_LATE": {
        "label": "Late night",
        "customer": "Late-night orders skew to a single serving.",
        "family": "context"},
    "BASKET_SOLO": {
        "label": "Looks like one person",
        "customer": "This basket appears to be for one person.",
        "family": "basket"},
    "BASKET_GROUP": {
        "label": "Looks like a group",
        "customer": "Meal and drink quantities suggest a group order.",
        "family": "basket"},
    "PACK_VALUE": {
        "label": "Better per-bar price",
        "customer": "This pack fits the inferred group at lower unit cost.",
        "family": "basket"},
    "LOW_STOCK": {
        "label": "Low stock",
        "customer": "Limited stock reduced the ranking or triggered a substitute.",
        "family": "operations"},
    "SUBSTITUTE": {
        "label": "Substitute",
        "customer": "Your usual pick is out at this store; this is the closest match.",
        "family": "operations"},
    "OFFER_MARGIN_OK": {
        "label": "Positive margin",
        "customer": "The eligible offer remains positive-margin in the simulation.",
        "family": "economics"},
    "OFFER_UPLIFT_BELOW_THRESHOLD": {
        "label": "Uplift too small",
        "customer": "The predicted change in behaviour was too small to justify a discount.",
        "family": "economics"},
    "OFFER_MARGIN_NEGATIVE": {
        "label": "Loses money",
        "customer": "After the discount and the cost of contact there was no margin left.",
        "family": "economics"},
    "FREQUENCY_CAPPED": {
        "label": "Contact limit reached",
        "customer": "The customer has reached the contact limit.",
        "family": "guardrail"},
    "POST_PURCHASE_SUPPRESS": {
        "label": "Just ordered",
        "customer": "A recent purchase closes the reorder window.",
        "family": "guardrail"},
    "NO_MARKETING_CONSENT": {
        "label": "No consent",
        "customer": "This household has not consented to marketing contact.",
        "family": "guardrail"},
    "OUT_OF_STOCK": {
        "label": "Out of stock",
        "customer": "This item is not available at the delivering store right now.",
        "family": "operations"},
    "NEW_CUSTOMER": {
        "label": "Not enough history",
        "customer": "We do not have enough history yet, so this uses similar shoppers instead.",
        "family": "personal"},
    "OFFER_DISCOUNT_NOT_NEEDED": {"label": "Discount not needed", "customer": "The biggest-lift discount was rejected: it costs more than the lift it buys.", "family": "economics"},
    "CONTEXT_HEAT_FLAVOUR": {"label": "Lighter in the heat", "customer": "On days this warm the lighter bars outsell the rich ones, so they move up.", "family": "context"},
    "CONTEXT_COLD_FLAVOUR": {"label": "Richer in the cold", "customer": "In cold weather the richer chocolate and caramel bars outsell the light ones.", "family": "context"},
    "OFFER_DEEPER_LAPSED": {"label": "Deeper - past their rhythm", "customer": "It has been longer than usual since their last one, so the coupon goes deeper to win the trip back.", "family": "economics"},
    "OFFER_TRIMMED_EARLY": {"label": "Trimmed - already due back", "customer": "They are ahead of their own reorder rhythm, so the note stays light.", "family": "economics"},
    "OFFER_TRIMMED_FULL_PRICE": {"label": "Trimmed - pays full price", "customer": "This household mostly buys without an offer, so a deep discount would be margin donated.", "family": "economics"},
    "OFFER_DEEPER_PRICE_LED": {"label": "Deeper - buys on offer", "customer": "This household buys on offer more often than most, so the note is what does the work.", "family": "economics"},
    "CONTEXT_SNOW": {"label": "Snow", "customer": "It is snowing - the whole order comes to the door or it does not happen.", "family": "context"},
    "CONTEXT_WEEKEND": {"label": "Weekend basket", "customer": "Weekend baskets take a box rather than a single more often than a weeknight.", "family": "context"},
    "CONTEXT_WEEKNIGHT": {"label": "Weeknight basket", "customer": "Weeknight baskets run smaller and more solo.", "family": "context"},
    "CONTEXT_OCCASION_PACK": {"label": "Packs over singles today", "customer": "Baskets on this day and in this window take a box rather than a single more often than average.", "family": "context"},
    "CART_FORMAT_PACK_NIGHT": {"label": "A box fits this night", "customer": "Baskets on nights like this one take a box far more often than average, so the fitter lets a box win a size it would otherwise lose by a bar.", "family": "context"},
    "CART_FORMAT_SINGLE_NIGHT": {"label": "A single fits this night", "customer": "Baskets on quiet nights like this one stay with loose bars, so the fitter holds the box to an exact fit.", "family": "context"},
    "CONTEXT_OCCASION_SINGLE": {"label": "Singles over packs today", "customer": "Baskets on this day take a single bar rather than a box more often than average.", "family": "context"},
    "CONTEXT_OCCASION_FLAVOUR": {"label": "Flavour runs hot today", "customer": "This flavour over-indexes on this day and in this window.", "family": "context"},
    "CONTEXT_OCCASION_QTY": {"label": "Day and occasion", "customer": "Baskets on this day and in this window carry more bars than an average one.", "family": "context"},
    "OFFER_TRIMMED_BUSY_SLOT": {"label": "Trimmed - busy slot", "customer": "This is one of the busier slots of the week, so the coupon does not need to be deep.", "family": "economics"},
    "OFFER_DEEPER_QUIET_SLOT": {"label": "Deeper - quiet slot", "customer": "This is one of the quieter slots of the week, so the coupon goes deeper.", "family": "economics"},
    "OFFER_DEEPER_SLOW_DEMAND": {"label": "Deeper - quiet hour", "customer": "Orders are running below normal right now, so the discount goes deeper to move volume.", "family": "economics"},
    "OFFER_TRIMMED_BUSY_DEMAND": {"label": "Trimmed - busy hour", "customer": "The store is already busy, so we trim the discount rather than pay for orders that were coming anyway.", "family": "economics"},
    "OFFER_RANKED_BY_MARGIN": {"label": "Ranked on margin", "customer": "Offers were ranked on expected incremental margin, not on lift alone.", "family": "economics"},
}


def explain(code: str) -> Dict[str, str]:
    r = REASONS.get(code)
    if not r:
        return {"code": code, "label": code, "customer": code, "family": "other"}
    return {"code": code, "label": r["label"], "customer": r["customer"], "family": r["family"]}


def explain_all(codes: List[str]) -> List[Dict[str, str]]:
    seen, out = set(), []
    for c in codes:
        if c and c not in seen:
            seen.add(c)
            out.append(explain(c))
    return out
