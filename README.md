# Magnum Now — context-aware commerce POC

A working reference build for the Magnum quick-commerce concept: an Uber
Eats-**inspired** storefront where every screen is driven by the same
context-aware demand model, and an analysis console that checks whether the
decisions it makes were actually the right ones.

> Not an Uber product. Not affiliated with or endorsed by Uber. No Uber logos,
> wordmarks or trade dress appear in this build. **All data is synthetic** — no
> real Magnum, Uber, retailer or customer data is used anywhere.

Market: New York + Connecticut metro, 10 dark-store catchments, 26 SKUs, USD.
Simulation window: 2025-12-02 → 2026-09-01 (39 weeks), seed `20260901`.

---

## What it does

| Screen | Question it answers |
|---|---|
| **Shop** | Given this neighborhood, hour, weather and occasion, what should we show — and why, term by term? |
| **Cart** | How many should we suggest, and is a nudge worth its margin? |
| **Demand desk** | What will each store sell in the next 48 hours, and what should move tonight? |
| **Analysis** | Did any of it work? Incremental lift, offline policy value, forecast accuracy, demand drivers, ground-truth recovery. |
| **Data** | Every table the app reads, straight off SQLite. |

The result the build exists to show is on the Analysis screen. All four offer
arms genuinely lift attach — but only the two non-discount ones make money, and
a policy that greedily maximises uplift (which is what a conversion model
optimises) lands **second from last** on dollars, behind doing nothing.

## Quick start

```bash
python3 -m pip install -r server/requirements.txt
python3 generator/generate.py          # deterministic, ~90s
python3 -m uvicorn server.main:app --port 8000
cd web && npm install && npm run dev   # http://localhost:5173
```

`scripts/start.sh` runs the last two together.

## Layout

```
BUILD.md          the full plan, as-built notes and an append-only change log
generator/        deterministic synthetic data generation
magnum_core/      catalog, context model, peer clusters, policies, reason codes
data/             generated CSVs + magnum.db
server/           FastAPI: 9 product endpoints, 7 analysis endpoints, data explorer
web/              React 19 + TS + Vite + Tailwind 4 client
docs/MODEL_CARD.md    what the models do, how they were evaluated, where they fail
docs/DEMO_RUNBOOK.md  presenter's script for the client demonstration
```

## Ground rules held throughout

- **Synthetic only.** The generator writes every row. Nothing is scraped,
  licensed or imported.
- **No secrets.** No tokens, OAuth credentials, production IDs or personal
  emails in source, logs or deliverables.
- **Held-out tables.** `latent_traits` and `ground_truth` are evaluation-only.
  The application never reads them; the data explorer returns `403`; the single
  read anywhere in the service is `analysis.validation()`, which returns five
  summary rows and no per-decision score.
- **Uber adapter is off.** `/api/integrations/uber/status` is a stub behind
  `UBER_ADAPTER_ENABLED`, default `false`. Nothing in this build calls an
  external service.

See [BUILD.md](BUILD.md) for the full specification, and
[docs/MODEL_CARD.md](docs/MODEL_CARD.md) for evaluation and limitations.
