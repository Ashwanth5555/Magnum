# Magnum Context-Aware Commerce POC — Build Document

**Single source of truth for this build.** Everything the implementation plan
(`Magnum_Commerce_POC_Implementation_Plan.docx`) specifies, plus the as-built record of
what actually exists in code. This file is updated whenever the application or the data
changes — see [§14 Change log](#14-change-log).

- **Project root:** `magnum-commerce-poc/`
- **Source plan:** `../Magnum_Commerce_POC_Implementation_Plan.docx` (built by `../build_magnum_plan_doc.py`)
- **Status:** in build
- **Deterministic seed:** `20260901`
- **Market:** New York + Connecticut metro, USD, Fahrenheit. Synthetic data only — no real Magnum, Uber or customer data anywhere.

---

## 0. Contents

| § | Section |
|---|---|
| 1 | North star, outcomes, demo definition |
| 2 | Scope and boundaries |
| 3 | Users and journey |
| 4 | Functional requirements |
| 5 | Data design (as specified + as built) |
| 6 | Decision logic (formulas, thresholds, policy) |
| 7 | Screen specifications |
| 8 | Architecture and API contracts |
| 9 | Uber Eats sandbox posture |
| 10 | Evaluation, KPIs, QA scenarios |
| 11 | Delivery plan |
| 12 | Backlog and acceptance checklist |
| 13 | As-built: repository map, how to run |
| 14 | Change log (append-only) |

---

## 1. North star, outcomes, demo definition

> **North-star question.** Can the experience recognise the moment, recommend the right Magnum
> type and quantity, make a responsible offer, and ensure the right store has stock? Every
> recommendation must be explainable using the same five signal families: **external context,
> current intent, personal history, similar-peer behaviour, live availability.**

Three connected surfaces:

1. **Shopper search** — intent inference, product ranking, contextual banner.
2. **Shopper cart** — basket-aware type and quantity recommendation.
3. **Demand desk** (internal) — hourly SKU demand, depletion risk, replenishment, next-best contact time.

### 1.1 Business outcomes

- Increase Magnum discovery and meal-order attach rate during high-propensity moments.
- Recommend a pack format and quantity appropriate to the current basket and inferred occasion.
- Reduce irrelevant discounts through uplift thresholds, eligibility rules and frequency caps.
- Predict the next craving window so notifications are timely rather than repetitive.
- Forecast SKU demand by store and hour so stock moves before a customer sees "out of stock".
- Create a safe synthetic-data foundation colleagues can develop against without production PII.

### 1.2 Definition of a successful demo

| Moment | What the reviewer does | What the system proves |
|---|---|---|
| Context | Selects Friday, 8 PM, summer, hot weather, match day. | Demand score and eligible offer rise; search unlocks only after context is applied. |
| Search | Searches "ice cream", "chocolate" or a meal item. | Ranking separates direct intent from attachment intent and explains personal, peer and context signals. |
| Cart | Adds one solo meal or a multi-person dinner basket. | Recommended Magnum changes from a single bar to an appropriate multipack and quantity. |
| Reorder | Switches among synthetic customers. | Next-purchase time and probability change with each customer's cadence. |
| Demand desk | Changes weather, time or match-day condition. | Hourly forecast, stockout risk and replenishment quantity respond consistently. |

---

## 2. Scope and boundaries

### 2.1 In scope (v1)

- Synthetic customer, peer-cluster, search, impression, basket, order, inventory, store, weather and event data.
- Context gate at the top of search containing **external conditions only**.
- Search, category filters, product cards, availability, personalised rank, recommendation reasons.
- Contextual banners/coupons with eligibility, margin guardrail, frequency-cap simulation.
- Cart quantity editing, totals, discount simulation, basket-aware Magnum recommendation.
- Reorder window prediction and next-notification preview.
- Store × SKU × hour demand forecast for 48 hours, plus a 3-hour operational view.
- Stockout risk, safety stock, suggested replenishment/movement quantity.
- Scenario switching across customers and external conditions.
- Event logging so every visible recommendation traces to input signals and a policy version.

### 2.2 Out of scope (v1)

- Real payment, production checkout, courier dispatch, consumer Uber account.
- Scraping or altering the live Uber Eats consumer experience.
- Production ad bidding, real push delivery, live coupon funding.
- Real customer identity or order history.
- Causal business-uplift claims from synthetic data.
- Melt-risk routing, packaging optimisation, courier handover scoring → **phase 2**.

### 2.3 Naming and legal posture

Working name **"Magnum Now"**. Described as an *Uber Eats-inspired delivery marketplace POC*,
not an Uber product. No Uber logos, trade dress, consumer screenshots or interface assets.
Synthetic merchants and test-store data only.

### 2.4 Assumptions (confirm at kickoff)

- [ ] Hyderabad first; currency INR; location granularity = postcode / store catchment.
- [ ] Magnum assortment, pack sizes, price, margin, stock are synthetic or supplied by commercial owner.
- [ ] Demo default = Rahul, Friday, 8 PM, summer, hot, match day, Banjara Hills.
- [ ] Uber test application/scopes/test store are **not** assumed available until dashboard-verified.
- [ ] Notification and coupon actions remain previews.

---

## 3. Users and journey

### 3.1 Primary users

| User | Goal | Needs from the POC |
|---|---|---|
| Shopper | Find a relevant meal or Magnum quickly; receive a credible offer. | Fast search, visible stock, relevant quantity, transparent reason, easy cart editing. |
| Commercial / brand manager | See where recommendations, offers and repeat sales create value. | Scenario controls, funnel KPIs, offer guardrails, plain-language explanations. |
| Demand planner | Know which store/SKU will run short and what to move. | Hourly forecast, on-hand, uncertainty, shortage amount, recommended action. |
| Data / product team | Validate data contracts, feature logic, model behaviour. | Synthetic ground truth, event logs, feature snapshots, policy versions, evaluation views. |
| Demo operator | Tell the story reliably in under ten minutes. | Seed scenarios, reset, deterministic outputs, no live dependencies. |

### 3.2 Seven-stage mapping

| Stage | POC capability | V1 status |
|---|---|---|
| 1. Trigger | Context-based craving and demand window. | Included |
| 2. Entry | Classify direct-intent search vs meal attachment. | Included |
| 3. Discovery | Rank products, show context-aware banner. | Included |
| 4. Selection | Recommend Magnum type, pack, quantity from basket. | Included |
| 5. Wait | Melt-risk prediction. | **Phase 2** |
| 6. Handover | Store/SKU depletion and replenishment action. | Included (demand desk) |
| 7. Reorder | Predict next purchase time and offer window. | Included |

### 3.3 Golden demo journey

1. Select **Rahul**; conditions Friday, 8 PM, summer, hot, match day, high local activity.
2. Apply. System shows demand lift, ~82% reorder likelihood, match-night Magnum offer.
3. Search "biryani"; add 2 biryani + 1 cola → attachment intent, group basket.
4. Open cart → recommendation becomes a Magnum multipack with inferred quantity and 3 reason chips.
5. Apply eligible coupon → bill shows savings, checkout labelled demo.
6. Demand desk → Magnum Almond stockout risk, suggested transfer before evening peak.
7. Set match day = no → offer, forecast and replenishment need all fall together (shared logic).

---

## 4. Functional requirements

### 4.1 Search page: external-condition gate

External conditions only. Customer history, peer cluster, basket state and inventory are **never**
manually entered here; they load silently from the selected synthetic profile and operational data.

| Field | Example values | Effect |
|---|---|---|
| Location / postcode | Banjara Hills, Jubilee Hills, Gachibowli | Store catchment, local history, inventory, forecast. |
| Day / date | Monday, Friday, Saturday, holiday | Weekly seasonality, reorder cadence, media daypart. |
| Time window | 2–5 PM, 7–10 PM, 10 PM–12 AM | Craving window, restaurant availability, delivery capacity. |
| Season | Summer, monsoon, winter | Long-term demand baseline, assortment preference. |
| Weather | Hot, warm, rainy, cool + temperature/humidity | Ice-cream propensity, cold-chain risk. |
| Match day | Yes/no; optional start/end | Group ordering, snack attachment, event-time peak. |
| Local event / holiday | Festival, concert, public holiday, none | Local footfall, group size, category mix. |
| Area activity | High, normal, low | Short-horizon demand, delivery pressure. |

**Acceptance rules**

- Search results and search input stay gated until conditions are applied.
- Changing an applied condition marks the scenario **stale**; requires re-apply (or auto-refresh with clear status).
- Applied context stays visible in a compact summary on search, cart and demand desk.
- Condition controls are keyboard-operable, labelled, 44×44 px targets, with deterministic reset to the golden scenario.

### 4.2 Search, discovery, intent classification

- Free-text query, category chips, ranked cards across Magnum, meals, drinks, sides, desserts.
- **Direct intent** when the query/product sequence is Magnum/ice-cream led; **attachment intent** when meal discovery precedes Magnum interest.
- Match score plus a short "Why this?" disclosure from personal, peer, context, basket and availability contributions.
- Never rank an unavailable SKU above an available substitute; low stock reduces rank or switches pack.
- Capture query submitted, impressions, rank, clicks, add-to-cart, no-result events with active policy version.

### 4.3 Offer and banner decision

The banner is a **decision**, not decoration: eligibility, expected incremental conversion, expected margin, contact pressure.

| Rule | Minimum POC behaviour |
|---|---|
| Eligibility | Offer SKU in stock; customer has not used it; campaign active; basket meets threshold. |
| Incrementality | Show only when predicted conversion uplift > threshold (initially **5 pp**). |
| Economics | Expected incremental margin after discount is positive; discount has a configurable cap. |
| Frequency cap | ≤ 1 offer impression per customer per 24 h and ≤ 3 per 7 days. |
| Suppression | After purchase, after repeated dismissal, or when the predicted reorder window is closed. |
| Fallback | Non-discount recommendation banner, or no banner, when guardrails fail. |

### 4.4 Cart and basket-aware recommendation

- Cart lines, quantities, removal, subtotal, fees, discount, total, clearly non-operational checkout.
- Infer occasion size from meal portions, beverage quantity, shareable sides, time, match/event context.
- Single bar (solo) → 2 bars (couple) → 3-pack (2–3 people) → 6-pack (group/family).
- Flavour: personal affinity first, peer affinity second, contextual compatibility third; respect exclusions and stock.
- Recompute immediately on any cart change.
- At least **three** short reason labels plus explicit suggested quantity.
- Coupon applies only after eligibility; ineligible selection explains exactly what is missing.

### 4.5 Reorder timing and pre-notification

- Predict days/hours to next Magnum purchase and probability within the next candidate window.
- Produce top candidate contact time, offer type, or a suppression reason.
- Use recency, frequency, preferred weekday/hour, flavour/pack cadence, last basket, cluster behaviour.
- Preview in the demand desk only — no real notification in v1.
- Suppress after a new purchase and recompute the next window.

### 4.6 Demand and stock desk

- Store, SKU, on-hand, reserved, forecast demand, prediction interval, net gap, status.
- 3-hour action view plus 48-hour hourly forecast.
- Status = healthy / watch / stockout risk from forecast plus safety stock.
- Recommend transfer/replenishment quantity and "needed by" time; never execute movement in v1.
- The same external conditions from search drive the forecast scenario.
- Record forecast version, generated-at time, data freshness.

---

## 5. Data design

### 5.1 Volume (recommended seed)

5,000 customers · 150,000 sessions · 60,000 completed orders · 450,000 events · 10 stores ·
8 Magnum SKUs · 20 companion items · 39 weeks of hourly context and inventory. Deterministic seed
so every team member sees the same golden scenarios.

### 5.2 Core datasets and minimum fields

| Dataset | Grain | Minimum fields |
|---|---|---|
| customers | customer | customer_id, home_area, household_size_band, consent flags, peer_cluster, created_at |
| products | SKU | sku_id, brand, category, flavour, pack_size, units_in_pack, price, margin, tags |
| stores | store | store_id, postcode, latitude, longitude, hours, fulfilment_capacity |
| contexts | store × hour | timestamp, day, season, temperature, humidity, rain, match_day, event, activity_index |
| sessions | session | session_id, customer_id, start_time, store_id, entry_source, assigned_policy |
| events | event | event_time, session_id, event_type, query, sku_id, rank, banner_id, cart_id |
| orders | order | order_id, customer_id, session_id, store_id, ordered_at, status, subtotal, discount |
| order_items | order line | order_id, sku_id, quantity, unit_price, margin, was_recommended |
| inventory | store × SKU × snapshot | snapshot_time, store_id, sku_id, on_hand, reserved, inbound, waste |
| offers | decision | decision_id, customer_id, session_id, offer_id, eligible, shown, reason, policy_version |
| notifications | candidate/action | customer_id, candidate_time, probability, action, suppression_reason, outcome |
| forecasts | store × SKU × future hour | generated_at, target_hour, p10, p50, p90, model_version |

### 5.3 Catalogue coverage

| Category | Illustrative SKUs | Pattern role |
|---|---|---|
| Magnum singles | Classic, Almond, Brownie, White Chocolate | Flavour affinity; solo/couple quantity. |
| Magnum packs | Almond 3-pack, Mini Classic 6-pack | Group/family quantity, value trade-off. |
| Meals | Pizza, burger, biryani, paneer wrap | Attachment intent, occasion-size inference. |
| Drinks | Cola, lime soda, water | Group-size evidence, match-night affinity. |
| Sides/snacks | Fries, nachos, chips | Event and late-night co-purchase. |
| Other desserts | Brownie, cheesecake, tub ice cream | Substitution, competitor availability, category choice. |

### 5.4 Pattern families

- **Weekend match-night indulgers** — 7–10 PM, meal + two bars, strong hot-weather response.
- **Family dessert planners** — Sunday meal, shareable sides, multipack, longer reorder cycle.
- **Late-night solo snackers** — 10 PM–midnight, one meal/snack + one premium single.
- **Heat-triggered direct seekers** — searches "ice cream" without a meal, strong temperature response.
- **Deal-sensitive explorers** — broad searches, coupon response, low loyalty, strict frequency cap.
- **Low-frequency premium buyers** — high margin, low discount need, long repeat cycle.

### 5.5 Generation rules

1. Assign latent traits first: flavour preference, household size, price sensitivity, event affinity, baseline craving rate.
2. Generate hourly contexts by location with plausible season/weather/match correlations.
3. Generate sessions from customer baseline + contextual lift; then search/attachment path, basket, conversion.
4. Generate inventory from prior stock, inbound, orders, reservations, waste. **Never** backfill stock from future demand.
5. Write ground-truth propensities and latent traits to separate evaluation tables not exposed to the UI.
6. Split train / validation / demo holdout **by time**.

### 5.6 As built

`python3 generator/generate.py` — deterministic (seed `20260901`), **6.8 s**, no network.
Writes CSVs plus `data/magnum.db` (SQLite, indexed) and `data/data_quality.json`.

**Market.** Ten store catchments — six New York, four Connecticut.

| State | Catchments |
|---|---|
| NY | Upper East Side · Chelsea · Williamsburg · Astoria · Park Slope · White Plains |
| CT | Stamford · Greenwich · Norwalk · New Haven |

Urban NY and suburban CT are given different group-occasion and transfer-lead priors, so the
demand desk compares two genuinely different operating patterns rather than ten copies of one.

**Window.** 12 weeks of hourly context, 2026-06-09 → 2026-09-01, 2,016 hours × 10 stores.
The observed history is therefore a summer window. Winter and snow scenarios still resolve
correctly on the gate because the demand model is parametric and shared (`magnum_core/context.py`),
not learned from the history — but no *observed* winter behaviour exists to validate against.
Stated here rather than discovered later.

**Volumes.**

| Table | Rows | Grain |
|---|---:|---|
| customers | 5,000 | customer |
| stores | 10 | store |
| products | 28 | SKU (8 Magnum + 20 companion) |
| contexts | 20,160 | store × hour |
| sessions | 149,427 | session |
| events | 450,000 | event |
| orders | 51,700 | order |
| order_items | 138,247 | order line |
| inventory | 120,960 | store × Magnum SKU × hour |
| offers | 72,303 | decision |
| notifications | 5,000 | reorder candidate |
| forecasts | 2,880 | store × SKU × future hour |
| latent_traits | 5,000 | **eval only — never served** |
| ground_truth | 72,303 | **eval only — never served** |

**Funnel.** 34.6% of sessions order · Magnum attach 31.6% overall, **64.8% dessert-led vs 15.8%
meal-led** · average order $33.43 across 2.41 lines · 4.1% of Magnum lines are substitutions ·
4.2% of store-SKU-hours are out of stock · 3,914 units lost to freezer shrink.

**Randomised arms.** Five arms at ~20% each. Assignment is uniform and logged; frequency caps and
post-purchase suppression are applied to *delivery* and recorded, so the randomisation survives.

| Arm | Observed uplift | True uplift |
|---|---:|---:|
| voucher20 (20% off) | +6.47 pp | +5.83 pp |
| multipack_value | +3.80 pp | +3.35 pp |
| flavour_discovery | +2.42 pp | +1.48 pp |
| reminder | +1.74 pp | +1.46 pp |
| none | — | — |

Observed recovers ground truth to within sampling noise. Two design decisions make that true:

- **Eligibility is a property of the session, not of the arm it drew.** Frequency caps are
  evaluated for every session before the arm is consulted. Otherwise the control arm silently
  collects everyone who was recently contacted or had just ordered, and every measured uplift is
  inflated by that selection.
- **Decisions are logged whether or not anything is bought.** Logging only the baskets that
  happened conditions the record on the outcome — a dessert-led session that buys nothing
  disappears — and every arm that lifts purchase inflates its own denominator. This was a real
  bug during the build: it read as +8.17 pp against a true +5.83 pp until it was fixed.

**Temporal split** (rule 6 of §5.5), by day, no household or decision crossing a boundary:
fit days 0–59 (105,110 sessions) · calibrate 60–71 (20,485) · holdout 72–83 (23,832).

**Instrumentation sampling.** Every session emits `session_started`; a deterministic 35% sample
carries the full interaction stream. That is how production client-side telemetry is actually
collected, and it holds the event table at the documented 450,000 rows instead of the 1.1 M an
unsampled stream produces. The trade-off: only instrumented sessions can be traced end to end.

**Quality gate.** Nine checks run at the end of every generation and the script exits non-zero if
any fails — referential integrity, non-negative stock, ground truth absent from every served
table, voucher carrying the largest true uplift, observed uplift within 1.5 pp of truth,
stockouts present but under 12%, and hot hours attaching more than cold (31.7% vs 14.5%).

---

## 6. Decision logic

### 6.1 Shared feature families

| Family | Examples | Used by |
|---|---|---|
| External context | day, hour, season, temperature, humidity, rain, event, match, activity | Demand, ranking, offer, quantity, reorder |
| Current intent | query tokens, category depth, dwell, clicks, add/remove sequence, entry path | Intent class, rank, banner |
| Personal history | recency, frequency, favourite flavour, pack mix, usual time, discount response | Ranking, offer, reorder |
| Peer behaviour | cluster co-purchase, flavour share, quantity distribution, time pattern | Cold start, quantity, reorder |
| Current basket | meal portions, drinks, shareables, value, inferred people | Pack, quantity, attachment offer |
| Operations | availability, on hand, reservations, capacity, competitor stock | Ranking, substitution, forecast action |

### 6.2 V1 baseline and model progression

| Decision | V1 transparent baseline | Later model |
|---|---|---|
| Intent class | Rules from first query/category and pre-Magnum cart state. | GBM or sequence classifier. |
| Product rank | Weighted score: text 35%, personal 25%, peer 15%, context 15%, stock 10%. | Learning-to-rank on calibrated conversion. |
| Quantity/pack | Occasion-size rules + personal/peer median quantity. | Multiclass pack + count/ordinal model. |
| Offer | Eligibility + uplift proxy + positive-margin + frequency cap. | Uplift model / contextual bandit with safe exploration. |
| Reorder time | Cadence and preferred weekday/hour. | Survival or discrete-time hazard model. |
| Demand | Seasonal hourly baseline × context multipliers. | Hierarchical GBM or probabilistic time series. |
| Stock action | Forecast p90 + safety stock − available − inbound. | Optimisation with transfer cost and service-level constraints. |

### 6.3 Reference formulas

```
SEARCH RANK
score(sku) = 0.35·text + 0.31·personal + 0.04·peer + 0.18·context + 0.12·availability

# When the shopper is looking at something a Magnum pairs with, a sixth family
# switches on and the five above compress by (1 - 0.28) so the weights still
# sum to one:
score(sku) = 0.72·(the five above) + 0.28·pairing
```
All components are 0–1, logged separately, exposed as human-readable reasons.
Unavailable products are filtered or heavily penalised before final ordering.

```
SUGGESTED QUANTITY
q* = constrained_round(0.40·personal_avg + 0.35·peer_avg + 0.25·occasion_size)
```
Convert q* to available pack formats, minimising leftover units. Cap by stock, basket economics
and a configurable maximum.

```
STOCK GAP
gap = available + inbound_before_peak − forecast_p90 − safety_stock
```
Negative gap → action quantity = |gap| plus transfer rounding. "Needed by" = peak start − transfer lead time.

### 6.4 Offer policy

1. Build candidate offers compatible with recommended SKU/pack and campaign schedule.
2. Remove candidates failing stock, eligibility, consent, minimum basket or prior-use rules.
3. Predict/approximate incremental conversion, incremental units, gross margin after discount.
4. Remove candidates below uplift or positive-margin thresholds; apply frequency caps.
5. Select highest expected incremental margin; else a non-discount message or no banner.
6. Log candidate set, chosen action, suppressed reasons, model/policy version, later outcome.

### 6.5 Leakage and bias controls

- No completed-order fields, later inventory, future weather or post-offer events when scoring an earlier decision.
- Customer-level splits so later behaviour cannot leak into an earlier session's training.
- Report performance by location, cluster, discount sensitivity, new/returning.
- Keep synthetic causal ground truth separate from features and UI data.
- Never call synthetic uplift an expected production result without a randomised pilot.

### 6.6 Reason codes

| Code | Customer/analyst explanation |
|---|---|
| PERSONAL_FAVOURITE | You often choose this flavour. |
| PERSONAL_REORDER_WINDOW | This is close to your usual reorder time. |
| PEER_CO_PURCHASE | Similar dinner baskets often include this product. |
| CONTEXT_HEAT | Hot weather raises frozen-dessert demand. |
| CONTEXT_MATCH | Match-night baskets tend to include shareable treats. |
| BASKET_SOLO | This basket appears to be for one person. |
| BASKET_GROUP | Meal and drink quantities suggest a group order. |
| PACK_VALUE | This pack fits the inferred group at lower unit cost. |
| LOW_STOCK | Limited stock reduced the ranking or triggered a substitute. |
| OFFER_MARGIN_OK | The eligible offer remains positive-margin in the simulation. |
| FREQUENCY_CAPPED | The customer has reached the contact limit. |
| POST_PURCHASE_SUPPRESS | A recent purchase closes the reorder window. |

---

## 7. Screen specifications

### 7.1 Screen A — Context-aware search

| Zone | Content and interaction | States |
|---|---|---|
| Header | Brand, delivery location, Search, Demand Desk, profile picker, cart count. | Desktop/mobile, active nav. |
| Context gate | Day, time, season, weather, match day, event/activity, location. Apply/reset. | Unapplied, applied, stale, loading, error. |
| Search | Keyword input, category chips, zero-result recovery. | Locked, ready, typing, results, no result. |
| Offer banner | Moment label, offer, reason, expiry/eligibility, action. | Discount, recommendation-only, suppressed. |
| Signal strip | Personal pattern, peer pattern, current demand, reorder timing. | Loaded; insufficient-history fallback. |
| Products | Ranked cards: badge, price, stock, match score, reasons, quantity control. | Available, low stock, unavailable/substitute. |
| Floating cart | Item count, subtotal, cart link. | Hidden when empty. |

### 7.2 Screen B — Cart

| Zone | Content and interaction | Key rule |
|---|---|---|
| Basket lines | Product, detail, quantity, price, remove. | Every change recomputes occasion and recommendation. |
| Smart match | Recommended Magnum, pack, quantity, reasons, add action. | Never recommend an unavailable SKU or an excessive quantity for the inferred occasion. |
| Coupon | Eligibility, code, savings, missing requirement. | Margin/frequency guardrails override UI temptation. |
| Bill | Subtotal, fees, discount, total. | No payment; checkout labelled demo-only. |
| Context summary | Applied external moment stays visible. | Cart and search share one context snapshot ID. |

### 7.3 Screen C — Demand desk

- Headline demand lift and selected scenario conditions.
- SKU cards: on-hand, forecast p50/p90, gap, risk, replenishment action.
- 48-hour chart by store/SKU with peak-window shading.
- Next-purchase card for the selected customer: time, probability, action, reason.
- Synthetic pattern table with filters for individual vs peer orders and match/weather conditions.
- Freshness, forecast version, reset-to-golden-scenario action.

### 7.4 Interaction and accessibility

- WCAG 2.1 AA contrast; risk never encoded by colour alone.
- Visible labels, focus states, 44×44 px targets where practical.
- Search, selectors, quantity controls, tabs and disclosures work by keyboard.
- Skeletons without layout shift; honour reduced motion.
- Breakpoints: 360 px mobile, tablet, 1280+ desktop.
- Copy says "suggested because", never "AI knows".

---

## 8. Architecture

### 8.1 Stack

| Layer | Recommendation | As built |
|---|---|---|
| Web client | React + TypeScript + Vite | React 19 + TS + Vite 7 + Tailwind 4 + lucide-react + recharts, compiled to `web/dist` and served by the API — single origin, single port |
| API | FastAPI or Node | FastAPI (Python 3.9) |
| Operational store | PostgreSQL; SQLite allowed for local POC | SQLite (`data/magnum.db`) + CSV source of truth |
| Analytics/features | Python + pandas | pandas / numpy generator + feature builder |
| Models | scikit-learn / LightGBM; transparent baseline first | Transparent rule baselines (v1), scikit-learn where it earns its place |
| Caching | In-memory/Redis optional | In-process catalogue + context cache |
| Charts | Existing chart library | recharts |
| Integration adapter | Server-side Uber sandbox client behind a feature flag | Stub adapter, disabled by default (`UBER_ADAPTER_ENABLED=false`) |

### 8.2 Logical request flow

1. UI requests a context snapshot for location/day/time/weather/event.
2. Recommendation API loads profile features, peer features, session intent, basket, inventory snapshot.
3. Policy service ranks products, chooses quantity/pack, evaluates banner candidates.
4. UI renders products and reasons; event collector records impressions/interactions asynchronously.
5. Forecast job writes store/SKU/hour quantiles; demand desk reads the latest version and computes stock action.
6. Optional Uber adapter syncs approved sandbox data; credentials never reach the browser.

### 8.3 API contracts

| Method and route | Purpose | Important response fields |
|---|---|---|
| `GET /api/demo/profiles` | List synthetic shopper scenarios. | id, display_name, cluster, usual_window |
| `POST /api/context/resolve` | Create applied external-context snapshot. | context_id, features, demand_index, expires_at |
| `POST /api/search` | Rank products for query and context. | intent_class, ranked_items, reason_codes, policy_version |
| `POST /api/offers/decide` | Choose/suppress banner. | action, offer, eligibility, expected_value, suppression_reason |
| `POST /api/cart/recommend` | Recommend pack and quantity. | sku, quantity, occasion_size, reasons, alternatives |
| `POST /api/events` | Capture impression/action events. | accepted, event_id |
| `GET /api/reorder/{customer_id}` | Next candidate contact time. | candidate_time, probability, action, reasons |
| `GET /api/forecast` | Store/SKU/hour forecast. | p10, p50, p90, on_hand, gap, action |
| `POST /api/demo/reset` | Restore deterministic golden scenario. | scenario_id, reset_at |

### 8.4 Event taxonomy

`session_started, context_viewed, context_applied, search_submitted, result_impression,
product_clicked, add_to_cart, remove_from_cart, recommendation_impression,
recommendation_accepted, banner_impression, banner_clicked, coupon_applied, cart_viewed,
checkout_demo_clicked, demand_action_viewed, notification_preview_viewed`

Every event carries `event_time, session_id, customer_id | anonymous_id, context_id, policy_version, experiment_arm`.

### 8.5 Security and operations

- Secrets/tokens server-side only; never committed, logged or screenshotted.
- Separate testing/production credentials and domains; reject token/domain mismatch at config validation.
- Verify webhook signatures; idempotent handlers.
- Log decisions and model versions without secrets or unnecessary customer data.
- Latency targets: search/recommendation p95 < 500 ms locally; UI acknowledgement < 100 ms.
- Feature flag disables all external integrations and keeps the demo fully synthetic.

---

## 9. Uber Eats sandbox posture

> Treat the Uber sandbox as an **optional merchant-side integration**, not the recommendation engine.
> Marketplace APIs cover stores, menus, orders, promotions, reporting. Written approval and partner
> alignment may be required. Sandbox data is simulated and may reset; sandbox access does not
> guarantee production access.

**Dashboard checklist:** application type TESTING with Eats Marketplace suite · scopes for stores,
menus, orders, promotions, reporting · client ID/secret storage owner and rotation (never values in
docs) · test store IDs and whether Integration Tech Support must provision them · webhook URL, auth
mode, signature verification · exact sandbox auth and API domains.

**Sequence after access:** server-side client-credentials token retrieval with caching/expiry →
list/retrieve test stores and map IDs → upload/retrieve test menu and map item IDs to SKUs →
sync price/availability without making Uber a feature source → webhook endpoint with signature
verification and idempotency → place a test order through the approved flow → contract tests plus a
"sandbox disconnected" fallback.

| Expectation | Plan |
|---|---|
| Control consumer Uber search results / cart banners | Not assumed; requires separate commercial agreement. |
| Manage a test store/menu/availability | Potentially supported via approved scopes and a test store. |
| Receive and process test orders | Potentially supported via webhooks and Order APIs. |
| Use production merchant/customer data | Not permitted in the POC. |
| Rely on sandbox data permanently | No — persist our own synthetic fixtures. |

References: [overview](https://developer.uber.com/docs/eats/introduction) ·
[getting started](https://developer.uber.com/docs/eats/guides/getting-started) ·
[sandbox](https://developer.uber.com/docs/eats/guides/sandbox) ·
[auth](https://developer.uber.com/docs/eats/guides/authentication) ·
[menu](https://developer.uber.com/docs/eats/guides/menu-integration) ·
[orders](https://developer.uber.com/docs/eats/guides/order-integration) ·
[webhooks](https://developer.uber.com/docs/eats/guides/webhooks)

---

## 10. Evaluation, KPIs, QA

### 10.1 Offline model metrics

| Capability | Primary metric | Required diagnostics |
|---|---|---|
| Intent class | Macro F1 / calibration | Direct vs attachment confusion; cluster and context slices. |
| Product rank | NDCG@5, MRR, recall@5 | Availability violations, new-customer performance, reason stability. |
| Quantity/pack | Exact accuracy + MAE | Over-recommendation rate, stock feasibility. |
| Offer | Uplift calibration / policy value | Margin after discount, cap breaches, negative uplift. |
| Reorder | Concordance / time-dependent AUC | Calibration by horizon; days-to-event MAE. |
| Demand | WAPE + pinball loss | Bias, p90 coverage, peak-hour and SKU/store slices. |
| Stock action | Stockout recall, excess units | False transfers, waste risk, service-level attainment. |

### 10.2 Product and business KPIs

Search→click and add-to-cart rate · Magnum attach rate on meal-led sessions and units per Magnum
basket · recommendation acceptance, pack appropriateness, removal-after-add · incremental
conversion and incremental margin per eligible offer · 7/30/90-day repeat rate and time-to-next
calibration · in-stock rate, avoided stockouts, forecast bias, waste · contact rate, dismissals,
frequency-cap compliance.

### 10.3 Pilot design

Randomise at customer or store-catchment level per contamination risk. Keep a no-personalisation
baseline, a transparent-rule treatment, later a model treatment. Pre-register primary KPI, duration,
MDE, margin guardrail, stop conditions. Never compare targeted recipients with untreated customers
without correcting selection bias.

> **Planning targets only.** Repeat rate +10%, attach +14%, craving-window orders +22%, acquisition
> cost −18%, melt refunds −50% are **hypotheses for pilot sizing**, not forecasts.

### 10.4 Demo QA scenarios

| Scenario | Expected visible result |
|---|---|
| Hot Friday match night + Rahul | Two-bar Almond/Classic offer, elevated demand, high match score, stock warning if constrained. |
| Cool Monday afternoon + Rahul | Lower demand, no urgent discount, fewer multi-unit recommendations. |
| Family profile + 2 pizzas + 3 drinks | Six-pack recommendation, quantity 1, group-occasion reasons. |
| Solo profile + 1 burger | One premium single bar; no multipack over-recommendation. |
| Favourite SKU out of stock | Available substitute ranks first; explanation mentions availability. |
| Offer frequency cap reached | No discount banner; optional non-discount recommendation. |
| Inventory below p90 forecast | Stockout risk, negative gap, replenishment amount with deadline. |
| Recent purchase just completed | Reorder notification suppressed; next window recalculated. |

### 10.5 Golden scenarios

| ID | Customer + context | Basket/search | Expected decision |
|---|---|---|---|
| G1 | Rahul; Fri 8 PM; summer; hot; match | "biryani"; 2 biryani + cola | Attachment intent; Almond/Classic ×2 or 3-pack; MAGNUM20; elevated demand. |
| G2 | Rahul; Mon 3 PM; winter; cool; no event | "ice cream" | Direct intent; favourite single ranks high; no urgent discount. |
| G3 | Emily; Sun 8 PM; warm; family cluster | 2 pizzas + 3 drinks | Mini 6-pack ×1; family reasons; moderate reorder window. |
| G4 | Arjun; Sat 11 PM; hot; match | Burger + fries | Single Classic/Brownie ×1; late-night offer if cap allows. |
| G5 | Rahul; favourite out of stock | "Magnum Almond" | Classic or Almond multipack substitute; stock reason visible. |
| G6 | Any; frequency cap reached | Eligible basket | No discount; non-discount creative or suppressed banner. |
| G7 | Banjara Hills; hot match night | Demand desk | Almond p90 exceeds stock; move units before peak. |
| G8 | Rahul; just purchased | Reorder preview | Immediate contact suppressed; next candidate recalculated. |

---

## 11. Delivery plan

| Week | Focus | Exit criteria |
|---|---|---|
| 0 / 3 days | Alignment, catalogue, golden scenarios, Uber access audit. | Signed scope; unknown API access isolated behind an assumption. |
| 1 | Data contracts and deterministic generator. | All core tables generated; data-quality report passes. |
| 2 | Search/cart UX skeleton and context gate. | Responsive flows work with rules and local fixtures. |
| 3 | Search rank, intent, reasons, offer guardrails. | Golden scenarios deterministic; events captured. |
| 4 | Cart quantity/pack recommendation and reorder baseline. | Scenario matrix passes; offer economics logged. |
| 5 | Demand forecast and stock action desk. | Time-based evaluation passes; p90 and gap displayed. |
| 6 | API hardening, optional Uber adapter, webhook test. | Synthetic fallback works; secrets server-side; contract tests pass. |
| 7 | End-to-end QA, accessibility, performance, narrative polish. | Acceptance checklist signed; demo reset reliable. |
| 8 | Stakeholder demo, experiment design, production backlog. | Decision on pilot, data access, phase 2. |

**Workstreams:** Product · Design · Frontend · Backend · Data science · Data engineering · QA ·
Commercial · Platform/legal (owners to be named at kickoff).

**Risks:** assumed Uber access unavailable → keep replica standalone · synthetic patterns too
perfect → noise, missingness, holdout, explicit labels · discount wins volume loses margin →
positive-margin guardrail + control · over-stated group size → conservative cap, pack fallback,
removal-after-add metric · forecast causes waste → p50/p90, safety stock, track excess jointly ·
personalisation feels invasive → coarse reasons, consent, caps, no sensitive traits · POC becomes
seven dashboards → one context snapshot, three-screen journey, shared policy logic.

---

## 12. Backlog and acceptance

### 12.1 Epics

| ID | Epic | Deliverable | Status |
|---|---|---|---|
| E1 | Synthetic commerce data | Schemas, generator, ground truth, seeds, quality report. | not started |
| E2 | Context service | Condition schema, applied snapshots, staleness, scenario reset. | not started |
| E3 | Search and intent | Search API/UI, rank baseline, intent class, reasons, instrumentation. | not started |
| E4 | Offer decisioning | Candidate library, eligibility, economics, cap, banner variants, logs. | not started |
| E5 | Cart intelligence | Occasion size, pack/quantity, substitutes, coupon eligibility, cart UI. | not started |
| E6 | Reorder | Cadence baseline, candidate time, probability, suppression, preview. | not started |
| E7 | Demand and inventory | Forecast pipeline, intervals, gap/action, demand desk. | not started |
| E8 | Uber adapter | Configuration, OAuth, mapping, webhook, synthetic fallback. | not started |
| E9 | Quality and evaluation | Offline metrics, scenario tests, accessibility, performance, model card. | not started |

### 12.2 Must-pass acceptance checklist

- [ ] External conditions are the only manual recommendation inputs on the search page.
- [ ] The system distinguishes direct Magnum intent from meal-attachment intent.
- [ ] Personal and peer patterns are both visible and separately explainable.
- [ ] Search recommendation includes Magnum type, rank and suggested quantity where appropriate.
- [ ] Cart recommendation changes when meal count / group evidence changes.
- [ ] Banner/offer changes with context and obeys eligibility and frequency caps.
- [ ] Reorder preview shows time, probability, action and suppression behaviour.
- [ ] Demand forecast and stock action change when the external scenario changes.
- [ ] Out-of-stock favourites are substituted without breaking the cart.
- [ ] Every decision carries a context ID and policy/model version.
- [ ] All synthetic fixtures, KPIs and demo checkout are labelled clearly.
- [ ] No secret, OAuth token, production ID or personal email appears in source, logs or deliverable.

### 12.3 Handoff package

Repository README and one-command start · data dictionary + generator README + seed · OpenAPI spec
and fixtures · decision-policy document (features, formulas, thresholds, guardrails) · model cards ·
UX component/state inventory and accessibility notes · test plan with golden scenarios · demo
script, reset runbook, disconnected fallback · production discovery backlog.

---

## 13. As-built

### 13.1 Repository map

```
magnum-commerce-poc/
  README.md           orientation and quick start
  BUILD.md            this document
  generator/          deterministic synthetic data generation
  data/               generated CSVs + magnum.db (git-ignored in a real repo)
  server/             FastAPI service, policies, contracts
  web/                React + TS + Vite client (shop, cart, demand desk, analysis, data)
  scripts/            start.sh and helpers
  docs/MODEL_CARD.md  E9 evaluation and limitations
  docs/DEMO_RUNBOOK.md  the client demonstration script (also §17)
```

### 13.2 How to run

```bash
# 1. generate the dataset (deterministic, ~16s)
python3 generator/generate.py

# 2. build the UI and start the app - one process, one port
scripts/start.sh          # -> http://localhost:8000
```

`start.sh` compiles `web/` into `web/dist` if the bundle is missing or older
than any source file, then starts the API, which serves that bundle at `/`.
There is no second process and no proxy in the path, so what runs locally is
what deploys.

Editing the front end and want hot reload? `npm run dev --prefix web` still
gives you Vite on `:5173` proxying `/api` back to `:8000`. That is a build-time
convenience only — it is not a launch target, it is not in the runbook, and the
demo never touches it.

### 13.3 As-built: the decision API

`server/store.py` builds every feature the policies need once at startup
(2.3 s) and holds it in memory:

| Artefact | Built from | Used by |
|---|---|---|
| `customer_features` (5,000) | orders, order_items | personal score, quantity, reorder |
| `cluster_features` (6) | orders grouped by peer cluster | peer score, cold-start quantity |
| `uplift_table` (5 arms × 6 clusters) | randomised decisions on the **fit split only** | offer ranking |
| latest stock / inbound | last inventory snapshot | availability score, stock action |
| per-store/SKU demand rate | magnum units ÷ demand-index exposure | forecast |
| contact counts (24 h, 7 d) | shown offers | frequency cap |

Cluster cells in the uplift table are shrunk toward the pooled arm effect with
weight `n / (n + 400)`, so a thin cell cannot swing a live decision.

`server/main.py` serves the nine §8.3 endpoints plus health, meta, catalog,
context options, reason vocabulary, network forecast, inventory, an in-memory
event sink, seven analysis endpoints and a read-only data explorer.
`latent_traits` and `ground_truth` are listed by the explorer as **locked** and
return `403` — the only read of `ground_truth` in the entire service is
`analysis.validation()`, which returns five summary rows and no per-decision
score.

### 13.4 As-built: what the analysis says

Offline policy evaluation on the holdout split, by inverse propensity scoring
(propensity is exactly 0.20 because the log randomised uniformly):

| Policy | $ per decision | 95% CI | Attach | Arm mix |
|---|---:|---|---:|---|
| always_reminder | +0.8048 | [+0.756, +0.854] | 25.3% | reminder 100% |
| **eic_greedy_v1** | +0.7628 | [+0.717, +0.809] | 26.6% | none 45%, reminder 34%, voucher 16%, discovery 6% |
| do_nothing | +0.7346 | [+0.688, +0.781] | 22.9% | — |
| uplift_greedy | +0.4584 | [+0.431, +0.486] | 28.9% | voucher 94% |
| always_voucher20 | +0.4409 | [+0.414, +0.467] | 29.1% | voucher 100% |

The headline is the ordering of the last two. `uplift_greedy` maximises the
thing a conversion model optimises and comes second from last on money: it
finds the voucher's real +5.3 pp lift and pays for it out of margin. The V1
policy sits mid-table with 45% of decisions left alone, which is the behaviour
the guardrails were written to produce.

Recovery of ground truth from the randomised log — the property the whole
analysis layer rests on:

| Arm | True uplift | Observed | Error | Inside 95% CI |
|---|---:|---:|---:|---|
| reminder | +1.90 pp | +1.85 pp | 0.05 | yes |
| flavour_discovery | +1.48 pp | +1.90 pp | 0.41 | yes |
| multipack_value | +3.35 pp | +3.35 pp | 0.01 | yes |
| voucher20 | +5.80 pp | +5.26 pp | 0.55 | yes |

Forecast accuracy on 39 weekly backtest origins, 112,320 forecast/actual pairs:

| Metric | Value |
|---|---:|
| p90 coverage (hourly) | 95.9% |
| p10 coverage (hourly) | 100% |
| WAPE, store-day | 0.79 |
| WAPE, SKU-day | 1.05 |
| Pinball loss @ p90 | 0.074 |
| Bias | −0.007 units/hour |

WAPE is quoted per SKU-day rather than per hour on purpose: hourly demand for
one flavour in one store is usually zero or one unit, where a percentage error
measures nothing. p90 coverage is the metric that maps to the decision — the
share of hours the shelf would have survived had it been filled to p90.

Demand drivers, measured on the log rather than asserted:

| Temperature | Attach | Orders |
|---|---:|---:|
| below 32 °F | 13.95% | 7,751 |
| 32–45 °F | 18.56% | 7,834 |
| 45–60 °F | 20.85% | 14,238 |
| 60–72 °F | 30.16% | 15,833 |
| 82–90 °F | 32.79% | 17,106 |
| above 90 °F | 45.74% | 15,107 |

Winter 17.6% → summer 34.8%; snow 11.1% → hot 40.2%; in-game window +1.97 pp.


### 13.5 As-built: the web client

React 19 + TypeScript on Vite 7, Tailwind 4 with the theme expressed as
`@theme` tokens rather than a config file, `lucide-react` for icons and
`recharts` for every chart. No component library — the surface is small enough
that a dozen primitives in `components/ui.tsx` (Card, Section, Badge, Stat,
Toggle, Select, Spinner, ErrorNote, ContribBar) cover it, and they can carry
the theme exactly.

**Theme.** Uber Eats-*inspired*, never Uber-branded: the delivery green
`#06c167`, a near-black ink scale, generous white space, heavy rounded cards,
one accent colour used sparingly for the primary action. No Uber wordmark,
logo, typeface or trade dress appears anywhere. The footer carries the
disclaimer on every screen. Flavour tiles are CSS gradients keyed to the SKU —
no product photography, since there is no licensed imagery to use.

**One shared context.** `ScenarioBar` sits under the header on every screen and
owns the entire scenario: neighborhood, day, hour, season, weather, event,
activity and game day. Every screen reads the same selection, so changing the
weather on the shop screen changes the offer economics in the cart and the
48-hour curve on the demand desk. It also prints what the context resolved to —
temperature, anomaly, heat pull, group bias, demand index — so the demo can
show the input to the model, not just its output.

| Screen | What it shows | Endpoints |
|---|---|---|
| **Shop** | search + suggestion chips, category browse, live ranking-weight strip, product grid, per-card "Why" panel with the full score decomposition and reason codes | `/api/search`, `/api/catalog` |
| **Cart** | cart lines, quantity panel (q\* as 0.40 personal + 0.35 peer + 0.25 occasion, with the occasion read and packs considered), offer panel with the candidate table (lift / cost / EIC), the guardrail grid, and "force a state" chips that drive cap-reached, no-consent, just-ordered and long-gap | `/api/cart/recommend`, `/api/offer/decide` |
| **Demand desk** | five stat cards, the 48-hour p10–p90 band with the p50 line, temperature overlay and game-window shading, stock-action table (gap, transfer qty, dispatch window), network table, reorder-timing card, demand-driver bars | `/api/forecast/store`, `/api/forecast/network`, `/api/stock/actions`, `/api/reorder/timing` |
| **Analysis** | six KPI stats and five tabs — incremental lift (uplift bars with CI error bars, \$-vs-none bars), policy value (IPS bars, arm-mix bars, the callout), forecast accuracy (daily totals, predicted-vs-actual scatter, by-horizon and by-SKU tables), demand drivers, validation | `/api/analysis/*` |
| **Data** | every browsable table straight off SQLite, paginated, sortable, filterable; `latent_traits` and `ground_truth` render as locked chips and the API returns 403 | `/api/data/tables`, `/api/data/table/{name}` |

The analysis screen is the point of the build. Everything else demonstrates
that the decisions can be made; the analysis screen is where the reader can
check whether they were the right ones, and it deliberately shows the result
that is least flattering to the obvious approach — see the policy table in
§13.4.


---

## 14. Change log

Append-only. Every change to the application or the data is recorded here.

| # | Date | Area | Change |
|---|---|---|---|
| 1 | 2026-09-01 | plan | Fixed two swapped list openers in `build_magnum_plan_doc.py` (§4.1↔§5.5, §8.5↔§9.2) that made the script fail with `SyntaxError`; rebuilt `Magnum_Commerce_POC_Implementation_Plan.docx` (284 paragraphs, 30 tables). |
| 2 | 2026-09-01 | docs | Created this build document from the full plan; scaffolded `magnum-commerce-poc/`. |
| 3 | 2026-09-01 | market | **Corrected the market.** The plan set the POC in Hyderabad, but Uber Eats exited India in January 2020 (business sold to Zomato), which makes the §9 sandbox integration plan unusable there and the framing wrong. Rebased on the US — New York + Connecticut metro, USD, ZIP codes, Fahrenheit, US delivery menus, "game day" instead of a cricket fixture. |
| 4 | 2026-09-01 | core | Added `magnum_core/` — `catalog` (10 NY/CT catchments, 26 SKUs), `context` (the one demand model shared by generator and forecast), `profiles` (six peer clusters, six named demo shoppers). |
| 5 | 2026-09-01 | data | Built and calibrated `generator/generate.py`. Four calibration passes: heat coefficient was scaled for °C and saturated the attach logit at 84%; occasion size ran large and pushed the format mix to 51% multipacks; daily shrink floored to zero so waste read as a perfect cold chain; and decisions were only logged when something was bought, inflating voucher uplift to +8.17 pp against a true +5.83 pp. All four fixed — see §5.6. |
| 6 | 2026-09-01 | data | **Extended the simulation window from 12 weeks to 39** (2025-12-02 → 2026-09-01). A June-to-September window never drops below 60 °F, so "attach rises with temperature" was asserted rather than demonstrated: the cold bucket of every driver chart was empty. December to September buys a genuine 14 °F → 93 °F ramp, snow days and a real seasonality curve. Volumes rose with it — 240k sessions, 88k orders, 655k events, 118k decisions. |
| 7 | 2026-09-01 | data | **Added an absolute-temperature term to the attach logit.** The model used only the anomaly against the seasonal norm, so a 38 °F February day at its norm attached exactly like an 88 °F July day at its norm. Added `heat_beta × 2.60 × (heat_pull − 0.62)` alongside the anomaly term; attach now runs 13.9% below freezing to 45.7% above 90 °F. |
| 8 | 2026-09-01 | data | **Rebuilt the forecast table around backtest origins.** Forecasts were generated once at `SIM_END` for the following 48 hours — hours no order can land in — so every accuracy metric came back empty or, worse, read as perfect (p90 coverage 1.000 against zero actuals). Now: a run every 7 days at noon across the window, each looking 48 hours ahead, using only sales that had already happened at that origin. 115,200 rows, 112,320 of them scoreable. |
| 9 | 2026-09-01 | core | Fixed `CURRENCY` (still `INR` from the Hyderabad draft) → `USD`. Lowered `MIN_UPLIFT_PP` from 5 pp to 2 pp — the 5 pp bar was set high enough that only the loss-making voucher ever cleared it, so the policy either discounted or did nothing. Made safety stock demand-scaled (`max(2, ceil(1.25 × busiest hour p50))`) instead of a flat 6 units, which had marked every SKU "at risk" during a snowstorm when nobody was buying ice cream. |
| 10 | 2026-09-01 | server | Added `server/` — `store.py` (startup feature build), `analysis.py` (uplift with CIs, IPS policy evaluation, forecast accuracy, demand drivers, stockouts, ground-truth validation), `main.py` (nine product endpoints, seven analysis endpoints, locked data explorer, Uber adapter stub behind `UBER_ADAPTER_ENABLED=false`). See §13.3–13.4. |
| 11 | 2026-09-01 | web | Built the client — React 19 / TS / Vite 7 / Tailwind 4 / recharts, five screens (Shop, Cart, Demand desk, Analysis, Data explorer) over one shared `ScenarioBar` context. Uber Eats-inspired theme with no Uber marks; flavour tiles are CSS gradients since there is no licensed product imagery. See §13.5. |
| 12 | 2026-09-01 | data | **Fixed the forecast cold-start prior.** The chain-wide fallback rate divided the chain's demand index by the store count while leaving units chain-wide, inflating the prior roughly tenfold; the daily-totals chart spiked to ~700 units at the first backtest origin. Corrected to `global_units / global_idx`. Store-day WAPE 1.038 → 0.786, SKU-day 1.30 → 1.05, bias +0.010 → −0.007 units/hour. |
| 13 | 2026-09-01 | data | Tested trailing-window demand rates against the expanding average, since a 39-week window spans a full season swing. Trailing 21, 42 and 63 days scored 0.819, 0.808 and 0.801 store-day WAPE against 0.786 for expanding — expanding won at every length, because seasonality is already carried by `absolute_index` and a trailing window only throws away sample. Kept the expanding average and recorded the test in `rate_at`'s docstring so it is not re-litigated. |
| 14 | 2026-09-01 | server | Vectorised `analysis.policy_eval()`. Each policy's arm choice depends only on the cluster, so a row-wise `apply` over 22k holdout rows × 5 policies was doing 110k redundant evaluations of a six-entry lookup — the Policy value tab took ~12 s. Replaced with a cluster→arm map; the endpoint now answers in under 11 ms with identical numbers. Added a startup thread that warms all seven analysis panels. |
| 15 | 2026-09-01 | web | UI defects found in browser verification and fixed: the tile gloss pseudo-element painted over the add button and swallowed every click (`pointer-events: none`); recharts series mounted inside a hidden tab never ran their entry animation and rendered as invisible paths (`isAnimationActive={false}` throughout); `main.py` overwrote already-scaled guardrail values so the panel read "0.02 pp"; the quality-gate list read `c.passed`/`c.name` against JSON keys `pass`/`check` and drew ten red crosses over ten passing checks; plus header nav overflow, category chips filtering instead of browsing, a duplicated occasion sentence, a crowded date axis and the demand desk defaulting to the riskiest store rather than the scenario store. |
| 16 | 2026-09-01 | docs | Closed epic E9: wrote `docs/MODEL_CARD.md` (what is modelled, temporal splits and the uniform-propensity log, holdout lift and policy value with CIs, forecast accuracy, ground-truth recovery, guardrails, eight named limitations, data handling, reproduction) and `README.md`. The limitations section states the two things the results should not be read as: the forecast shares the generator's own demand model, so its accuracy measures parameter recovery rather than prediction; and the shipped policy's CI overlaps `always_reminder`, so it is not demonstrably better than always sending the cheapest nudge on this data. |
| 17 | 2026-09-01 | server | **Iteration 2, server.** `POST /api/search` now returns `magnum_live` — the Magnum rail ranked with the text term stood down, so it survives any query and any category — plus `signals`, the context and household terms currently moving the ranking, each with sign and size. New `GET /api/customer/{id}/analytics` (~26 ms) assembles one household's whole picture from `orders`, `order_items`, `offers` and `sessions`. New `POST /api/context/sensitivity` sweeps one context gate while holding the rest, returning a real resolve-and-rank per point so the what-if preview cannot drift from what clicking it produces. `store.py` gained `cluster_features[*].discount_share` and `.cadence_days` so every household number travels with its benchmark. |
| 18 | 2026-09-01 | server | Two corrections found while building the sweep. The customer endpoint returned `NaN`/`inf` for a thin household and failed JSON encoding — added a recursive scrub rather than guarding at forty call sites, since a two-order household is a legitimate case. The sensitivity sweep initially compared points on `demand_index`, which is measured against the neutral case *at the same hour* and therefore returned a perfectly flat line across the time-of-day axis — implicitly claiming the clock does not affect demand. Switched to `absolute_index`; morning now reads 1.15× against dinner 4.06×. |
| 19 | 2026-09-01 | web | **Iteration 2, client.** New `LiveRecoRail` (persistent Magnum rail, diffed against the previous computation for ▲/▼/new, measured latency, live signal list), `WhatIfStrip` (the context response surface as clickable bars), `ChangeFeed` (names the transition that just happened and what it did to demand), and `screens/Customer.tsx` as a sixth tab. Shop became a two-column layout so the rail sits beside the results rather than inside them. Rail rows were re-laid-out after the first pass truncated every product name to "Magnum A…" in a 320 px column. The rail's "top driver" excludes the text family, which is a constant when there is no query and would otherwise win every time. |
| 20 | 2026-09-01 | web | **Cart blank-page defect, fixed.** Adding an item and opening the cart unmounted the whole application: `TypeError: Cannot read properties of null (reading 'predicted_uplift_pp')`. `decide_offer` has *three* outcomes, not two — `suppress` (a guardrail said no), an offer, and `show_recommendation` with `offer=None` (the guardrails permitted contact and no arm earned it). `OfferPanel` keyed on `action === 'suppress'` alone, so the third state took the offer branch and dereferenced null. The panel now models all three: **"No offer worth making"**, with the reason code and the line *"The recommendation still shows; nothing is sent."* Ironically the crashing state was the restraint case the runbook's cue 5 is built on. |
| 21 | 2026-09-01 | web | **`ScreenBoundary` added** (`components/ui.tsx`), wrapping every screen in `App.tsx` keyed by tab. A render error is now contained to its own panel with a *Try again* button instead of blanking the console. Defect 20 was survivable in development and not survivable in front of a client; this makes the failure mode local by construction. |
| 22 | 2026-09-01 | web | **Product photography replaces the painted tiles.** 26 generated 640×640 `.webp` shots, one per SKU, copied in from the sibling `magnum-commerce-poc 2` build to `web/public/products/`. New `components/ProductImage.tsx` renders `/products/{sku}.webp` **over** the old gradient tile, so the tile survives as the loading and failure state rather than a broken-image glyph. Wired into Shop cards, cart lines, the recommendation header and the Magnum rail. Packaging in the shots is unbranded — no trade dress. |
| 23 | 2026-09-01 | web | **Cart's "Offer decision" panel removed.** The candidate table, EIC column, guardrail grid and Force-a-state chips were an analyst's view sitting on a shopper's screen, and they dominated a page whose job is "how many, and why". Replaced by `OfferBanner` — the winning offer only, as the shopper would meet it, attached to the suggestion it applies to. When the policy declines, the banner is simply absent; nothing announces the silence to the shopper. The ranking itself is unchanged server-side. Cart is now a single column. `SUPPRESSION_COPY` moved to `lib/copy.ts` for the screens that still explain refusals. |
| 24 | 2026-09-01 | web | **Analysis tab removed from the UI.** Nav is now Shop / Cart / Customer / Demand desk / Data. `screens/Analysis.tsx` moved to `web/removed/` (out of the `src` tree, so it no longer compiles) rather than deleted. The `/api/analysis/*` endpoints are untouched and still serve every figure; the evidence now lives in [MODEL_CARD.md](docs/MODEL_CARD.md) and §12 of this document. |
| 25 | 2026-09-01 | api+web | **`POST /api/notify` and the per-household nudge.** New `server/notify.py` assembles the artefact a marketer actually ships: one message, one household, with a product, a size, an offer and a send hour. It re-uses three existing policies and re-decides none of them — `reorder_candidate` picks the hour, `recommend_pack([])` picks the size, `decide_offer` picks what rides along. Copy is templated off the lead driver (overdue → due → heat → game → generic), so the headline can never claim something the decision layer did not decide. Surfaced as `NotificationPanel` on the Customer screen, rendered as a phone notification; held sends are shown greyed with the guardrail named, so restraint stays visible. Latency ~0.3 ms. |
| 26 | 2026-09-01 | api | **Measured pairing model.** New `Store._build_pair_table` aggregates the order log into, for every non-Magnum SKU, the flavour lift it carries (share of Magnum flavour in co-purchase baskets ÷ store-wide flavour mix) and its units ratio (mean Magnum units in those baskets ÷ store mean). Held to n ≥ 120 baskets; a category roll-up weights members by basket count. The structure is real and strong: pizza/wings pull **classic 1.63–1.69×** while caramel collapses to **0.18×**; burger/halal/hero pull **caramel 1.44–1.52×**. Size splits the same way — shared dishes carry **1.66×** the bars, single-serve **0.69×**. Nothing is hand-authored; the generator planted it and the aggregation finds it. |
| 27 | 2026-09-01 | api | **Pairing joins the ranking formula.** New `pairing_score()` (log2 of the lift, so half-as-likely and twice-as-likely move the score equally, and 1.0× lands on neutral 0.5) and `build_anchors()`, which resolves cart lines (weight 3× qty) and on-screen results (weight 1) into weighted anchors — the cart outweighs the screen because a basket is a decision and a glance is not. `W_PAIR = 0.20` is live **only** when there is something to pair with; the other five families compress by `(1 − 0.20)` so the weights still sum to 1 and the shift is visible on screen. Anchors are gated on an actual query or category: an unfiltered browse anchors nothing. |
| 28 | 2026-09-01 | api | **`recommend_pack` is pairing-aware.** `units_ratio` multiplies `q_raw` before rounding, and flavour choice becomes `household_share × pairing_lift` — multiplicative, so the household's own mix stays the base and the basket tilts it. A flavour they never buy cannot be promoted out of nowhere. Across the six demo households a pizza switches two of them off their usual flavour and leaves four unchanged. Five new reason codes: `PAIR_STRONG`, `PAIR_WEAK`, `PAIR_SHARED_BASKET`, `PAIR_FLAVOUR_SWITCH`, `PAIR_FLAVOUR_CONFIRMED`. |
| 29 | 2026-09-01 | web | **The rail no longer needs scrolling to reach.** The weights strip and the what-if strip moved *inside* the left column, and the layout became `flex-col` with explicit ordering — the rail is `order-1` when stacked and `order-2` in the xl two-column grid. Rail top went from **y≈3086 to y≈340** at 1440×900, and from 3086 to 743 at phone width. Rail widened 320 → 360 px and product names wrap to two lines instead of truncating. |
| 30 | 2026-09-01 | web | **Score is now visible, not just its winner.** Every rail row carries an always-on stacked contribution bar, and a chevron opens the full table — score, weight, points per family, summing to the match score — plus a plain-English pairing line with its basket count. New `PairingNote` header block shows what the term is keyed to, the per-flavour pull as diverging bars around 1.0×, and the size consequence. |
| 31 | 2026-09-01 | web | **Cart reasoning responds to edits.** New `BasketPairing` (flavour pull, size pull, `q*` before → after → bars, per-anchor contributions) and `BasketChanges`, a running trace that logs every actual movement in occasion size, flavour, units or pack as lines are added and removed — and stays silent when a change moves nothing, so the log records causes rather than flicker. |
| 32 | 2026-09-02 | data | **The pairing effect was an artefact, and was rewritten.** The pizza→classic 1.64× lift measured in row 26 was real in the order log but its *mechanism* was wrong: the generator chose flavour from `flavour_pref[c]` alone and never consulted the basket, so what looked like dish affinity was pack selection wearing a flavour label — group baskets routed to the Mini Classic 6-count, and the only two boxes in the catalogue were classic and almond. Every group-associated dish therefore showed classic/almond inflated and caramel/white crushed to 0.11–0.17×, for reasons that had nothing to do with taste. Fixed at the source rather than patched at the ranker. |
| 33 | 2026-09-02 | data | **Dishes now have character.** `_p()` in `catalog.py` gained `spice` (0–1, capsaicin heat, which drives the cooling response), `richness` (0–1, how heavy the plate already is) and `pairs` (flavours the dish tilts toward, strongest first). Assigned across all 20 non-Magnum SKUs. Fries and onion rings were deliberately left with **no** pairs — a side of fries says nothing about dessert flavour, and they now serve as the null control that proves the rest of the signal is not spurious. |
| 34 | 2026-09-02 | data | **Two pack SKUs added — `MAG-CAR-3` and `MAG-WHT-3`.** Every flavour now has a box. This is the structural half of the row-32 fix: with packs in only two flavours, choosing a *format* silently changed what someone was eating, and any measurement of "which dessert follows this dish" was really measuring "how many people are at the table". `MAG_POPULARITY` re-weighted to 8 SKUs; `analysis.py` unit expansion updated. **Product photography for these two is outstanding** — they fall back to the painted tile, which is the designed failure state, not a broken image. |
| 35 | 2026-09-02 | data | **Flavour is chosen before format.** The order was the bug. `basket_character()` reduces a basket to spice, richness and per-flavour pair weights, weighted by **prominence** (`qty × (0.6 + portion_size)`, then `× (1 + 1.2 × spice)`) rather than by line count — the wings are what the table is eating, the fries are what came with them, and averaging them as equals let one side dish cancel the main course. Personal preference is then tilted by `PAIR_FLAVOUR_TILT = 1.60`, so a dish's first-listed flavour carries 2.6× its baseline odds. Format is decided *afterwards*, and the box is drawn in the flavour already chosen. |
| 36 | 2026-09-02 | data | **Spice, richness and heat now move attach and volume.** `SPICE_ATTACH_BETA = 0.85` (a wings basket and a burger basket of the same size do not attach at the same rate, and the difference is not size), `RICH_ATTACH_BETA = −0.30` (a heavy plate has already done dessert's job), `HEAT_QTY_BETA = 0.90` and `SPICE_QTY_BETA = 0.55` on units. Measured: attach climbs **14.4% → 19.4%** across basket spice, and units per Magnum order climb **1.01 (Dec) → 1.42 (Aug)**. |
| 37 | 2026-09-02 | data | **Heat tilts flavour, not just volume.** New `HEAT_FLAVOUR_TILT` in `catalog.py` (white +1.00, almond +0.55, classic −0.55, caramel −1.00), applied in the generator at `HEAT_FLAVOUR_BETA = 0.55` and mirrored in `context_score` at 0.20. It lives in the catalogue, next to the flavours, because the generator and the live ranker both need it and must not be allowed to disagree — a recommender tuned to a seasonality its own training data does not contain is the easiest way to build a demo nobody can reproduce. Measured winter → summer: **white 12.7% → 30.3%**, **caramel 36.3% → 18.2%**. |
| 38 | 2026-09-02 | api+data | **Discount depth moves against demand, from one shared function.** `policies.discount_depth(base_pct, demand_index)` is imported by the generator rather than reimplemented, so history and live policy cannot drift. Asymmetric on purpose — soft demand is leaned on hard (β 2.2), strong demand is backed away from gently (β 0.85) — because a discount exists to buy volume that was not coming anyway, and even on a busy night there is a tail of price-sensitive shoppers a shallow note still converts. Symmetry would be tidier and would describe a business nobody runs. Capped at the existing `MAX_DISCOUNT_PCT`. Generated voucher depth now spans **12.4% (busy) → 25.0% (dead hour)**; live, the gate reaches **13% → 23%**. Two new reason codes: `OFFER_DEEPER_SLOW_DEMAND`, `OFFER_TRIMMED_BUSY_DEMAND`. The offers table carries the depth actually delivered plus `basket_spice`, `basket_richness`, `basket_pair_flavour`. |
| 39 | 2026-09-02 | api | **Peers turned down; pairing turned up.** `W_PEER` 0.15 → **0.04** and `W_PERSONAL` 0.25 → **0.31**, `W_CONTEXT` 0.15 → **0.18**, `W_AVAIL` 0.10 → **0.12**. "People like you bought this" is the weakest evidence in the stack and the easiest to be wrong about; it now breaks ties and nothing more. `W_PAIR` 0.20 → **0.28**, because a pairing term that only ever reshuffles ties is a term nobody can see working — at 0.28 a measured 1.6× lift beats a moderate personal preference and a 1.2× lift does not, which is the correct outcome. On-screen anchors now decay by rank (`1 / (1 + 1.6i)`): giving row four the same vote as row one let a loosely-matched burger drag the whole rail toward caramel on a search for chips. |
| 40 | 2026-09-02 | web+api | **Plain English everywhere a score is shown.** `FAMILY_LABEL` in `policies.py` is the single definition, emitted on every contribution and consumed by the screens, so the API and the UI cannot drift: *Matches what you searched · What you usually buy · Similar shoppers · Weather and time of day · In stock near you · Goes with your food*. Also retired from the UI: `q*` → "bars before rounding", "Raw q*" → "Bars before rounding", offer arm ids → plain names (`multipack_value` → "Money off a box"), "no arm paid for itself" → "no discount paid for itself here", "the context leads" → "that is the weather". The rail score table headers are now *What moved it / Score / Weight / Points*. |
| 41 | 2026-09-02 | web | **The weights strip shows the weights actually in force.** It read from the static published defaults, so the one moment the system is most obviously reasoning — pairing switching on and the other five families compressing to make room — was the one moment the strip went quiet. It now renders `rail_weights`, live and labelled, and says how many past baskets the pairing is measured across. |
| 42 | 2026-09-02 | web+api | **Search suggestion chips are ranked by the hour, not fixed in a file.** New `_suggestions()` scores each chip from the catalogue's own dish character against heat, group bias, the game window, the hour and the household's top flavour, and every chip carries the reason it is where it is. A shopper who has typed nothing has told the system almost nothing, so what it puts in front of them is the clearest statement it makes about what it thinks is going on — and it has to re-order when any of that moves. Hot Saturday evening leads with *wings · hot out, spicy sells*; a cold Tuesday morning leads with *garlic knots · pairs with classic*. |
| 43 | 2026-09-02 | web | **The offer banner explains its own depth.** A discount that changes size without saying why reads as a bug, or worse, as arbitrary pricing. The banner now names the movement against the base rate in the shopper's own terms — *"Deeper than the usual 20% — orders are running below normal this hour"* / *"Trimmed from the usual 20% — the store is already busy, so we are not paying for orders that were coming anyway."* |
| 44 | 2026-09-02 | ops | **One application, one port.** The build ran two processes — Vite on `:5173` for the UI, FastAPI on `:8000` for everything it depends on — and `:8000` answered `404` at its root because nothing was mounted there. That reads, correctly, like a second broken application sitting next to the real one. `server/main.py` now mounts `web/dist` at `/`, registered **after** every `/api` route so it can never shadow one. `http://localhost:8000` serves the whole product from a single process with no Node running. The Vite entry was removed from `.claude/launch.json`; `npm run dev --prefix web` still works for hot reload while editing but is no longer a launch target and appears nowhere in the demo path. |
| 45 | 2026-09-02 | ops | **`scripts/start.sh` rewritten, and it now detects a stale bundle.** It previously started only the API while the runbook told the presenter to open `:5173` — which nothing was starting. It now rebuilds `web/dist` when any file under `web/src`, `web/public`, `index.html`, `package.json` or `vite.config.ts` is newer than the bundle, then starts the app and prints the one URL. Without that check a `dist` built before the last edit is served silently and looks like working software, which is a far worse failure than a two-second build. `PORT` is overridable for deployment. |
| 46 | 2026-09-02 | api | **CORS narrowed from `*` to the dev origin.** With the UI on the same origin the browser never makes a cross-origin request, so the wildcard was doing nothing except widening the surface of something we intend to deploy. Now defaults to `http://localhost:5173,http://127.0.0.1:5173` and is overridable via `MAGNUM_CORS_ORIGINS`. Verified: the client calls `/api/*` relative (`BASE = ''` in `lib/api.ts`), so the build carries no hardcoded host and deploys behind any origin unchanged. |
| 47 | 2026-09-02 | api | **The offer label was static text sitting next to a live discount.** `OFFER_LIBRARY` carried the literal string *"20% off any Magnum"* while the depth policy had already moved the actual discount to 12.35% for that hour. A shopper reading the card sees the two numbers disagree, and the one they will quote back is the bigger one — that is a customer-service ticket, not a rounding issue. The library entries are now templates (`"{pct}% off any Magnum"`, `"{pct}% off a multipack"`) rendered from the depth the policy just decided. Verified live: busy Friday dinner **12% off any Magnum**, quiet Tuesday lunch **25% off any Magnum**, same household, same basket. |
| 48 | 2026-09-02 | api | **Six households, six headlines.** The `CONTEXT_HEAT` headline was built from temperature and flavour alone, so on a hot evening three of the six demo households composed the identical line — *"93° out — almond weather"* — which quietly contradicts the one claim cue 5 exists to make. Their **sizes and offers already differed**; the headline was simply not carrying the part that differed. It now folds the size in (*"90° out — 2 almond bars, 15 minutes"* / *"an almond box for the house"* / *"one almond bar, 15 minutes"*), the `OVERDUE` headline varies by how overdue (*"Michael, it has been 30 days"* vs *"the freezer is looking empty"* under a week), and the quiet fallback leads on the size rather than a stock phrase. Verified **6 distinct headlines out of 6** in both a hot summer Friday dinner and a cold winter Tuesday lunch. |
| 49 | 2026-09-02 | docs | **Runbook cue 5 and cue 6 re-verified against the running API, not against intent.** Cue 5's table claimed Michael gets *20% off*; the live figure is 12%. It now carries the composed headline per household alongside the size and offer, and states the depth swing explicitly. Cue 6 quoted *"the usual 20%"* in the banner copy, but on the pizza basket the winning arm is the multipack at an 8% base — the banner renders the base of whichever offer won, so the script now reads *the usual 8%* with the measured **10% / \$1.09** quiet and **5% / \$0.54** busy. The closing beat changed from a wrong number (*"Michael's banner becomes 20% off, saving \$0.92"*) to a verified contrast: on the busy hot Saturday, Jessica gets **no banner at all** and Michael's returns. Cart figures re-confirmed live: q\* 4.511 → 5.168 on adding wings, format flip to Mini Classic 6 Count on the second pizza. |
| 50 | 2026-09-02 | data | **Demo households renamed to plain US names.** John Smith · Sarah Miller · David Brown · Emily Davis · Michael Johnson · Jessica Wilson, replacing the previous set. `magnum_core/profiles.py` is the source of record, so a regeneration reproduces them; the existing `customers` table was updated in place rather than paying for an 88k-order regeneration to change six cosmetic strings. Cluster ids, customer ids, blurbs and every behavioural parameter are untouched — this is a display change only. |
| 51 | 2026-09-02 | api+web | **Search suggestions cut from seven chips to two resolved cards.** Seven shortcuts is a menu; two worked answers is a demonstration. Each card now runs the whole pipeline against a basket the shopper has not built yet — `build_anchors` → `recommend_pack` → `decide_offer` — so it carries the dish, **the Magnum it pairs to, the size in bars, the coupon and its depth reason**, plus the scoring terms that put it there. New `SuggestionCards.tsx`; `_suggestions()` rewritten and its scoring split into `_suggest_score()` so every term is kept rather than collapsed into a number. |
| 52 | 2026-09-02 | api | **The household was a rounding term in suggestion ranking; now it is a weight.** Three very different households were shown the same two chips on a hot night — the weather drowned out the person. The pairing bonus rose from 0.30/0.16 to 0.55/0.28 scaled by the household's own flavour share, a `category_shares` term was added (what they actually order), and a peer term reads `clf["sku_shares"]` — **measured off the order log, not read out of a generator parameter**, which would have been ground truth leaking into serving. |
| 53 | 2026-09-02 | api+web | **Every coupon now explains itself, including the ones that do not exist.** New `_coupon_view()` builds one plain-language block — label, depth, saving, why the depth moved, and a season note — consumed by the suggestion cards *and* the cart, so the two cannot describe the same decision differently. When the policy declines, the block renders grey with the reason instead of vanishing: *"No coupon — orders are running 44% above normal for this hour, so every arm costs more in discount than it returns in extra orders."* The cart's `OfferBanner` no longer carries its own hard-coded depth copy. |
| 54 | 2026-09-02 | policy | **The hour moves the size, and until now it did not.** The generator encodes quantity scaling with heat and with the occasion; `recommend_pack` was blind to all three, so a match-day basket at 93 °F recommended exactly the same count as the same basket on a cold Tuesday. That is the serving policy under-fitting its own training data, not a presentation problem. New `Q_HEAT_BETA=0.45`, `Q_GAME_BETA=0.12`, `Q_GROUP_BETA=0.18`, `Q_RAIN_BETA=-0.10` — the generator's own betas at roughly half strength — applied as a named multiplier per term, surfaced as `context_terms` and rendered as its own rows in the cart table between the basket subtotal and the final count. Measured: same basket of 2 pizzas + wings goes **×1.47 on a 93 °F match day → ×0.81 on a cold Tuesday lunch**, six bars in a box down to five singles. Four new reason codes. |
| 55 | 2026-09-02 | policy | **On-site pricing separated from outbound contact.** `decide_offer` gained a `channel` argument. Consent, the frequency cap and the post-purchase window are rules about *interrupting* somebody; they were also gating the price a shopper sees while already holding a basket, which meant a household who ordered four hours ago browsed the entire store at full price for a reason nobody could defend — and made the on-site banner contradict the suggestion card beside it. On-site also pays no contact cost, because no contact is being made. The economic guardrails (min uplift, margin, the 25% cap) still apply on both channels. Verified: push restraint intact (John still held, `POST_PURCHASE_SUPPRESS`), on-site coupons live, and on a peak hot Friday the policy still declines for five of six households on economics alone. |
| 56 | 2026-09-02 | api | **Reorder notifications specialised by condition and by household.** `_drivers` gained `CONTEXT_RAIN`, `CONTEXT_COLD` and `CONTEXT_EVENT` alongside heat and the match window; `_message` gained a headline per lead driver × size; and `CLUSTER_VOICE` gives each pattern family a closing line — with **condition-specific variants**, because a fixed line goes wrong the moment the weather moves under it ("enough for the whole watch party" on a wet Wednesday with no game on is worse than saying nothing). Verified **6 distinct headlines out of 6** in all three of match day, rainy evening and cold Tuesday, with the size and the coupon moving too. |
| 57 | 2026-09-02 | api+web | **New Impact screen, first in the nav — what a month, a quarter and half a year add up to.** New `server/impact.py` + `GET /api/impact`. Every rate is read off 273 days of log; every projection names the baseline it is measured against; every estimate carries the IPS interval it came with. Against **a blanket 20% campaign** (what most retailers actually run): **+0.282 margin per decision, interval 0.200–0.365, does not cross zero** — and it gets there by discounting *less*, attach 1.48pp lower, ~171 fewer discounted orders a month. Against **doing nothing**: +410 Magnum orders a month but the margin interval runs −0.064 to +0.135, so **the screen says the money is not established rather than rounding it up**. Volume and money are never added — they are two views of one lever. The single genuine assumption (what share of measured stock loss better forecasting recovers) is a slider, not a constant, and stock loss is costed at the *average* shelf-hour demand, which understates it because stockouts cluster in busy hours. |
| 58 | 2026-09-02 | api+web | **The coupon moved from the search box to the rail, and the rail was cut to two.** Row 51 put the two resolved cards on the wrong surface: the search area is where a shopper types, the rail is where they look. `magnum_rail` now defaults to **2**, and each rail row carries a coupon block built by the same `_coupon_view()` the cart uses, from the same `decide_offer(..., channel="onsite")` call, so the two surfaces cannot quote different prices. The existing "Why" chevron — the stacked contribution bar, the score table and the pairing sentence — is untouched. Search suggestions went back to a compact chip row (7 chips, no per-card pipeline run), keeping the improved `_suggest_score()` ordering; `SuggestionCards.tsx` deleted. |
| 59 | 2026-09-02 | policy | **Discount depth now moves for the household, not only for the hour.** Every household saw the same depth because `discount_depth` read `demand_index` alone. New `household_depth()` adds two continuous terms read off the order log: how far past their own cadence they have drifted (`due_ratio`, `HH_CADENCE_BETA=0.34`) and how they have historically bought (`discount_response`, `HH_PRICE_BETA=0.30` around a 0.35 midpoint). Continuous rather than banded on purpose — a threshold would price two households a day apart in cadence four points apart, which is not a difference either of them earned. Four new reason codes, each with shopper-facing copy carried on the coupon block as a second line. Measured on one hot match-day Friday: **13.0% · 12.8% · no coupon · no coupon · 16.9% · no coupon** across the six demo households, all six moving again when the hour changes. |
| 60 | 2026-09-02 | web | **Impact screen rebuilt as four charts.** The text-and-tables version buried the argument. Now: stacked margin by horizon with 95% whiskers, a **forest plot** of value per decision against both baselines with a dashed zero line, extra orders split by how they were won, and stockouts/waste avoided — one sentence of caption each and one "how to read these" note at the foot. The forest plot is the point of the redesign: a bar growing out of an axis hides whether an interval crosses zero, a point with its interval drawn through it puts that right where the argument is. Every `<Bar>`/`<Scatter>` carries `isAnimationActive={false}`, matching the rest of the app — the animation never completes in this environment and bars render at zero height without it. |
| 61 | 2026-09-02 | policy+api | **The day of the week reached pricing.** `demand_index` is raw demand over the *same day and hour* under ordinary conditions, so the day cancels by construction and all seven days priced identically — 16.56% on every one of them. New `slot_index` in `context.resolve()` is the neutral multiplier over `_TYPICAL_NEUTRAL = 1.3404`, the order-weighted median neutral multiplier across the whole log; it holds day, hour and season, and is disjoint from `demand_index`, which holds weather, occasion and area activity. `discount_depth()` takes it as a third term through `log2(slot_index)` with `SLOT_BETA_QUIET = 0.30` / `SLOT_BETA_BUSY = 0.10`. Measured at dinner: Monday 1.329 → Saturday 2.017. |
| 62 | 2026-09-02 | api | **The day reached the ranking, measured rather than assumed.** It had been arriving through `group_bias` alone — one step, at Friday. `Store._build_occasion_profile()` measures, per weekday and for the match window, pack share, bars per basket and flavour mix, each as a lift against the same quantity over all 25,280 Magnum orders. `_add_occasion()` combines the day and match slices **in deviations from 1.0** rather than multiplying, which would count their overlap twice, and applies `OCCASION_PULL = 0.5`. Base: pack share 0.4442, 2.5865 bars. Raw day lifts run 0.820 (Monday) → 1.135 (Sunday) on packs; the match window is 1.360 / 1.138. Slices under `MIN_PROFILE_ORDERS = 400` are held at 1.0. |
| 63 | 2026-09-02 | policy | **`MAX_UNITS` 6 → 10 and the pack fitter rewritten twice.** A match-day two-pizza basket computes 8.1 bars, so the old cap flattened every context above six to the same answer while the model underneath was moving. Lifting it exposed the fitter: ranking on leftover alone hands a loose single every tie, so it proposed nine bars at $3.49 with an $11.49 six-pack on the shelf. A full shortfall/overage cost model over-corrected into 12 bars for a target of 9. What shipped is `LEFTOVER_TOLERANCE = 1` — within one bar is an equally good fit, so the cheaper format can win — plus `GROUP_UNITS = 4`, above which unit price outranks flavour in the sort key. |
| 64 | 2026-09-02 | api+web | **Coupon copy rewritten as components, not verdicts.** "Held at the usual 20%" printed next to a 17% coupon, because `depth_code` is decided before `household_depth()` runs. All three variants now describe one component ("The hour trims it from the usual 20% — …"), and the rail carries a breakdown strip — `20% base · hour −37.1% · slot −4.4% · = 10.9%` — which is where two adjacent weekdays that both round to "16%" stay visibly different. |
| 65 | 2026-09-02 | api | **Notification drivers gained snow and the weekday/weekend split.** Snow was reading as "Raining out" because snow carries `rain_in > 0`; `CONTEXT_SNOW` now sits ahead of `CONTEXT_RAIN` with its own headline. `CONTEXT_WEEKEND` / `CONTEXT_WEEKNIGHT` fire off the measured `occasion_pack_lift`, and the body gained a day sentence naming what the day did to the size. |
| 66 | 2026-09-02 | policy | **Rejected and recorded: relaxing `MIN_UPLIFT_PP` on-site.** Adding the slot term pushed the trimmed depth below the 2pp uplift floor on busy hours and coupons collapsed to zero everywhere. `MIN_UPLIFT_ONSITE = 0.005` was tried and reverted: with no contact cost to pay, the zero-discount `flavour_discovery` arm then outscored every voucher on every hour of the week, and the system stopped discounting altogether. The floor stays on both channels with the reasoning in a code comment; `SLOT_BETA_BUSY` was softened to 0.10 instead. |
| 67 | 2026-09-02 | policy | **The measured pack share reached the basket.** `occasion_pack_lift` moved the rail ranking and stopped there — the cart fitter never saw it, so toggling match day on a Monday returned the same six bars. `_pack_for_units()` now takes `pack_bias` and applies it as an **asymmetric** tolerance: on a pack night a box may over-deliver by two and under-deliver by none, on a quiet night the over-delivery is taken back. Symmetric widening was tried first and does the opposite of what it looks like — it lets the cheapest box undershoot a group target and win on unit price, which sent a Friday match basket *down* from nine bars to six. The fitter also costs both the floor and the ceiling pack count, not just the nearest: rounding alone never offers three boxes for a target of seven, so the only format that could hit it exactly was the loose single. `PACK_BIAS_HI = 1.08` / `PACK_BIAS_LO = 0.99` sit in the two gaps of the served distribution (weeknights 0.91–0.95, weekends 1.05–1.07, match windows 1.09–1.25). |
| 68 | 2026-09-02 | api | **Every no-coupon message names its slot.** The suppression copy was byte-identical across two different nights, which reads as a screen that ignored the change even when declining to discount is the right answer. `_coupon_view()` now builds a `when` phrase from the day and window and an `occ_phrase` from the measured occasion terms, and uses them in the label, the `why` and a `slot` line on all three no-coupon branches. Match-day notification headlines gained the day for the same reason — a Monday game and a Saturday game were pushing the same sentence. |
| 69 | 2026-09-02 | web | **Forest plot removed from the Impact screen.** The confidence-interval chart added in row 60 was not legible to the audience the page is for. Impact is now three charts: margin gained by horizon, extra Magnum orders, and stockouts and waste avoided. The significance evidence still exists behind `/api/analysis/policy-eval` and on the Analysis screen; it is no longer the second thing a client sees. |
| 70 | 2026-09-02 | core | **Fix: both forecast endpoints were returning 500.** `peak_window()` was reading `best["slot_index"]` as a required key, but it is called on two different row shapes — the raw horizon from `snapshot_hours()`, which carries it, and the forecast rows `forecast_series()` builds from that horizon, which did not. `/api/forecast` and `/api/forecast/network` both raised `KeyError` and the whole Demand desk screen rendered as an error card. `forecast_series()` now carries `slot_index` through, and `peak_window()` reads it with `.get()` so no future caller can take a screen down over an annotation nothing downstream depends on. |
| 71 | 2026-09-02 | web | **Demand desk simplified; the reorder panel removed from it.** "Reorder timing" duplicated what the Customer screen already covers in more depth, so it and its `/api/reorder` fetch are gone from this screen. The eight-column stock-action table became one **cover bar per SKU** — the bar is what is on the shelf, the marker is what the busiest hour ahead takes at p90 plus safety stock, and the row states the shortfall and the dispatch deadline in words. The subtraction the table used to ask the reader to do themselves is behind a **Show the arithmetic** toggle. The five-column network table became a list sorted by risk, phrased as a lending decision — *"4 SKUs short"* against *"61 units to lend"* — because which store can help is the only question that list exists to answer. |
| 72 | 2026-09-03 | web | **Both Demand desk panels became real bar charts.** The row 71 version drew coverage as a CSS bar with a marker sitting on it; the marker reads as an annotation on the bar rather than as a second quantity, so *what is here* and *what is coming* did not compare at a glance. Both panels are now horizontal grouped `BarChart`s with two bars per row — pale `#a7e8c6` for what is on the shelf, dark for what the peak takes — so the shortfall is the visible difference in length. The demand bar turns `#dc2626` when the row cannot cover itself. `CoverRow` and `StoreRow` are deleted. Store bars are clickable and load that store's 48 hours above. Each `<Bar>` carries its own `fill` even where every rectangle is painted by a `<Cell>`: recharts takes the legend swatch from the Bar, not the Cells, and a Bar without one draws a black key. |
| 73 | 2026-09-03 | api+web | **Impact rebuilt as a four-step argument, funnel first and margin last.** The page used to open on money, which is the conclusion, and never showed the denominator. It now runs *shown → extra orders → stock saved → margin*. `impact.py` gained the counted funnel — `shown`, `converted`, and converted split by whether `discount_pct > 0` — plus `unprompted`, the 6,628 log conversions that happened with **no recommendation on screen**; those are reported beside the chart and never counted as something the system won. It also gained `stockout_episodes`: a contiguous run of stockout hours on one shelf via a `LAG()` window, which is one van trip rather than one hour of pain, so the network-rebalancing claim is counted in moves (101 over six months) instead of hours. `bars_saved` puts availability in units next to the dollars. The stock chart carries an honest caption the data forced: **3,752 of the 3,924 bars saved are spoilage, not refused customers** — the stockout half is a 4px band and the text says so rather than letting the title over-promise. Margin gained is now full width at the bottom and its note names which chart each stacked half came from. |
| 74 | 2026-09-03 | web | **The funnel became one bar, not two.** Shown and bought were drawn side by side, which reads as two independent quantities when bought is a *subset* of shown. The chart is now a single stack per horizon totalling what was shown: full-price green and coupon amber at the bottom, `not_bought` pale on top. Labelling it needed care — at the one-month scale the whole bar is 26px and the converted band is 6px, so a second `position="top"` label landed 12px from the total and collided. The converted label is now custom `content` drawing beside the bar at its own band height with a leader line, and the chart carries a 72px right gutter so it still fits when the grid is three columns wide (measured: label ends at x=433 in a 442px wrapper). It reads `12.4k · 22%` — the count that was asked for plus the share, rounded to a whole percent because the decimal was what pushed it out of the column. |
| 75 | 2026-09-03 | web | **Funnel labels moved above the bar and given words.** Row 74's side label held only while the network-scale slider sat at x1. Move it to x11 and the bars grow, the label stays pinned to the height of the band it measures, and it lands on top of the next bar — at a 422px three-column width the one-month label ran x64-125 straight through the three-month bar. Both figures now sit above the bar as two centred lines, *`56.2k shown`* over *`12.4k bought · 22%`*, so they are named rather than guessed at and they cannot collide: each block is centred on its own category. Measured clear at both 761px and 422px wrappers and at x1 and x11 scale. Two smaller legibility fixes with it: recharts paints legend text in the series colour, which made **Shown, not bought** near-white on white, so the legend now forces ink for the words and lets the swatch carry the colour; and that near-white segment gained a `#b8dfc9` stroke, without which it reads as empty space above the bar rather than as the rest of it. |
| 76 | 2026-09-03 | assets | **The last two product images exist; the shop no longer falls back to a painted tile.** `MAG-CAR-3` and `MAG-WHT-3` were the only two of twenty-eight catalogue rows with no render, so both 404'd and dropped to a gradient placeholder next to twenty-six photographs. `scripts/build_pack_renders.py` derives them from `mag-alm-3.webp`, which is the same **format** — flat presentation box, three bars behind oval windows, one loose bar in front — so the carton, shadow, counter, lens and framing carry over untouched and the pack size stays truthful to the SKU. Only the confection is repainted, by **histogram matching**: each bar pixel is ranked within the source bars' luminance distribution and given the colour at the same percentile in that flavour's own single-bar photo. Ranking rather than rescaling is what keeps the moulded nubs and the occlusion inside the windows, and it is the only version that gets white chocolate right — a linear stretch produced a khaki bar, because the real white bar is skewed light (median luminance 216 in a 150–234 range). Double Caramel needed more than colour: recoloured alone it was the almond box with the nuts recoloured, so it also gets the nut relief median-filtered out of the coating, a tapered variable-width caramel drizzle (constant-width strokes read as piped icing), and an amber cast on the counter garnish so the almonds read as broken toffee. |
| 77 | 2026-09-03 | data | **Every store had the same Magnum mix, so changing store on the demand desk changed nothing.** The generator draws flavour preference from one population-wide distribution and never conditions it on the shelf the order was filled from, which left all ten stores at 25/25/25/25 to within two points - while the screen's own subtitle claimed the mix is fitted per store. `scripts/shape_store_flavours.py` gives each store a flavour identity written as a neighbourhood story (Williamsburg almond, New Haven caramel, Stamford white, Astoria classic) by redrawing the flavour of existing Magnum lines against a per-store affinity. It adds no orders, changes no quantities and never moves a line between pack sizes - a 3-count stays a 3-count - and corrects `unit_price`, `unit_margin` and the order's subtotal, service fee, total and both margin columns by the exact delta, verified: zero orders where the money columns disagree with their own lines. Leading flavours now land at 38-47% against trailing ones at 13-16%. Idempotent by construction: the target flavour is a hash of (seed, store, order, line position) and never reads the line's current value, so a second run re-flavours 0 of 25,383 lines and the row-level digest is unchanged. |
| 78 | 2026-09-03 | data | **The shelf follows the catchment.** Row 77 alone produced a caramel-led store stocked mostly with white chocolate, because inventory is simulated from one network-wide popularity vector rather than per store. The same script now re-allocates the final inventory snapshot across SKUs in proportion to each store's own trailing 28 days of unit sales - the generator's own replenishment rule, computed per store instead of globally. Each store's total on-hand is preserved exactly (network total unchanged at 691 units), so this moves units between SKUs on one shelf rather than conjuring stock, and which store is short still falls out of the simulation - what changes is which SKU it is short of. Astoria now covers its classic and runs short on almond, caramel and both 3-counts, which is the story a classic-led shelf should tell. One performance fix while writing it: the `UPDATE` resolved `(SELECT MAX(snapshot_time) FROM inventory)` inline, turning eighty writes into eighty full scans of a 524k-row table; resolving it once cuts that to a single lookup. |
| 79 | 2026-09-03 | core | **Flavours rode one curve, so the mix was frozen across 48 hours.** `forecast_series()` multiplied a constant per-store-and-SKU rate by the shared demand index, which makes every flavour band a scaled copy of every other - a flavour that is 30% of the shelf at 6am is still 30% of it at the 8pm peak, and the stacked areas never cross. Flavour is chosen at a different moment than the decision to buy ice cream at all. `FLAVOUR_HOUR_SHAPE` gives each flavour its own 24-hour shape (classic flat with a hot-afternoon lift, almond an evening bar, caramel the late one, white daytime and heat-driven) and `FLAVOUR_HEAT_SLOPE` its own response to degrees above 72F. The shapes average ~1.0 over a day, so this re-ranks the mix hour to hour without inflating or deflating a store's total demand. `flavour` is an optional argument - omitted, the function returns the shape the store sells as a whole, and an unknown flavour degrades to 1.0 rather than to zero. |
| 80 | 2026-09-03 | web | **"Where demand comes from" removed from the demand desk.** The context-multiplier bar chart showed weights on a 0-1 axis with no unit and no decision attached to them; the drivers it listed are already named on the scenario bar and in the forecast subtitle. Removing it left the two-column grid with one child, so the grid is gone too and "Across the network" runs full width (460px to 795px measured), which is what a ten-store paired-column chart needed. The `ctxExtra` prop and the App-level state that fed it were only read here and are gone with it. |
| 81 | 2026-09-10 | api+infra | **Deployed to Azure, and it found a real bug on the way.** `get_store()` had no lock, so `_store is None` stayed true for every request arriving during the first build and each one built a complete second store - 579 MB and 5.8 s apiece, measured. Locally that window is 2.5 s with nobody knocking, so it never fired; on App Service the warm-up thread, the platform's startup probe and every health poll each got their own, and the instance climbed to 1,117 MB on B1 and then 2,506 MB on B2 with no build ever winning. It read as "the server is down" but `/` served in 0.4 s throughout - only the API hung, because `health()` called `get_store()` and queued behind a build that never ended. `get_store()` is now double-checked under a lock and `health()` uses a new `store_if_built()` that never triggers a build and answers `loading` until one is ready; twelve concurrent cold-start requests now peak at 431 MB and one store, and production warms in 42.7 s. Three separate startup-path traps had to be cleared first, none of which failed the deployment - it reported success every time while the site returned 503: Oryx extracts the app to `/tmp/<hash>` rather than running it from `/home/site/wwwroot` (absolute path exits 127), Oryx wraps the startup command in single quotes so a command containing them silently loses the antenv `PYTHONPATH` (`No module named uvicorn`), and changing config mid-push restarts the SCM container and kills the deployment. Details in §23.4-23.6. |
---

## 15. Current state (as of iteration 1, 2026-09-01)

Everything below is running and verified end to end. This section is the
snapshot the next iteration is measured against.

### 15.1 What exists

| Layer | State |
|---|---|
| **Data** | 39 weeks (2025-12-02 → 2026-09-01), seed `20260901`, deterministic. 5,000 customers · 10 stores · **28 SKUs** · 65,520 contexts · 239,926 sessions · 655,113 events · **88,255 orders** · 219,329 order items · 524,160 inventory snapshots · 118,313 randomised offer decisions · 5,000 notifications · 153,600 forecast rows. Generator quality gate **10/10**. Regenerated 2026-09-02 with the dish-character, seasonal-flavour and dynamic-depth model (change log 32–38). |
| **Core** | `magnum_core/` — catalog (NY/CT), one shared context/demand model, six peer clusters, six demo shoppers, ranking + quantity + offer + forecast + reorder policies, 40-odd reason codes. |
| **API** | FastAPI, warm in 2.2 s. Nine product endpoints, seven analysis endpoints, a locked data explorer, an Uber adapter stub behind a disabled flag. Every analysis endpoint answers in under 11 ms. |
| **Web** | React 19 / TS / Vite 7 / Tailwind 4 / recharts. Five screens over one shared `ScenarioBar`. `tsc` clean, production build clean. |
| **Docs** | This document, `README.md`, `docs/MODEL_CARD.md`. |

### 15.2 Headline numbers the build can defend

- Attach 13.95% below 32 °F → 45.74% above 90 °F (2.19×); winter 17.6% → summer 34.8%; snow 11.1% → hot 40.2%; in-game window +1.97 pp.
- Ground truth recovered from the randomised log to within 0.55 pp, all four arms inside their 95% CI.
- Forecast: 95.9% p90 coverage, 0.79 store-day WAPE, −0.007 units/hour bias, on 112,320 backtest pairs across 39 weekly origins.
- Policy value: `eic_greedy_v1` +\$0.7628/decision with 45% restraint, against `uplift_greedy` at +\$0.4584 — the ordering the whole build exists to show.

### 15.3 The three gaps this iteration closes

Reviewing the build as a **client-facing demonstration** rather than as an
engineering deliverable, three things are missing. None of them are defects;
all three are the difference between "the system works" and "the client can
see it working".

1. **Magnum recommendations are not continuously visible.** The Magnum block on
   the shop screen only appears when Magnum SKUs happen to survive the text
   query and category filter. Search "wings", or browse Drinks, and the entire
   Magnum surface disappears — which is exactly the moment a Magnum stakeholder
   most wants to see what the system would place. The recommendation must be a
   **persistent live rail**, computed on every keystroke-to-search, category
   change, context change and profile change, and visible regardless of what
   the shopper is looking at.

2. **Selecting a customer changes the decisions but shows nothing about the
   customer.** The profile picker drives personal ranking weight, quantity and
   offer eligibility, but the reviewer cannot see *who* that person is: their
   history, cadence, flavour mix, how they compare to their peer cluster, what
   offers they have been shown and whether they converted, or when they are due
   next. Every one of those features already exists in `store.py` and in the log
   — none of it is surfaced.

3. **Context changes are applied silently.** Changing the weather from hot to
   snow re-ranks the entire catalogue, moves the offer economics and reshapes
   the 48-hour curve — but the screen simply redraws. Nothing says *what moved,
   by how much, and because of which term*. For a demonstration, the delta is
   the product.

---

## 16. Iteration 2 — live recommendations, customer analytics, visible reactivity

**Status: shipped and verified in the browser.** §16.4 records what it does as built.

Scope agreed with the client-demo requirement: the application is a
presentation instrument as well as a reference build, so the capability must be
**legible while it happens**, not reconstructable afterwards from the analysis
tab.

### 16.1 Server changes

| Endpoint | Status | What it does |
|---|---|---|
| `POST /api/search` | extended | Adds `magnum_live` — the top Magnum picks ranked in the current context **independently of the query and category filter**, so the rail never goes empty. Adds `signals`: the context terms currently moving the ranking, each with its weight and direction. |
| `GET /api/customer/{id}/analytics` | new | Everything the log knows about one household: lifetime value and order counts, attach rate against the peer-cluster benchmark, cadence and due-ratio, flavour and category mix beside the cluster's mix, hour-of-day and day-of-week histograms, a monthly attach and spend trend, the full offer history with arm, conversion and discount, the last ten orders, and current eligibility state (consent, contacts in 24 h / 7 d, suppression window). |
| `POST /api/context/sensitivity` | new | A what-if surface: holding everything else fixed, the resolved demand index, forecast peak and top Magnum pick under **every** weather option and **every** time window. This is what makes reactivity demonstrable rather than assertable — the client can see the response curve, not just one point on it. |

`latent_traits` and `ground_truth` remain unreachable. The customer analytics
endpoint reads `orders`, `order_items`, `offers` and `sessions` only — the same
tables the application already reads — and returns aggregates plus the
household's own rows, never another household's.

### 16.2 Web changes

| Component | Status | What it does |
|---|---|---|
| `components/LiveRecoRail.tsx` | new | A persistent Magnum rail beside the results. Recomputes on every query, category, context and profile change; each entry carries its rank movement (▲/▼/new) against the previous computation, its score delta, and the single term that moved it most. Headed by a live pulse showing the recompute latency. |
| `components/WhatChanged.tsx` | new | A running feed of the last context changes — "weather hot → snow: demand index 1.44 → 0.71, Classic ▼3, Almond ▲1" — so the client sees cause and effect in one line. |
| `screens/Customer.tsx` | new | Sixth tab. The full household analytics view: identity and consent, lifetime stats against cluster benchmarks, the due-next gauge, flavour and category mix versus peers, order and attach trend, hour/day histograms, offer history with conversion, and the live decision state for that customer right now. |
| `screens/Shop.tsx` | changed | Two-column layout with the rail; a what-if weather strip driven by `/api/context/sensitivity` that shows the demand index and top pick for each weather **before** you click it. |
| `App.tsx` | changed | Sixth nav entry; the selected profile becomes a clickable chip that opens the customer view. |

### 16.3 What this must not become

Three constraints held from the original plan, restated because a demo surface
is exactly where they usually break:

- **No new claims.** The rail shows the ranker's existing score decomposition.
  The what-if strip calls the same `context.resolve` the application already
  uses. Nothing here introduces a number that the analysis tab cannot audit.
- **No held-out data.** The customer view reads the log, not `latent_traits`.
  A household's propensities are not shown, because the application does not
  know them.
- **No fake liveness.** Latency shown is measured, not simulated. If a
  recompute takes 40 ms the rail says 40 ms.

### 16.4 As built

**`POST /api/search` → `magnum_live` + `signals`.** The rail calls
`rank_products` a second time with the text term stood down and the category
pinned to `magnum`. It therefore survives any query and any category: searching
*wings* returns exactly one product and the rail still carries all six Magnum
SKUs ranked for the selected household in the current weather. Because the rail
has no query, "top driver" is computed across the *discriminating* families
only — personal, peer, context, availability — since the text term would
otherwise be a constant that wins every time.

**`GET /api/customer/{id}/analytics`.** ~26 ms. Reads `orders`, `order_items`,
`offers` and `sessions` for one customer. `store.py` gained
`cluster_features[*].discount_share` and `.cadence_days` so every household
number has a benchmark to sit beside — an attach rate without its cluster's is
not a fact a reviewer can use. NaN and inf are scrubbed on the way out:
a household with two orders is a legitimate case, and an empty pandas mean is
not valid JSON.

**`POST /api/context/sensitivity`.** ~0.3 ms for a five-point sweep. One gate is
swept while everything else is held; each point is a real `resolve` + `rank`,
so the preview cannot drift from what clicking it produces. It compares points
on **`absolute_index`, not `demand_index`** — `demand_index` is measured against
the neutral case *at the same hour*, so sweeping the time window on it returns a
flat line and implicitly claims the clock does not matter. Measured on the live
build, Astoria, summer Friday evening: weather hot 2.63× → snow 1.16×
(−56%); time morning 1.15× → dinner 4.06×; day Tuesday 1.84× → Saturday 2.89×.

**Web.** `LiveRecoRail` diffs each recomputation against the previous one and
shows ▲/▼/new per SKU plus the measured server latency, re-keyed so the pulse
fires on real recomputes and not on idle re-renders. `WhatIfStrip` renders the
sweep as a clickable bar chart. `ChangeFeed` (a hook plus a one-line banner
under the scenario bar) names the transition that just happened —
"Weather hot → snow: demand 2.63× → 1.16× (−56%), 93 °F → 67 °F".
`screens/Customer.tsx` is the sixth tab.

What did **not** change: no new estimate, no new claim, no read of a held-out
table. Every number on the new surfaces comes from a path the analysis tab can
already audit.

---

## 17. Client demonstration runbook

Also kept as a standalone file at `docs/DEMO_RUNBOOK.md` so it can be handed to
a presenter without the rest of this document.

Written to be read aloud. Roughly 20 minutes with questions; each act names the
screen, the exact clicks, and the sentence that carries it. The numbers quoted
are live in the build — if one of them has moved, the build is telling the
truth and the script is stale, not the other way round.

**Before you start.** Run `scripts/start.sh`, open `http://localhost:8000`, and
leave it on the default scenario: **Astoria, NY · Friday 5–7 PM · summer · hot ·
game day on · John Smith**. Say the disclaimer once, in your own words: this
is an Uber Eats-*inspired* reference build, not an Uber product, and every row
of data is synthetic.

### Act 1 — The problem, in one screen (2 min) · *Shop*

> "This is a quick-commerce storefront. What makes it different is that nothing
> on it is a static merchandising rule."

Point at the scenario bar: 93 °F, hot, game day live, demand ×1.44 against a
normal Friday. Point at the **Ranking this list** strip: text 35%, personal
25%, peer 15%, context 15%, availability 10% — the weights are on the screen,
not in a slide.

Click **Why** on Magnum Almond Bar. The score decomposes term by term with
reason codes. *"Every recommendation in this system can be interrogated. If it
cannot be explained it does not ship."*

### Act 2 — The recommendation never goes away (3 min) · *Shop*

This is the act that answers "what does Magnum actually get out of it".

1. Point at **Live Magnum picks** on the right. Note the latency chip — that is
   measured server time, not a spinner.
2. Click the category chip **Drinks**. The grid becomes soda and iced tea. The
   rail does not move.
3. Type **wings** and search. One result: Buffalo Wings. *The rail is still
   there, still ranked, still for this household.*

> "The moment a shopper is looking at wings is the moment Magnum most wants to
> know what the system would place. So the rail is ranked independently of the
> search box — it is always answering, whatever the shopper is doing."

Point at **What is moving this list** beneath it: temperature +0.94, vs
seasonal norm +0.85, weather +0.32, household flavour *almond*. Those are the
live terms, with signs.

### Act 3 — Change the world, watch it react (4 min) · *Shop*

Scroll to **If the world changed right now**.

> "One resolved context tells you what the system does. It does not prove the
> system is reacting. So here is the whole curve."

1. **Weather.** Five bars: hot 2.63× down to snow 1.16×. Click **Snow**.
   - The banner under the scenario bar names it: *Weather hot → snow, demand
     2.63× → 1.16× (−56%), 93 °F → 67 °F.*
   - The signal list flips sign: weather −0.42, seasonal norm −0.46.
   - The rail re-ranks and the arrows show what moved.
2. Click **Time of day** → morning 1.15× versus dinner 4.06×. Click **Day** →
   Tuesday 1.84× versus Saturday 2.89×.
3. Put it back on **Hot**.

> "Nothing here is a demo animation. Each bar is the real resolve-and-rank path
> the live screen uses, so what you preview is exactly what you get."

### Act 4 — Who is this shopper? (4 min) · *Customer*

Click **View analytics** in the header.

- **Identity and consent** first, deliberately: marketing consent, personalisation,
  contacts 0/1 in 24 h and 0/3 in 7 d, and whether they are contactable right now.
  *"The first thing the system shows about a customer is what it is allowed to do."*
- **Lifetime**: 33 orders, \$918, 18.2% attach against a 24.1% cluster.
- **Against the cluster**: green is the household, grey is the peer group.
  *"A household number without its benchmark is not a fact anyone can act on."*
- **When are they due**: the due-ratio gauge. John bought yesterday, so it
  reads 0.01× — *early* — and the reorder nudge stands down. Switch the
  selector to another household to show the gauge move.
- **Month by month**: the attach line climbing from winter into August. *"That
  is the entire thesis, one customer at a time."*
- **Offers this household was shown**: 41 decisions, 32 eligible, 27 shown,
  6 converted. Read the caption — the arms were randomised, so these are
  unbiased but tiny-sample; the pooled numbers are in Act 6.
- Close on the padlock: `latent_traits` is never read here.

### Act 5 — The commercial decision (3 min) · *Cart*

Add two Magnum bars, open **Cart**.

- **Quantity**: q\* = 0.40 personal + 0.35 peer + 0.25 occasion, with the
  occasion read spelled out.
- **Offer**: the candidate table with predicted lift, cost and expected
  incremental contribution for every arm — including the ones that lost.
- Use the **Force a state** chips: *Cap reached*, *No consent*, *Just ordered*.
  Each one produces a refusal with a named reason code.

> "Most of the time the right answer is to send nothing. Forty-five percent of
> the time, this policy does exactly that."

### Act 6 — Did any of it work? (5 min) · *Analysis*

This is where you hand the room the argument, including the parts that do not
flatter the approach.

1. **Incremental lift.** All four nudges lift attach. The 20% voucher lifts
   most: +5.89 pp. Then the dollars column: it loses \$0.2570 per decision.
2. **Policy value.** Offline evaluation by inverse propensity scoring:
   `eic_greedy_v1` +\$0.7628, `do_nothing` +\$0.7346, `uplift_greedy` +\$0.4584.
   > "`uplift_greedy` maximises exactly what a conversion model optimises. It
   > correctly finds the voucher's real lift, and it finishes fourth of five,
   > below doing nothing, because it pays for that lift out of margin. That is
   > the single most useful result in this build."
   Be straight about the honest caveat: the shipped policy's confidence
   interval overlaps `always_reminder`. On this data it is not *proven* better
   than always sending the cheapest nudge; what it buys is restraint.
3. **Forecast accuracy.** 112,320 backtest pairs across 39 weekly origins:
   95.9% p90 coverage, 0.79 store-day WAPE, −0.007 units/hour bias. Explain why
   hourly WAPE is not quoted as the headline: hourly demand for one flavour in
   one store is 0 or 1 units.
4. **Demand drivers.** Attach 13.95% below freezing → 45.74% above 90 °F.
   *Demonstrated on 88,161 orders, not asserted.*
5. **Validation.** True versus recovered uplift for all four arms, max error
   0.55 pp, every arm inside its interval; ten of ten generator quality checks
   green.

### Act 7 — Show your homework (2 min) · *Demand desk*, then *Data*

- **Demand desk**: the 48-hour p10–p90 band with the temperature overlay and the
  shaded game window, the stock-action table, the transfer window.
- **Data**: every table the application reads, browsable. Then point at the two
  greyed chips — `latent_traits` and `ground_truth` return `403`.
  > "The generator knows the true answer. The application is not allowed to see
  > it. That is the only reason the validation panel means anything."

### Closing

> "Three claims, and each one has a screen behind it. Context changes demand and
> the system reacts to it live. The system knows the household and can show you
> what it knows and what it is allowed to do with it. And it can tell you which
> of its own ideas make money — including the one that does not."

### Questions you should expect, and the honest answer

| Question | Answer |
|---|---|
| "Is this real data?" | No. Every row is synthetic, deterministically generated from seed 20260901. That is stated on every screen. |
| "How good is the forecast really?" | On this data, very. But it shares the generator's demand model, so it measures parameter recovery, not prediction. Expect materially worse on live data. `docs/MODEL_CARD.md` §5 says so in writing. |
| "Can you plug this into Uber Eats?" | Not in this build. There is an adapter stub behind a flag that is off; nothing here calls an external service, and no Uber credentials or trade dress exist in the repo. |
| "Why does the shipped policy not beat always-reminder?" | On this sample it does not, and we say so. Its case is restraint — 45% of decisions left alone — plus guardrails that a fixed always-send policy has no way to express. |
| "What about the customer's privacy?" | Consent is the first thing on the customer screen and a hard block in the offer policy. The evaluation tables are unreachable from the application and return 403 in the explorer. |


---

## 18. Iteration 3 — the data rewrite (2026-09-02)

### 18.1 Why the data had to change, not the ranker

Iteration 2 shipped a pairing term backed by a measured 1.64× pizza→classic
flavour lift. The lift was real. Its cause was not what the screen said it was.

The generator picked a Magnum flavour from `flavour_pref[c]` — the household's
own preference vector — and consulted the basket at no point. What actually
happened was this: a pizza implies a group, a group implies a box, and the
catalogue only sold boxes in two flavours. So classic and almond rose in every
group basket and caramel and white collapsed to 0.11–0.17×, for reasons that had
nothing to do with what anybody was eating. A dish-affinity story told over that
data would have been a true number attached to a false explanation, which is the
one failure mode a client demo cannot survive being asked about.

Patching the ranker would have hidden it. The fix is in the generator, and the
evidence is now downstream of a mechanism that would produce it in the world.

### 18.2 What a dish now does to the dessert behind it

Three fields on every non-Magnum SKU, in `magnum_core/catalog.py`:

| Field | Range | What it drives |
|---|---|---|
| `spice` | 0–1 | Capsaicin heat drives the cooling response — attach rate and units |
| `richness` | 0–1 | A heavy plate has already done dessert's job — suppresses both |
| `pairs` | flavours, strongest first | Tilts *which* bar, never decides it |

A basket is reduced to those three numbers by **prominence**, not by line count:
`qty × (0.6 + portion_size)`, then `× (1 + 1.2 × spice)` for the flavour vote.
The wings are what the table is eating; the fries are what came with them.
Averaging them as equals let one side dish cancel the main course.

**Fries and onion rings carry no pairs at all.** A side of fries genuinely says
nothing about dessert flavour, and they now function as the null control: if the
pairing signal were an artefact of basket size, they would show lift. They sit at
0.95–1.05× across all four flavours.

### 18.3 The coefficients, and what they buy

All of these live in `generator/generate.py` as named constants, together, so the
effect sizes can be argued with rather than reverse-engineered out of a logit.

| Constant | Value | Effect |
|---|---:|---|
| `SPICE_ATTACH_BETA` | 0.85 | logit points at maximum spice |
| `RICH_ATTACH_BETA` | −0.30 | heavy plate suppresses attach |
| `SPICE_QTY_BETA` | 0.55 | extra units at maximum spice |
| `RICH_QTY_BETA` | −0.35 | heavy plate suppresses volume |
| `HEAT_QTY_BETA` | 0.90 | nobody buys one bar for the house in August |
| `PAIR_FLAVOUR_TILT` | 1.60 | first-listed flavour carries 2.6× baseline odds |
| `HEAT_FLAVOUR_BETA` | 0.55 | applied against `catalog.HEAT_FLAVOUR_TILT` |

`HEAT_FLAVOUR_TILT` (white +1.00, almond +0.55, classic −0.55, caramel −1.00)
lives in the **catalogue**, not the generator, because the live ranker needs the
same numbers. A recommender tuned to a seasonality its own training data does not
contain is the easiest way to build a demo that cannot be reproduced.

### 18.4 Measured on the regenerated 88,255 orders

Dish → flavour lift, against the store-wide flavour mix:

| Dish | almond | caramel | classic | white | encoded affinity |
|---|---:|---:|---:|---:|---|
| Bacon Cheeseburger | 0.79× | **1.55×** | 0.73× | 0.97× | caramel, white |
| Italian Hero | 0.76× | **1.48×** | 1.22× | 0.54× | caramel, classic |
| Chicken Over Rice | 0.73× | **1.31×** | 0.69× | **1.31×** | white, caramel |
| Large Cheese Pizza | 1.20× | 0.66× | **1.29×** | 0.81× | classic, almond |
| Large Pepperoni Pizza | 1.19× | 0.64× | **1.34×** | 0.79× | classic, almond |
| Buffalo Wings | **1.27×** | 0.60× | 1.08× | 1.03× | white, almond |
| Tortilla Chips & Salsa | **1.41×** | 0.85× | 1.07× | 0.66× | white, almond |
| Mozzarella Sticks | 0.90× | **1.22×** | 1.10× | 0.80× | caramel, classic |
| *French Fries* | *0.95×* | *1.05×* | *0.96×* | *1.04×* | *none — control* |
| *Onion Rings* | *1.03×* | *1.03×* | *1.04×* | *0.89×* | *none — control* |

Note wings and chips: both list **white** first, and both land on **almond**.
That is the model working, not failing. The dish tilts the odds; the household's
own eight-month history still outranks it, and almond simply starts from a higher
base. It is the single best line in the demo — *the plate moves it, the person
still decides.*

Seasonal flavour mix, winter → summer:

| | almond | caramel | classic | white |
|---|---:|---:|---:|---:|
| Winter | 19.0% | 36.3% | 32.0% | 12.7% |
| Summer | 28.5% | 18.2% | 23.0% | 30.3% |
| **Δ** | **+9.5pp** | **−18.1pp** | **−9.0pp** | **+17.6pp** |

Volume and attach:

- Units per Magnum order, December → August: **1.01 → 1.42**
- Attach rate across basket spice (0.0 → 0.4): **14.4% → 19.4%**
- Overall Magnum attach: **28.6%**, generator quality gate **10/10**

### 18.5 Discount depth

`policies.discount_depth(base_pct, demand_index)` is the only implementation, and
the generator imports it rather than carrying a copy. A generator and a policy
that each own a pricing rule will drift, and the first symptom is a demo whose
numbers cannot be traced back to the data they were fitted on.

It is **asymmetric on purpose**: soft demand is leaned on hard (β 2.2), strong
demand is backed away from gently (β 0.85). A discount exists to buy volume that
was not coming anyway, so a dead hour is worth paying for; but even on a busy
night there is a tail of price-sensitive shoppers a shallow note still converts.
Symmetry would be tidier and would describe a business nobody runs. The result is
capped at the existing `MAX_DISCOUNT_PCT = 0.25` guardrail, so no generated
decision is one the live policy would refuse to make.

| Band | n | mean depth | conversion |
|---|---:|---:|---:|
| Very slow hour | 5,442 | 24.9% | 16.9% |
| Slow | 2,736 | 20.6% | 21.7% |
| Normal | 7,108 | 17.5% | 25.6% |
| Busy hour | 5,823 | 13.5% | 30.0% |

Conversion falls as depth rises because busy hours convert better *anyway* — the
table is confounded by design and is not a causal claim. The randomised arm
assignment is what the uplift estimates rest on; this table only shows the policy
moving. Live, the context gate reaches 13% → 23%.

### 18.6 Serving-side consequences

- **Peers turned down.** `W_PEER` 0.15 → 0.04. "People like you bought this" is
  the weakest evidence in the stack and the easiest to be wrong about. It breaks
  ties and nothing more. The weight went to personal (0.31), context (0.18) and
  availability (0.12).
- **Pairing turned up.** `W_PAIR` 0.20 → 0.28. A pairing term that only reshuffles
  ties is a term nobody can see working. At 0.28 a measured 1.6× lift beats a
  moderate personal preference and a 1.2× lift does not.
- **Anchors decay by rank** (`1 / (1 + 1.6i)`). Giving row four the same vote as
  row one let a loosely-matched burger drag the rail toward caramel on a search
  for chips and salsa.
- **`context_score` now discriminates between Magnums.** It previously scored
  every Magnum identically on heat, so temperature could raise the whole rail and
  never reorder it. It now applies the shared `HEAT_FLAVOUR_TILT` at 0.20 and
  lifts boxes on hot, group-shaped hours.

Same household, same store, weather changed:

| Context | Rail order |
|---|---|
| Hot summer evening | Almond 3ct → Mini Classic 6ct → Almond Bar → Caramel 3ct |
| Cold winter morning | Mini Classic 6ct → Caramel 3ct → Classic Bar → Almond 3ct |

Same household, same hour, browsing changed:

| Looking at | Top of rail |
|---|---|
| nothing | Almond Bars, 3 Count |
| pizza | **Mini Classic Bars, 6 Count** |
| wings | Almond Bars, 3 Count |
| burger | **Double Caramel Bars, 3 Count** |

### 18.7 Language

Every score family now carries a plain label from a single definition
(`policies.FAMILY_LABEL`), emitted by the API and consumed by the screens so the
two cannot drift:

> Matches what you searched · What you usually buy · Similar shoppers ·
> Weather and time of day · In stock near you · Goes with your food

Also retired from the UI: `q*` → "bars before rounding"; offer arm ids →
plain names (`multipack_value` → "Money off a box"); "no arm paid for itself" →
"no discount paid for itself here"; "the context leads" → "that is the weather".
Rail score table headers are now *What moved it / Score / Weight / Points*.

### 18.8 Known gap — closed 2026-09-03

`MAG-CAR-3` and `MAG-WHT-3` had no product photography and rendered on the
painted gradient tile. That tile is the designed loading-and-failure state rather
than a broken image, but two of them read as unfinished next to 26 photographed
SKUs. Both now exist, built by `scripts/build_pack_renders.py` from
`mag-alm-3.webp` — the same three-bars-in-a-windowed-box format, so the pack size
on the tile matches the SKU — with only the confection repainted. See change-log
row 76 for how, and for the two failures that shaped it: a linear tone stretch
turns white chocolate khaki, and a recolour alone leaves Double Caramel
indistinguishable from the almond box.

All 28 catalogue rows now have a 640×640 render; the shop was checked with every
image decoded (`naturalWidth > 0`), so nothing falls back to the placeholder.

---

## 19. Deployment shape (2026-09-02)

The build is a **single process serving a single origin**, which is the form it
should be deployed in.

```
                    ┌──────────────────────────────────┐
  browser  ────────▶│  uvicorn  server.main:app  :8000 │
                    │                                  │
                    │  /api/*      decision API        │
                    │  /products/* product imagery     │
                    │  /assets/*   compiled JS + CSS   │
                    │  /           web/dist/index.html │
                    └───────────────┬──────────────────┘
                                    │
                            data/magnum.db (read-only)
```

**Why one process rather than two.** A separate front-end host means a second
deploy target, a CORS policy that has to stay correct, an environment variable
carrying the API's address into the bundle, and a class of failure where the two
halves are on different versions. None of that buys anything here. The client is
216 kB gzipped of static assets; the API is already running and can serve them.

**What makes it portable:**

- `lib/api.ts` sets `BASE = ''`. Every call is relative, so the bundle contains
  no hostname and works behind any origin, path prefix or reverse proxy without
  a rebuild.
- `PORT` is read from the environment by `scripts/start.sh`.
- `MAGNUM_CORS_ORIGINS` scopes CORS; it is only needed if someone runs the Vite
  dev server against a remote API.
- The static mount is registered last, so adding an `/api` route never requires
  touching it.

**Resolved when it was deployed (2026-09-10):**

| Item | How it landed |
|---|---|
| `data/magnum.db` is 325 MB | Shipped in the deployment package. It is 59 MB gzipped, so the zip is 58 MB — well inside what a zip deploy handles, and it removes the need to run the generator on the host. Regenerating at build time stays the alternative if the artifact ever has to shrink; `SEED = 20260901` makes both routes byte-identical. |
| No `Dockerfile` | Not needed. App Service's Python 3.11 runtime plus Oryx installs `requirements.txt` and runs `scripts/azure_startup.sh`. A container would add a registry and an image push for no gain on a single-process app. |
| SQLite, read-only | Unchanged and still correct. It is why one instance is the right shape: there is no shared write path to coordinate. |
| Bundle is one 717 kB chunk | Still true, still deferred. It costs first paint, not correctness. |

**Sizing, measured rather than guessed.** `store.py` builds every feature table
into memory at startup; a cold start peaks at **615 MB RSS** and takes **6.0 s**
(2.8 s to build the store, 3.1 s to warm the seven analysis panels). That is what
picks **B1** (1.75 GB) over the free tier, and what makes the startup command
pin `--workers 1`: workers do not share that memory, so a second one doubles the
footprint to solve a concurrency problem this read-only workload does not have.
The warm-up runs on a background thread, so the port binds immediately and the
platform's start probe is never waiting on it.

---

## 20. Iteration 4 — per-person dynamism and the impact case (2026-09-02)

The brief for this pass was that a client should be able to change *anything* —
the household, the weather, the hour, what is in the basket — and watch the
recommendation, the size, the flavour and the discount all move with it, with a
sentence attached to every movement. Plus a business case at the top that
survives being argued with.

Four things were wrong before this pass and two of them were real defects rather
than missing features.

### 20.1 The serving policy was blind to the hour

The generator scales quantity with heat (`HEAT_QTY_BETA = 0.90`) and with how
many people the basket reads as. `recommend_pack` used none of it. The
consequence was easy to miss and hard to defend once seen: a basket of two
pizzas and a portion of wings recommended **exactly the same count on a 93 °F
match-day Friday as on a cold Tuesday lunch**, because the only context the size
model saw was the basket itself.

This is the policy under-fitting its own training data, not a demo problem. Four
named multipliers now sit between the weighted average and the rounding, at
roughly half the generator's betas — the log is one store network's worth of
evidence and the policy should lean on it, not lunge:

| Term | Beta | What it reads |
|---|---|---|
| `Q_HEAT_BETA` | +0.45 | `heat_pull` against a 0.62 neutral |
| `Q_GAME_BETA` | +0.12 | the match window being open |
| `Q_GROUP_BETA` | +0.18 | `group_bias`, how shareable this hour is trading |
| `Q_RAIN_BETA` | −0.10 | measurable rain — wet nights go smaller and more solo |

Measured, same basket and same household, nothing else touched:

| Condition | Multiplier | q\* | Answer |
|---|---|---|---|
| Match day, 93 °F | ×1.47 | 8.19 | Mini Classic Bars, 6 Count — 6 bars |
| Rainy Wednesday evening | ×0.83 | 4.61 | Classic Milk Chocolate Bar — 5 bars |
| Cold Tuesday lunch | ×0.81 | 4.50 | Classic Milk Chocolate Bar — 5 bars |

Each term is returned as `context_terms` and rendered as its own row in the cart
table, with the sentence that justifies it, between the basket subtotal and the
final count. Nothing moves silently.

### 20.2 Contact guardrails were pricing the store

`decide_offer` applied consent, the frequency cap and the post-purchase window to
every call. Those three rules exist to stop us **interrupting** somebody. They
were also gating the price a shopper sees while already on the page holding a
basket — so a household who ordered four hours ago browsed the entire store at
full price for a reason nobody could defend, and the on-site banner contradicted
the suggestion card sitting next to it.

`channel` now separates the two. On-site skips the contact rules and pays no
contact cost, because no contact is being made. The economic guardrails — minimum
uplift, margin, the 25% cap — apply on both, because those are rules about the
money. Verified: push restraint intact (John Smith still held on
`POST_PURCHASE_SUPPRESS`), and on a peak hot Friday the on-site policy still
declines for **five of six households on economics alone**.

### 20.3 The household had to start mattering

The pairing bonus was 0.30 against a weather term worth 0.46, so three very
different households saw the same shortcuts in the same order on a hot night.
Personal weight roughly doubled and now scales with the household's own flavour
share; a `category_shares` term was added; and the peer term reads
`clf["sku_shares"]` — **measured off the order log, not read out of a generator
parameter**, which would have been ground truth leaking into serving.

The first attempt at showing this resolved the two top shortcuts all the way to a
size and a coupon and put them under the search box. That was the right idea on
the wrong surface, and §21 moves it. The scoring work survived the move.

### 20.4 Coupons that explain themselves, in both directions

One `_coupon_view()` block is now consumed by the rail and the cart,
so the two cannot describe the same decision differently. It renders when there
is no coupon as well as when there is — *"No coupon — orders are running 44%
above normal for this hour, so every arm costs more in discount than it returns
in extra orders"* — because the interesting half of this system is the half that
declines to discount, and an absence with no copy on it reads as a bug.

The season note states the direction plainly: **summer peak, demand is doing the
selling, coupons go shallow or disappear** · **winter lull, orders below normal,
the coupon goes deeper to move the stock.**

### 20.5 Notifications specialised by condition

`_drivers` gained rain, cold and local events. `_message` builds a headline per
lead driver × size. `CLUSTER_VOICE` gives each pattern family a closing line with
**condition-specific variants**, because a fixed line goes wrong the moment the
weather moves under it — "enough for the whole watch party" on a wet Wednesday
with no game on is worse than saying nothing.

Verified **6 distinct headlines out of 6** in all three of match day, rainy
evening and cold Tuesday:

| Condition | John Smith | David Brown |
|---|---|---|
| Match day, 93 °F | *John, 4 classic bars before kickoff* | *David, 2 almond bars before kickoff* |
| Rainy Wednesday | *Raining out — 2 almond bars to the door* | *Raining out — one almond bar to the door* |
| Cold Tuesday | *John, 2 almond bars worth staying in for* | *David, one almond bar worth staying in for* |

### 20.6 The Impact screen

`server/impact.py` and `GET /api/impact`, first in the nav. This is the easiest
screen in the product to lie on, so it is built to be argued with: every rate is
read off 273 days of log, every projection names the baseline it is measured
against, every estimate carries the IPS interval it came with, and the single
genuine assumption is a slider rather than a constant.

| Against | Per decision | Interval | Crosses zero? |
|---|---|---|---|
| A blanket 20% campaign | **+0.282** | 0.200 – 0.365 | no |
| No targeting at all | +0.035 | −0.064 – 0.135 | **yes** |

Two things the screen refuses to do:

- **It does not round up the weak result.** Against doing nothing it reports +410
  Magnum orders a month and then says the margin difference is *not established
  on this much data*, because the interval crosses zero.
- **It never adds volume to money.** Extra orders and extra margin are two views
  of one lever; adding them would double-count the entire offer policy. Against
  the blanket campaign attach is 1.48pp *lower* — about 171 fewer discounted
  orders a month — and it still makes more, because the campaign was paying for
  orders that were coming anyway. That contrast is the headline, not a footnote.

At ×1 network scale (10 stores, 5,000 households): **$5.2k / month, $15.7k /
quarter, $31.4k / 6 months** of extra gross margin against a blanket campaign,
of which roughly a third is recovered stock. Stock loss is costed at the
*average* demand on a shelf-hour; stockouts cluster in busy hours, so this
understates the loss rather than flattering it.

---

## 21. Iteration 5 — the price on the surface people are looking at (2026-09-02)

Iteration 4 put two fully-resolved recommendations under the search box. The
placement was wrong. The search box is where a shopper *types*; the rail on the
right is where they *look*, and it is the surface that survives every query, every
category and every context change without being dismissed. Putting the worked
answer anywhere else meant the most complete thing the system produced sat in the
one place a shopper scrolls past.

### 21.1 The rail is two rows and each one carries its price

`magnum_rail` defaults to **2**. Each row gains a `coupon` block built by the
same `_coupon_view()` the cart uses, from the same `decide_offer(...,
channel="onsite")` call on the same inputs — so the rail and the cart physically
cannot quote different numbers for the same SKU. Verified end to end: rail says
*12% off any Magnum, saves $1.29*; add it and the cart says *12% off any Magnum,
saves $1.17* on the pack it rounds to. Same depth, same reason, same words.

Everything that was already on the row stays: the rank badge, the plain-words
driver line, the stacked contribution bar, the chevron that opens the full
*What moved it / Score / Weight / Points* table, and the pairing sentence. The
coupon is an addition, not a replacement — the "why it is here" and the "what it
costs" are different questions and both now have an answer on the same card.

Search suggestions went back to a compact chip row. Seven chips, no pipeline run
per chip, but ordered by the improved `_suggest_score()` — so the row still
re-orders live when the weather, the hour, the occasion or the household moves,
which is the only claim a shortcut needs to make. `SuggestionCards.tsx` is gone.

### 21.2 Depth moves for the household, not only for the hour

With the coupon on the rail, a flat depth across every household became obvious:
click through six very different people on the same hot Friday and every one of
them was offered the same 14%. `discount_depth` read `demand_index` and nothing
else.

`household_depth()` adds two terms, both read off the order log rather than
assumed:

| Term | Beta | What it reads | Direction |
|---|---|---|---|
| `HH_CADENCE_BETA` | 0.34 | `due_ratio` − 1, clamped [−0.60, +1.00] | past their own rhythm → deeper |
| `HH_PRICE_BETA` | 0.30 | `discount_response` − 0.35, clamped [−0.35, +0.45] | pays full price → shallower |

Continuous, not banded. A threshold would price two households a day apart in
their cadence four points apart, which is not a difference either of them did
anything to earn. The term that actually carried the move is named, and its
sentence rides on the coupon block as a second line: *"They are past their own
reorder rhythm, so this one goes deeper to win the trip back"* · *"This household
mostly pays full price, so we do not spend much buying a decision they were
already making."*

Measured, top rail row, store resolved from the household's own home area rather
than pinned, nothing else touched. (Pin the area — Astoria, say — and the levels
shift with the local demand index while the ordering holds.)

> **Re-measured 2026-09-02, after §22.** The table first written here was taken
> with `day="tue"` and `weather="cold"`. Neither is a value `context.resolve()`
> accepts — it falls back to `friday` / `warm` without complaint — so two of its
> three columns were the same context under different headings. Valid values are
> the full day names and `hot` / `warm` / `cool` / `rain` / `snow`. The figures
> below are re-measured with valid values and against the current policy.

| Household | Hot match-day Friday, dinner | Cool Tuesday afternoon | Rainy Wednesday, late | Snowy Sunday, dinner |
|---|---|---|---|---|
| John Smith | 10.9% | 21.3% | 21.6% | 21.5% |
| Sarah Miller | 10.7% | 21.2% | 21.4% | 21.3% |
| David Brown | **no coupon** | 19.1% | 19.4% | 19.3% |
| Emily Davis | no coupon | no coupon | no coupon | no coupon |
| Michael Johnson | 14.2% | 23.6% | 23.7% | 23.7% |
| Jessica Wilson | no coupon | no coupon | no coupon | no coupon |

Both axes are live at once: read a row and the hour is moving the price, read a
column and the household is. Michael Johnson is 71% past his own cadence and
buys on offer, so he is the deepest everywhere. Jessica Wilson has never bought
on an offer in 273 days of log, so the policy declines to pay her — on every hour
tested. That is not a gap in the demo; it is the guardrail doing the only job it
has.

The three quiet columns land within half a point of each other, and they used to
land on exactly the same number: all three saturated the 25% cap and printed
23.3%, 22.9%, 19.9% down the column with nothing distinguishing a cool spring
afternoon from a snowy winter dinner. §22.4 is the fix — the same bounds, held
softly.

### 21.3 Impact rebuilt as four charts

The previous version was three cards, two prose panels, a table and a method
list — all defensible, none of it legible at a glance in a room. It is now four
charts with one sentence of caption each, and a single "how to read these" note
at the foot:

| Chart | What it answers |
|---|---|
| Margin gained (stacked bars, 95% whiskers) | how much, split into offer decisions and recovered stock |
| Value per decision (**forest plot**, dashed zero line) | is it distinguishable from zero at all |
| Extra Magnum orders (grouped bars) | won by targeting vs saved by substitution |
| Stockouts and waste avoided (grouped bars) | what the availability half is actually made of |

The forest plot is the point of the redesign. A bar growing out of an axis hides
whether its interval crosses zero; a point with the interval drawn through it and
a dashed line at zero puts the whole argument in one glance — the blanket-campaign
comparison sits clear of the line, the do-nothing comparison straddles it. The
screen still refuses to round the weak result up.

Both sliders stay, moved into the header. They are what make the page a live
model rather than a slide: the recovery assumption is labelled as the only
assumption on the page, and network scale takes the measured rates out to a real
footprint.

Implementation note: every `<Bar>` and `<Scatter>` carries
`isAnimationActive={false}`, matching every other chart in the app. Without it
the entry animation never completes in this environment and recharts renders the
rectangles at zero height — the axes, legends and labels all draw and the bars
simply are not there.

## 22. Iteration 6 — making every external condition move something (2026-09-02)

The brief for this iteration was one sentence: *for any external condition,
something should change for the first three households — the flavour, the
quantity or the discount — and every custom message with it.* Testing it found
four places where a real, measured signal was being computed and then thrown
away before it reached a surface, and one place where two genuinely different
worlds were being printed as the same number.

### 22.1 `demand_index` divides the day back out

`demand_index` is raw demand over the **same day and hour** under ordinary
conditions. That is the right denominator for the question it answers — *is this
hour trading unusually?* — and it means the day of the week cancels by
construction. `discount_depth()` read only that, so every day priced identically:
**16.56%, seven days a week**, holding everything else fixed. The Day selector
was wired, live, and arithmetically incapable of moving the price.

The fix is a second index that holds exactly what the first one divides out.
`slot_index` is the neutral multiplier — day, hour and season with no weather,
no occasion, no local activity — over a fixed reference:

```python
# The order-weighted median neutral multiplier across the whole log - the
# trading level of a typical hour in which somebody actually orders, as opposed
# to a typical hour on the clock, most of which are the middle of the night.
_TYPICAL_NEUTRAL = 1.3404
```

The reference is measured, not chosen, and the choice of *order-weighted median*
is the point. A plain mean over the clock is dominated by the 3 a.m. hours nobody
orders in, which would put the typical slot far below 1.0 and hand every real
trading hour a permanent "busy" trim. Weighting by orders asks the question that
matters: what does an hour in which somebody is actually shopping look like?

Measured at dinner, holding season and weather:

| Day | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| `slot_index` | 1.329 | 1.283 | 1.360 | 1.497 | 1.833 | 2.017 | 1.742 |

The two indices are disjoint by construction — `slot_index` holds day, hour and
season, `demand_index` holds weather, occasion and activity — so adding their
effects counts nothing twice. The slot term enters `discount_depth()` through
`log2(slot_index)`, because the index is multiplicative and twice as busy should
read as one step whichever end of the range it lands at.

### 22.2 The day reached the ranking through a single step at Friday

The other half of the same problem. The day's only route into the *ranking* was
`group_bias`, a two-step function that changes once, at Friday. Six of the seven
days were interchangeable there too.

`Store._build_occasion_profile()` replaces the assumption with a measurement.
Across all 25,280 Magnum orders it computes, per weekday and for the match
window: how often a basket takes a pack rather than a single, how many bars come
home, and how the flavour mix tilts — each as a lift against the same quantity
over the whole log. Base: pack share **0.4442**, **2.5865** bars per basket.

| Day | n | pack lift | bars lift |
|---|---|---|---|
| Monday | 2,673 | 0.820 | 0.937 |
| Tuesday | 2,316 | 0.836 | 0.935 |
| Wednesday | 2,869 | 0.902 | 0.939 |
| Thursday | 3,091 | 0.862 | 0.937 |
| Friday | 4,954 | 1.096 | 1.050 |
| Saturday | 4,997 | 1.100 | 1.043 |
| Sunday | 4,380 | 1.135 | 1.052 |
| **Match window** | 5,006 | **1.360** | **1.138** |

Day and match window overlap — match windows cluster on particular days — so
`_add_occasion()` combines the two slices **in deviations from 1.0** rather than
multiplying, which would count the overlap twice, then applies `OCCASION_PULL =
0.5` on the same principle as every other borrowed coefficient here: the log is
one network's worth of evidence and the policy should lean on it, not lunge. A
slice under `MIN_PROFILE_ORDERS = 400` has nothing to say and is held at 1.0.

After the pull, the lift the policy actually sees spans **0.910** (Monday) to
**1.248** (Sunday match).

### 22.3 The measured pack share stopped at the rail

`occasion_pack_lift` moved the ranking and went no further. The cart fitter never
saw it, so toggling match day on a Monday returned the same six bars it had
returned a moment earlier, which is precisely the complaint that opened this
iteration.

Two things were wrong in `_pack_for_units()`, and the first fix for each was
wrong in an instructive way.

**`MAX_UNITS` was 6.** A match-day two-pizza basket computes 8.1 bars, so every
context above six flattened to the same answer — the cart looked frozen while the
model underneath it was moving. Raised to **10**, which is two six-packs: the
largest number that is still a suggestion rather than a bulk order.

**The fitter ranked on leftover alone**, which is correct up to six bars and
absurd above it: a loose single hits any target exactly, so a strict leftover
ranking hands singles every tie. Once the cap lifted it started proposing nine
loose bars at $3.49 with an $11.49 six-pack on the shelf. A full shortfall and
overage cost model over-corrected into twelve bars for a target of nine. What
shipped is a one-bar tolerance — inside it the fitter picks on price, outside it
fit wins — plus `GROUP_UNITS = 4`, above which price per bar outranks flavour,
because above four bars the basket is for a table and the log agrees: pack share
climbs with basket size regardless of flavour.

Then the pack lift itself. It does **not** change how many bars are wanted — the
size signal is already in the target — it changes how much slack a box is allowed
in reaching it, and the slack is deliberately **asymmetric**:

| Night | Multipack may over-deliver by | may under-deliver by |
|---|---|---|
| Pack night (`pack_bias ≥ 1.08`) | 2 bars | 0 |
| Ordinary | 1 bar | 1 bar |
| Quiet night (`pack_bias ≤ 0.99`) | 0 | 1 bar |

Widening it symmetrically was tried first and does the opposite of what it looks
like: it lets the cheapest box *undershoot* a group target and win on unit price,
which sent a Friday match-day basket **down** from nine bars to six. The fitter
also now costs both the floor and the ceiling pack count rather than only the
nearest — rounding alone never offers three boxes for a target of seven, so the
only format that could hit that target exactly was the loose single.

`PACK_BIAS_HI = 1.08` and `PACK_BIAS_LO = 0.99` are not round numbers picked for
looks; they sit in the two gaps of the served distribution. Across every day ×
match-window the policy can be asked for, the lift lands in three clumps —
weeknights 0.91–0.95, weekends 1.05–1.07, match windows 1.09–1.25 — and the
thresholds sit in the empty space between them.

### 22.4 Two different worlds, one number

The last defect was the quietest. `discount_depth()` clamped the demand slack at
±0.45 and the result at `MAX_DISCOUNT_PCT`; `household_depth()` clamped again.
Any hour slow enough to reach a clamp came out at the same place as every other
hour slow enough to reach it. A cool Tuesday afternoon and a rainy Wednesday
midnight printed the **identical 23.3%** coupon, for two households, on two
conditions with nothing in common.

Every bound is now a soft bound with exactly the same limits. `tanh` on the slack
and on the slot pressure; an exponential approach on the depth:

```python
SOFT_CAP_KNEE = 0.18

def _soft_cap(x, lo, hi, knee=SOFT_CAP_KNEE):
    if x <= lo:   return lo
    if x <= knee: return x
    span = hi - knee
    return knee + span * (1.0 - math.exp(-(x - knee) / span))
```

The slack never leaves ±0.45, the depth never reaches 25%, and both are strictly
monotone all the way out, so ordering survives past the edge. Below the knee the
function is the identity and ordinary trading is untouched — which matters,
because the first version softened from the floor instead and quietly turned a
plain unadjusted 20% base into **15.2%**. That is what a soft cap looks like when
nobody checks the middle.

### 22.5 Restraint that says which night it is declining

A price that holds still across two different nights is a defensible answer. An
*explanation* that is byte-identical across two different nights reads as a
screen that ignored the change. `_coupon_view()` now builds a `when` phrase from
the day and window and an `occ_phrase` from the measured occasion terms, and uses
them in the label, the `why` and a `slot` line on all three no-coupon branches:

> **No coupon · Saturday 7-10 PM** — orders are running 36% above normal for this
> hour. At that level the shallow price this hour can afford would not move this
> household enough to pay for itself.
> *The pick and the size are still moving — saturday and match window baskets are
> what put this one first.*

Match-day notification headlines gained the day for the same reason: a Monday
game and a Saturday game were pushing the same sentence, and they are not the
same night — the measured pack share on a Saturday match is a fifth higher again.

### 22.6 Considered and rejected: relaxing the uplift floor on-site

Adding the slot term pushed the trimmed depth below `MIN_UPLIFT_PP` on busy hours
and coupons collapsed to zero everywhere. `MIN_UPLIFT_ONSITE = 0.005` was tried
and reverted within the hour: with no contact cost to pay, the zero-discount
`flavour_discovery` arm then outscored every voucher on every hour of the week,
and the system stopped discounting altogether. That is arguably the correct
economic answer, and it is certainly not a guardrail to remove as a side effect
of a pricing change. The floor stays on both channels with the reasoning written
into the code; `SLOT_BETA_BUSY` was softened to 0.10 instead.

### 22.7 What moves now

Astoria, summer, warm, dinner, everything else held. Rail = top row of the live
Magnum picks; cart = two large cheese pizzas.

| | Monday | Monday + match | Saturday | Saturday + match |
|---|---|---|---|---|
| **John Smith** — rail | Classic bar · 15.9% | Caramel 3-pack · 13.2% | Caramel 3-pack · 15.1% | Caramel 3-pack · 12.4% |
| **John Smith** — cart | 6 mini classic | **9 almond** | 6 mini classic | **9 almond** |
| **Sarah Miller** — rail | Caramel 3-pack · 15.6% | Caramel 3-pack · 13.0% | Caramel 3-pack · 14.8% | Caramel 3-pack · 12.2% |
| **Sarah Miller** — cart | 6 mini classic | **9 almond** | **9 almond** | **9 almond** |
| **David Brown** — rail | Classic bar · 13.6% | **Almond 3-pack · no coupon** | Classic bar · 12.9% | **Almond 3-pack · no coupon** |
| **David Brown** — cart | 3 almond | **6 mini classic** | 6 mini classic | 6 mini classic |

Reorder notifications, same three households across seven conditions, produced
21 distinct headlines — no two conditions share one within a household.

The honest limit, stated so nobody has to discover it in front of a client:
**Monday and Tuesday genuinely look alike in this log.** Their pack lifts are
0.820 and 0.836, their slot indices 1.329 and 1.283, and forcing them apart on
screen would be fabrication. Rounded to a whole percent they can print the same
coupon label. The breakdown strip on the rail row — `20% base · hour −37.1% ·
slot −4.4% · = 10.9%` — is where the difference between them stays visible, and
it is the right place for it: a tenth of a point is a real number and not a
headline.

### 22.8 Impact screen: forest plot removed

The confidence-interval chart added in iteration 5 was not legible to the
audience the page is for, and a client asking "what am I looking at" about the
second chart on the business-case screen is a chart that has failed. Impact is
now three: margin gained by horizon with 95% whiskers, extra Magnum orders split
by how they were won, and stockouts and waste avoided. The significance evidence
has not gone anywhere — it is still served by `/api/analysis/policy-eval` and
still shown on the Analysis screen, which is where an analyst goes looking for
it. It is no longer the second thing a client sees.

---

## 23. Deployed to Azure (2026-09-10)

Live at **https://magnum-now-demo.azurewebsites.net**, verified 2026-09-10 05:45 UTC:
`/api/health` returns `{"status":"ok","loaded_in_s":42.73}`, the Impact panel
renders 13 charts against live data, `latent_traits` and `ground_truth` both
answer 403, and the Uber adapter reports `enabled:false`.

### 23.1 What was created

One resource group, in the region and naming convention the subscription's other
demos already use (`rg-*-demo-ci`, `centralindia`).

| Resource | Name | Notes |
|---|---|---|
| Subscription | `ACIINFOTECH-AZURE-SUBCRIPTION-DEMOS` | `75dba07a-…` |
| Resource group | `rg-magnumnow-demo-ci` | `centralindia` |
| App Service plan | `asp-magnumnow-demo` | Linux, **B2** — 2 cores, 3.5 GB RAM, ~$26/month. See §23.5: B1 was the original choice and the cold start is now cheap enough that B1 would likely hold, but B2 is what the working deployment was verified on. |
| Web app | `magnum-now-demo` | Python 3.11, one instance |

Everything lives in that one resource group, so `az group delete -n
rg-magnumnow-demo-ci --yes` removes the whole deployment and stops the billing.
To pause without destroying it: `az webapp stop -g rg-magnumnow-demo-ci -n
magnum-now-demo` — the plan still bills, the app stops answering.

### 23.2 How it deploys

`scripts/deploy_azure.sh` is the whole procedure and is idempotent: rebuild the
UI, zip the seven paths the app actually needs, push, wait for health.

The package is **58 MB** — the 325 MB SQLite file is 59 MB gzipped, and shipping
it beats running the generator on the host. It is deterministic from `SEED =
20260901`, so if the artifact ever has to shrink, regenerating at build time
produces identical bytes and is a drop-in swap.

Deliberately *not* in the package: `web/src`, `web/node_modules`, `docs/`, the
CSV exports, and this file. `data/data_quality.json` **is** in it — `store.py`
reads it at startup and the app will not boot without it. That was found by
reading the startup path rather than by watching a deploy fail.

**The app does not run from `/home/site/wwwroot`.** Oryx packs the built app
into `wwwroot/output.tar.zst` and extracts it to `/tmp/<hash>` at every container
start, so at runtime `wwwroot` holds the tarball and little else. The first
deploy succeeded and the site still returned 503: the startup command pointed at
`/home/site/wwwroot/scripts/azure_startup.sh`, bash could not find it, and the
container exited 127 in 43 s. Nothing in the deployment status showed this —
it reported 4 (SUCCESS). It was only visible in
`LogFiles/StartupLogs/*_failure.log`.

Both halves are now path-independent: the startup command discovers the app root
(wwwroot if the app is really there, otherwise the extracted `/tmp` copy), and
`azure_startup.sh` resolves its own directory instead of assuming one.

### 23.3 Configuration

| Setting | Value | Why |
|---|---|---|
| `UBER_ADAPTER_ENABLED` | `false` | The adapter stays off in the deployed build, set explicitly rather than left to the default. |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Oryx installs `requirements.txt` on the host. |
| `WEBSITES_CONTAINER_START_TIME_LIMIT` | `600` | Headroom over the measured 6 s warm-up; the default 230 s would be enough, but a cold pip install of pandas and numpy on B1 is not fast. |
| Startup command | `bash -c 'A=/home/site/wwwroot; [ -f "$A/server/main.py" ] \|\| A=$(ls -d /tmp/*/server/main.py 2>/dev/null \| head -1 \| xargs -r dirname \| xargs -r dirname); cd "$A" && exec bash scripts/azure_startup.sh'` | Finds the app root, then hands off to the script, which pins `--workers 1`. See §19 for why, and §23.2 for why the path has to be discovered. |

`requirements.txt` pins exact versions. The generator is deterministic and the
policy numbers in this document are measured off it, so a floating dependency
would let a deployed demo quietly disagree with its own documentation.

### 23.4 The bug deploying found: `get_store()` had no lock

Deploying surfaced a real concurrency defect that local use never could.

```python
def get_store() -> Store:          # before
    global _store
    if _store is None:
        _store = Store()           # every caller that gets here builds its own
    return _store
```

`Store()` costs **2.5 s and 315 MB**; the full warm-up including the seven
analysis panels costs **5.8 s and 579 MB** (measured, not estimated). Nothing
serialises construction, so `_store is None` stays true for every request that
arrives during that window and each one builds a **complete second store**.

Locally the window is 2.5 s with nobody knocking, so it never fired. On App
Service the warm-up thread started one build, the platform's startup probe
started another, and each health poll started another. The instance climbed
198 → 417 → 870 → 1011 → 1117 MB on B1, and after scaling to B2, straight on to
2506 MB — growing to fill whatever it was given, with no build ever winning.

What made it hard to see: the symptom was `/api/health` hanging, which reads as
"the server is down". It wasn't. `/` returned **200 in 0.4 s** and the JS bundle
served fine the whole time — only the API hung, because `health()` called
`get_store()` and queued behind a build that never finished. The one endpoint
that most needed to answer during a cold start was the one that couldn't.

Both halves are fixed. `get_store()` is now double-checked under a lock, and
`health()` uses `store_if_built()`, which never triggers a build and reports
`{"status":"loading"}` until one is ready. Verified locally by firing twelve
concurrent requests at a cold server: **431 MB peak, one store** — before the
fix that would have been twelve. In production the first build now completes in
**42.7 s**, and health reports `loading` then `ok` instead of timing out.

This would have hit the client demo directly: the first two people to open the
page on a cold instance were enough to trigger it.

### 23.5 Three deployment traps, all in the startup path

Worth keeping, because none of them showed up as a failed deployment — every
one reported success while the site returned 503.

1. **The app does not run from `/home/site/wwwroot`.** Oryx packs the build into
   `wwwroot/output.tar.zst` and extracts it to `/tmp/<hash>` at every container
   start. An absolute wwwroot path in the startup command exits **127**.
2. **The startup command must not contain single quotes.** Oryx wraps the user
   command in single quotes when generating `/opt/startup/startup.sh`. A quoted
   command mangles that script and silently loses the antenv `PYTHONPATH`
   export, giving **`No module named uvicorn`** from the system interpreter.
   The command is now the quote-free `bash scripts/azure_startup.sh`; Oryx has
   already `cd`-ed to the app path by then.
3. **Do not change configuration while a deployment is in flight.** An
   `az webapp config set` during a push restarts the SCM container and kills the
   deployment: *"Deployment has been stopped due to SCM container restart."*
   Change config, or deploy — not both at once.

A fourth, less reproducible: one Oryx build wedged at *"Running oryx build…"*
for 25 minutes against 4 minutes for the identical build earlier. A site restart
and a re-push cleared it.

### 23.6 Standing caveats

- **The site is public and unauthenticated.** That is a deliberate choice for a
  client demo of entirely synthetic data carrying its own disclaimer in the
  footer, not an oversight. If it needs to be closed, App Service auth or an IP
  restriction is a configuration change, not a code change.
- **One instance, and it should stay that way.** The store is in-process memory
  over a read-only SQLite file. Scaling out would give each instance its own
  copy of a 615 MB working set for no throughput that this workload needs.
