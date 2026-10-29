"""External context: the only signals a person types into the demo.

Section 4.1 of the build document is strict about this - the context gate
carries external conditions and nothing else. Everything personal, peer, basket
or inventory related is loaded silently by the server.

US market (NY / CT metro): Fahrenheit, four seasons, and "game day" rather than a
cricket fixture. The multipliers here are the single demand model shared by the
synthetic generator (which uses them to draw sessions and baskets) and the
forecast service (which uses them to predict), so when a reviewer toggles game
day on the demand desk the number moves for exactly the reason the copy says.
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# Vocabulary for the context gate (§4.1)
# --------------------------------------------------------------------------

DAYS: List[str] = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

TIME_WINDOWS: List[Dict] = [
    {"id": "morning", "label": "8-11 AM", "start_hour": 8, "end_hour": 11, "peak_hour": 9},
    {"id": "lunch", "label": "11 AM-2 PM", "start_hour": 11, "end_hour": 14, "peak_hour": 12},
    {"id": "afternoon", "label": "2-5 PM", "start_hour": 14, "end_hour": 17, "peak_hour": 16},
    {"id": "evening", "label": "5-7 PM", "start_hour": 17, "end_hour": 19, "peak_hour": 18},
    {"id": "dinner", "label": "7-10 PM", "start_hour": 19, "end_hour": 22, "peak_hour": 20},
    {"id": "late", "label": "10 PM-12 AM", "start_hour": 22, "end_hour": 24, "peak_hour": 23},
]
TIME_WINDOW_BY_ID: Dict[str, Dict] = {w["id"]: w for w in TIME_WINDOWS}

# norm_temp is the seasonal daily mean in Fahrenheit for Chicago.
SEASONS: List[Dict] = [
    {"id": "summer", "label": "Summer", "months": (6, 7, 8), "norm_temp": 76.0, "norm_humidity": 68.0, "multiplier": 1.22},
    {"id": "spring", "label": "Spring", "months": (3, 4, 5), "norm_temp": 55.0, "norm_humidity": 63.0, "multiplier": 1.00},
    {"id": "fall", "label": "Fall", "months": (9, 10, 11), "norm_temp": 57.0, "norm_humidity": 69.0, "multiplier": 0.90},
    {"id": "winter", "label": "Winter", "months": (12, 1, 2), "norm_temp": 35.0, "norm_humidity": 66.0, "multiplier": 0.70},
]
SEASON_BY_ID: Dict[str, Dict] = {s["id"]: s for s in SEASONS}

WEATHER: List[Dict] = [
    {"id": "hot", "label": "Hot", "temp_delta": 12.0, "humidity_delta": -4.0, "rain_in": 0.0, "multiplier": 1.32},
    {"id": "warm", "label": "Warm", "temp_delta": 4.0, "humidity_delta": 0.0, "rain_in": 0.0, "multiplier": 1.09},
    {"id": "cool", "label": "Cool", "temp_delta": -8.0, "humidity_delta": 3.0, "rain_in": 0.0, "multiplier": 0.84},
    {"id": "rain", "label": "Rain", "temp_delta": -6.0, "humidity_delta": 16.0, "rain_in": 0.28, "multiplier": 0.76},
    {"id": "snow", "label": "Snow", "temp_delta": -14.0, "humidity_delta": 10.0, "rain_in": 0.12, "multiplier": 0.58},
]
WEATHER_BY_ID: Dict[str, Dict] = {w["id"]: w for w in WEATHER}

EVENTS: List[Dict] = [
    {"id": "none", "label": "No local event", "multiplier": 1.00, "group_bias": 0.00},
    {"id": "street_festival", "label": "Street festival", "multiplier": 1.24, "group_bias": 0.55},
    {"id": "concert", "label": "Concert", "multiplier": 1.12, "group_bias": 0.32},
    {"id": "public_holiday", "label": "Public holiday", "multiplier": 1.15, "group_bias": 0.38},
]
EVENT_BY_ID: Dict[str, Dict] = {e["id"]: e for e in EVENTS}

ACTIVITY: List[Dict] = [
    {"id": "high", "label": "High", "multiplier": 1.13},
    {"id": "normal", "label": "Normal", "multiplier": 1.00},
    {"id": "low", "label": "Low", "multiplier": 0.89},
]
ACTIVITY_BY_ID: Dict[str, Dict] = {a["id"]: a for a in ACTIVITY}

# NY / CT sports calendar - Yankees, Mets, Knicks, Nets, Giants, Jets,
# Rangers, Islanders, plus UConn in Connecticut.
GAME_MULTIPLIER = 1.20            # overall lift during a game window
GAME_SHAREABLE_BIAS = 0.48        # extra pull toward shareable formats
DEFAULT_GAME_START = 19
DEFAULT_GAME_END = 23

# Hour-of-day shape for frozen-dessert demand. Index = hour 0-23.
HOUR_CURVE: List[float] = [
    0.26, 0.16, 0.11, 0.09, 0.09, 0.11, 0.19, 0.30,
    0.42, 0.50, 0.58, 0.72, 0.88, 0.90, 0.78, 0.74,
    0.84, 0.98, 1.14, 1.36, 1.54, 1.44, 1.16, 0.68,
]
WEEKDAY_CURVE: List[float] = [0.87, 0.84, 0.89, 0.98, 1.20, 1.32, 1.14]  # Mon..Sun

# Reference moment used to normalise the absolute index to ~1.00:
# Wednesday, 4 PM, summer, warm, no game, no event, normal activity.
REFERENCE = {
    "day": "wednesday", "hour": 16, "season": "summer", "weather": "warm",
    "game_day": False, "event": "none", "activity": "normal",
}

FREEZING_F = 32.0


def season_for_month(month: int) -> str:
    for s in SEASONS:
        if month in s["months"]:
            return s["id"]
    return "summer"


def hour_multiplier(hour: int) -> float:
    return HOUR_CURVE[int(hour) % 24]


def raw_demand_multiplier(day: str, hour: int, season: str, weather: str,
                          game_day: bool, event: str, activity: str,
                          in_game_window: bool = False) -> float:
    """Un-normalised demand multiplier. Shared by the generator and the forecast."""
    dow = DAYS.index(day) if day in DAYS else 2
    m = HOUR_CURVE[int(hour) % 24]
    m *= WEEKDAY_CURVE[dow]
    m *= SEASON_BY_ID.get(season, SEASON_BY_ID["summer"])["multiplier"]
    m *= WEATHER_BY_ID.get(weather, WEATHER_BY_ID["warm"])["multiplier"]
    m *= EVENT_BY_ID.get(event, EVENT_BY_ID["none"])["multiplier"]
    m *= ACTIVITY_BY_ID.get(activity, ACTIVITY_BY_ID["normal"])["multiplier"]
    if game_day:
        m *= GAME_MULTIPLIER if in_game_window else 1.05
    return m


_REFERENCE_MULTIPLIER = raw_demand_multiplier(
    REFERENCE["day"], REFERENCE["hour"], REFERENCE["season"], REFERENCE["weather"],
    REFERENCE["game_day"], REFERENCE["event"], REFERENCE["activity"],
)


# The order-weighted median neutral multiplier across the whole log - the
# trading level of a typical hour in which somebody actually orders, as opposed
# to a typical hour on the clock, most of which are the middle of the night.
# Measured, not chosen: see BUILD.md 22.1.
_TYPICAL_NEUTRAL = 1.3404


def temperature_for(season: str, weather: str, hour: int) -> float:
    """Fahrenheit. Diurnal swing peaks around 3 PM, bottoms around 3 AM."""
    base = SEASON_BY_ID.get(season, SEASON_BY_ID["summer"])["norm_temp"]
    delta = WEATHER_BY_ID.get(weather, WEATHER_BY_ID["warm"])["temp_delta"]
    diurnal = 7.0 * math.cos((int(hour) - 15) / 24.0 * 2 * math.pi)
    return round(base + delta + diurnal, 1)


def humidity_for(season: str, weather: str) -> float:
    base = SEASON_BY_ID.get(season, SEASON_BY_ID["summer"])["norm_humidity"]
    delta = WEATHER_BY_ID.get(weather, WEATHER_BY_ID["warm"])["humidity_delta"]
    return round(min(98.0, max(20.0, base + delta)), 1)


def plausible_weather(season: str) -> List[str]:
    """Snow is only offered in winter; a New York July whiteout is not a scenario."""
    if season == "winter":
        return ["cool", "snow", "rain", "warm"]
    if season == "summer":
        return ["hot", "warm", "cool", "rain"]
    return ["warm", "cool", "rain", "hot"]


def resolve(day: str = "friday", time_window: str = "dinner", season: str = "summer",
            weather: str = "hot", game_day: bool = True, event: str = "none",
            activity: str = "high", area_id: str = "upper-east-side",
            hour: Optional[int] = None, game_start_hour: Optional[int] = None,
            game_end_hour: Optional[int] = None) -> Dict:
    """Turn the seven gate selections into one context snapshot with features.

    The returned dict is the payload the whole application shares: search, cart,
    offer, reorder and the demand desk all reference one snapshot id, which is
    what stops the POC becoming seven unrelated dashboards (§11.4).
    """
    day = (day or "friday").lower()
    if day not in DAYS:
        day = "friday"
    window = TIME_WINDOW_BY_ID.get(time_window, TIME_WINDOW_BY_ID["dinner"])
    hour = int(window["peak_hour"]) if hour is None else int(hour)
    season = season if season in SEASON_BY_ID else "summer"
    weather = weather if weather in WEATHER_BY_ID else "warm"
    event = event if event in EVENT_BY_ID else "none"
    activity = activity if activity in ACTIVITY_BY_ID else "normal"

    g_start = DEFAULT_GAME_START if game_start_hour is None else int(game_start_hour)
    g_end = DEFAULT_GAME_END if game_end_hour is None else int(game_end_hour)
    in_game_window = bool(game_day and g_start <= hour < g_end)

    raw = raw_demand_multiplier(day, hour, season, weather, game_day, event, activity,
                                in_game_window=in_game_window)
    # Neutral counterfactual: same day and hour, ordinary conditions. Dividing by
    # it isolates what the reviewer actually changed on the gate.
    neutral = raw_demand_multiplier(day, hour, season, "warm", False, "none", "normal")
    demand_index = raw / neutral
    absolute_index = raw / _REFERENCE_MULTIPLIER
    # How busy this *slot* is - day of week, hour and season - with the
    # conditions stripped out. `demand_index` deliberately divides the day and
    # the hour back out so a reviewer can see what they themselves changed on
    # the gate; that is the right number for an explanation and the wrong one
    # for a price. A Tuesday lunch and a Saturday dinner are not equally busy,
    # and a discount blind to the difference pays full freight on the busiest
    # slot of the week. The two are disjoint by construction: `neutral` holds
    # day, hour and season, `demand_index` holds weather, occasion and activity,
    # so pricing can use both without counting anything twice.
    slot_index = neutral / _TYPICAL_NEUTRAL

    temperature = temperature_for(season, weather, hour)
    humidity = humidity_for(season, weather)
    rain_in = WEATHER_BY_ID[weather]["rain_in"]
    temp_anomaly = round(temperature - SEASON_BY_ID[season]["norm_temp"], 1)
    dow = DAYS.index(day)

    group_bias = EVENT_BY_ID[event]["group_bias"] + (GAME_SHAREABLE_BIAS if in_game_window else 0.0)
    if dow >= 4:
        group_bias += 0.20
    if window["id"] in ("dinner", "evening"):
        group_bias += 0.15
    if window["id"] == "late":
        group_bias -= 0.30

    context_id = "ctx-" + hashlib.sha1(
        "|".join([day, window["id"], season, weather, str(game_day), event, activity,
                  area_id, str(hour)]).encode("utf-8")
    ).hexdigest()[:12]

    store = None
    try:
        from magnum_core.catalog import STORE_BY_AREA
        store = STORE_BY_AREA.get(area_id, {}).get("store_id")
    except Exception:
        store = None

    return {
        "context_id": context_id,
        "area_id": area_id,
        "store_id": store,
        "day": day,
        "day_of_week": dow,
        "is_weekend": dow >= 5,
        "time_window": window["id"],
        "time_window_label": window["label"],
        "hour": hour,
        "season": season,
        "weather": weather,
        "game_day": bool(game_day),
        "game_start_hour": g_start,
        "game_end_hour": g_end,
        "in_game_window": in_game_window,
        "event": event,
        "activity": activity,
        "temperature_f": temperature,
        "humidity_pct": humidity,
        "rain_in": rain_in,
        "temp_anomaly_f": temp_anomaly,
        "activity_index": round(ACTIVITY_BY_ID[activity]["multiplier"], 3),
        "slot_index": round(slot_index, 4),
        "demand_index": round(demand_index, 3),
        "absolute_index": round(absolute_index, 3),
        "neutral_multiplier": round(neutral, 4),
        "raw_multiplier": round(raw, 4),
        "group_bias": round(group_bias, 3),
        # 0 at freezing, 1 by the mid-90s: how hard the weather pulls toward frozen dessert.
        "heat_pull": round(max(0.0, min(1.0, (temperature - FREEZING_F) / 62.0)), 3),
    }


def snapshot_hours(context: Dict, horizon: int = 48) -> List[Dict]:
    """Expand a snapshot into an hourly horizon for the demand desk.

    Weather decays toward the seasonal norm across the horizon rather than being
    held flat, so a 48-hour forecast is not the current hour repeated 48 times.
    """
    out: List[Dict] = []
    day_idx = context["day_of_week"]
    weather = context["weather"]
    season = context["season"]
    for h in range(horizon):
        hour = (context["hour"] + h) % 24
        day_offset = (context["hour"] + h) // 24
        dow = (day_idx + day_offset) % 7
        day = DAYS[dow]
        # Game day and local events apply only to the selected day.
        game = context["game_day"] and day_offset == 0
        event = context["event"] if day_offset == 0 else "none"
        in_window = bool(game and context["game_start_hour"] <= hour < context["game_end_hour"])
        decay = 0.55 ** day_offset
        raw_now = raw_demand_multiplier(day, hour, season, weather, game, event,
                                        context["activity"], in_game_window=in_window)
        raw_norm = raw_demand_multiplier(day, hour, season, "warm", False, "none", "normal")
        raw = raw_norm + (raw_now - raw_norm) * decay
        out.append({
            "offset": h,
            "day": day,
            "hour": hour,
            "in_game_window": in_window,
            "slot_index": round(raw_norm / _TYPICAL_NEUTRAL, 4),
            "demand_index": round(raw / raw_norm, 4),
            "absolute_index": round(raw / _REFERENCE_MULTIPLIER, 4),
            "temperature_f": temperature_for(season, weather if day_offset == 0 else "warm", hour),
        })
    return out


def peak_window(hours: List[Dict]) -> Dict:
    """The next demand peak in a horizon - used for 'needed by' deadlines.

    `slot_index` is read defensively because this is called on two different row
    shapes: the raw horizon out of `snapshot_hours`, and the forecast rows
    `policies.forecast_series` builds from it. Requiring the key took both
    forecast endpoints down with a 500 the moment the second shape stopped
    carrying it, which is a lot of screen to lose over an annotation nothing
    downstream depends on.
    """
    best = max(hours[:30], key=lambda h: h["absolute_index"])
    return {"offset": best["offset"], "hour": best["hour"], "day": best["day"],
            "slot_index": best.get("slot_index"),
            "demand_index": best["demand_index"], "absolute_index": best["absolute_index"]}
