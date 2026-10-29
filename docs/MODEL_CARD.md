# Model card — Magnum Now decision layer

Version `policy-v1.0.0` / `forecast-baseline-v1.0.0` / generator `gen-v1.0.0`,
seed `20260901`. Covers every model that influences a user-visible decision in
this build. Companion to [BUILD.md](../BUILD.md) §6, §10 and §13.

**All inputs and outputs are synthetic.** Nothing here has been trained on, or
evaluated against, real Magnum, Uber, retailer or customer data. Numbers below
are properties of a simulation, not forecasts of a real market.

---

## 1. What is modelled

| Model | Output | Where it is used |
|---|---|---|
| **Context demand model** | `raw_demand_multiplier`, `demand_index`, `absolute_index`, `heat_pull` for a (store, hour, weather, season, event) tuple | shared by the generator *and* the runtime — the same function writes the data and scores the live request |
| **Ranking score** | per-SKU relevance for search and browse | Shop |
| **Quantity model** | q\* = 0.40 personal + 0.35 peer + 0.25 occasion | Cart |
| **Uplift table** | attach lift per (arm, peer cluster), shrunk toward the pooled effect | Offer decision |
| **EIC offer policy** | expected incremental contribution, guardrailed | Offer decision |
| **Forecast** | p10/p50/p90 units per store-SKU-hour, 48 h ahead | Demand desk, stock actions, reorder timing |

The demand model being shared is deliberate and is the main reason the forecast
scores well: it is not an independent learner, it is the generator's own
structure fitted per store and SKU. That is honest for a reference build and
would be dishonest as a production claim — see §5.

## 2. Training and evaluation data

273 simulated days split **temporally**, never randomly:

| Split | Share | Days | Use |
|---|---|---|---|
| fit | 72% | 1–196 | uplift table, demand rates, customer/cluster features |
| calibrate | 14% | 197–234 | threshold and guardrail setting |
| holdout | 14% | 235–273 | every number quoted in the analysis screen |

Offer arms were assigned **uniformly at random** at propensity 0.20 on every
eligible decision — 118,233 decisions, logged whether or not anything was
bought. That is what makes the uplift estimates unbiased and inverse-propensity
policy evaluation valid; it is also the single most important property of the
dataset and the one an observational log would not have.

## 3. Evaluation results (holdout, 21,990 decisions)

**Incremental lift.** Baseline attach with no nudge: 23.28%.

| Arm | Attach | Uplift | 95% CI | Significant | \$ vs none |
|---|---:|---:|---|---|---:|
| voucher20 | 29.16% | +5.89 pp | [+4.04, +7.73] | yes | **−0.2570** |
| multipack_value | 26.65% | +3.37 pp | [+1.56, +5.18] | yes | **−0.0188** |
| reminder | 25.40% | +2.12 pp | [+0.32, +3.92] | yes | +0.0586 |
| flavour_discovery | 24.67% | +1.39 pp | [−0.40, +3.18] | no | +0.0241 |

Every arm lifts attach. Two of them destroy margin doing it. `flavour_discovery`
is positive on money but its lift is **not** statistically distinguishable from
zero at this sample size — the honest reading is "cheap, plausibly useful,
unproven".

**Offline policy value** (IPS, propensity 0.20):

| Policy | \$/decision | 95% CI |
|---|---:|---|
| always_reminder | +0.8048 | [+0.756, +0.854] |
| eic_greedy_v1 (shipped) | +0.7628 | [+0.717, +0.809] |
| do_nothing | +0.7346 | [+0.688, +0.781] |
| uplift_greedy | +0.4584 | [+0.431, +0.486] |
| always_voucher20 | +0.4409 | [+0.414, +0.467] |

`uplift_greedy` is the control worth staring at: it optimises exactly what a
conversion model optimises, correctly identifies the voucher's real lift, and
finishes fourth of five because it pays for that lift out of margin. The
shipped policy's CI overlaps `always_reminder`'s — on this data it is *not*
demonstrably better than always sending the cheapest nudge, and the build does
not claim otherwise. Its case is that it leaves 45% of decisions alone, which
is what the frequency and fatigue guardrails exist to buy.

**Forecast accuracy** — 39 weekly backtest origins, 112,320 forecast/actual
pairs, each origin using only sales that had already happened:

| Metric | Value |
|---|---:|
| p90 coverage (hourly) | 95.9% |
| p10 coverage (hourly) | 100% |
| WAPE, store-day | 0.79 |
| WAPE, SKU-day | 1.05 |
| Pinball @ p90 | 0.074 |
| Bias | −0.007 units/hour |

Hourly WAPE (1.74) is reported but is close to meaningless: demand for one
flavour in one store in one hour is almost always 0 or 1, and a percentage
error on a zero denominator measures nothing. p90 coverage is the metric tied to
the actual decision — the share of hours the shelf would have survived had it
been filled to p90.

**Ground-truth recovery.** The generator knows each arm's true effect; the
analysis layer is not allowed to see it until scoring:

| Arm | True | Recovered | Error | In 95% CI |
|---|---:|---:|---:|---|
| reminder | +1.90 pp | +1.85 pp | 0.05 | yes |
| flavour_discovery | +1.48 pp | +1.90 pp | 0.41 | yes |
| multipack_value | +3.35 pp | +3.35 pp | 0.01 | yes |
| voucher20 | +5.80 pp | +5.26 pp | 0.55 | yes |

Largest absolute error 0.55 pp; all four inside their intervals. This is the
check that says the analysis layer is reading the log correctly — if it failed,
every other number on this page would be suspect.

## 4. Guardrails in the shipped policy

An arm ships only if it clears all of: uplift ≥ 2.0 pp, discount ≤ 25%,
frequency cap not hit (24 h / 7 d contact counts), no post-purchase
suppression window, marketing consent present, and EIC > 0 where
`EIC = uplift × (unit margin − discount) − contact cost`. Every blocked decision
emits a reason code; the cart screen can force each blocking state on demand.

Cluster cells in the uplift table are shrunk toward the pooled arm effect with
weight `n / (n + 400)`, so a thin cell cannot swing a live decision on noise.

## 5. Limitations — read before quoting any number

1. **The forecast shares the generator's demand model.** Its accuracy measures
   parameter recovery, not the ability to predict a market nobody wrote. On
   real data, expect materially worse.
2. **Synthetic ceiling.** Effect sizes, price elasticity, weather sensitivity
   and margin structure were chosen to be plausible and internally consistent.
   None of them are measurements.
3. **Uniform randomisation is not free in production.** The unbiasedness that
   makes the analysis clean comes from showing a random arm to every eligible
   customer. A real pilot must budget for the cost of that exploration or use a
   logged-propensity bandit instead.
4. **IPS on a five-arm uniform log is low-variance here and will not be later.**
   Once propensities concentrate, these CIs widen fast; doubly-robust
   estimation is the next step, not a refinement.
5. **flavour_discovery is unproven**, per §3. Treat it as a hypothesis.
6. **Single market, single brand, one season-and-three-quarters.** 10 stores,
   26 SKUs, NY/CT, 39 weeks. No generalisation to other geographies, formats or
   categories is supported.
7. **No fairness audit.** Peer clusters are behavioural, not demographic, and
   the build carries no protected attributes — but it has also not been tested
   for disparate impact, and it should be before any real deployment.
8. **Cold-start is a prior, not a model.** New store-SKU pairs fall back to a
   chain-wide rate. That fallback was the single largest accuracy bug found
   during the build (change log #12).

## 6. Data handling

- `latent_traits` and `ground_truth` are evaluation-only. The application layer
  cannot reach them: the data explorer returns `403`, and the only read in the
  service is `analysis.validation()`, which returns five summary rows.
- No secrets, tokens, production identifiers or personal emails exist in source,
  logs or deliverables.
- The Uber sandbox adapter is a stub behind `UBER_ADAPTER_ENABLED` (default
  `false`) and makes no external calls.

## 7. Reproducing

```bash
python3 generator/generate.py     # seed 20260901, deterministic
python3 -m uvicorn server.main:app --port 8000
curl -s "localhost:8000/api/analysis/policy-eval"
```

Every table on this page is regenerated from `/api/analysis/*` and passes the
generator's ten-check quality gate (10/10 at time of writing).
