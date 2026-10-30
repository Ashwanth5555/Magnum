# Magnum Now — context-aware commerce POC

A working reference build for the Magnum quick-commerce concept: an Uber
Eats-**inspired** storefront where every screen is driven by the same
context-aware demand model, plus an impact view that checks whether the
decisions it makes were actually worth making.

> Not an Uber product. Not affiliated with or endorsed by Uber. No Uber logos,
> wordmarks or trade dress appear in this build. **All data is synthetic** — no
> real Magnum, Uber, retailer or customer data is used anywhere.

| | |
|---|---|
| **Market** | New York + Connecticut metro, 10 dark-store catchments, USD, °F |
| **Catalogue** | 28 SKUs — 8 Magnum (4 singles, 4 multipacks) + 20 meals, drinks, sides, desserts |
| **Simulation window** | 2025-12-02 → 2026-09-01 (39 weeks), deterministic seed `20260901` |
| **Scale** | 5,000 households · ~240k sessions · ~88k orders · ~118k randomised offer decisions |

---

## Live demo

| Version | Link | Notes |
|---|---|---|
| **Latest** | https://magnum-now-demo-v2.azurewebsites.net | Current `main` — seasonal funnel, honest ranges, Demand desk interactions |
| Original | https://magnum-now-demo.azurewebsites.net | First deployment, kept unchanged for reference |

Both are public and unauthenticated (synthetic data only). After a quiet period
the first visit takes **~35–40 s** while the server loads its data ("Starting
the console…"). If you see an older layout, hard-refresh with **Ctrl + F5**.

---

## What it does

| Screen | Question it answers |
|---|---|
| **Impact** | What does running this add up to over the first month, and the next 3 and 6 months? Shown-to-bought funnel, extra Magnum orders (with a 95% range), stockouts and waste avoided, and margin gained against a blanket 20% campaign. |
| **Shop** | Given this neighbourhood, hour, weather and occasion, what should we show — and why, term by term? A live Magnum rail, a "what if the weather changed" strip, and a feed of what each context change moved. |
| **Cart** | How many bars, in which pack, and is a coupon worth its margin? Basket-aware pack and quantity, with the coupon's depth explained. |
| **Customer** | Who is this household? History, cadence, flavour mix against their peer cluster, offer history, and the next-purchase nudge. |
| **Demand desk** | What will each store sell in the next 48 hours, and what should move before the peak? Click a product to see its own forecast band; click a legend colour to highlight it. |
| **Data** | Every table the app reads, straight off SQLite. |

### The result the build exists to show

All four offer arms genuinely lift Magnum attach — but only the non-discount
ones make money, and a policy that greedily maximises uplift (which is what a
conversion model optimises) lands near the bottom on dollars. The shipped policy
(`eic_greedy_v1`) beats a blanket 20% voucher on margin per decision with an
interval that does not cross zero, and it does it by discounting *less*.

### How to read the Impact numbers

- **Counted, not invented.** Every figure is read off the log. The funnel is the
  first 1, 3 and 6 months counted from the start of the log; the share bought
  rises 13.3% → 15.2% → 19.0% as the run moves out of winter.
- **Three stated assumptions, each a slider:** forecast recovery (default 35%),
  substitutes that save a sale (default 40%), and **network scale** (default
  **×10 = a 100-store network**; ×1 is the simulated 10 stores). Rates never
  change with scale — only volumes do.
- **Ranges travel with estimates.** The targeting lift is +3.5 pts against doing
  nothing (95% range 1.7–5.4), drawn as a whisker on the chart.
- **Synthetic means unproven.** The lift was built into the simulation; a
  randomised pilot is what would confirm it with real shoppers.

---

## Tech stack

| Layer | Built with |
|---|---|
| Web client | React 19 · TypeScript · Vite 7 · Tailwind 4 · recharts · lucide-react |
| API | FastAPI on Python 3.11 (uvicorn, one worker) |
| Data | SQLite (`data/magnum.db`) + CSV exports, built by a deterministic pandas/numpy generator |
| Hosting | Azure App Service (Linux, B2 plan) — the API also serves the compiled UI, so it is one process on one port |

---

## Repository layout

```
BUILD.md              full specification, as-built notes and an append-only change log
README.md             this file
requirements.txt      pinned Python dependencies (used locally and on Azure)
generator/            deterministic synthetic data generation (config.py holds the seed)
magnum_core/          catalogue, context/demand model, peer clusters, policies, reason codes
server/               FastAPI app: product, analysis, impact and data-explorer endpoints
web/                  React client (src/) — compiled to web/dist and served by the API
scripts/              start.sh, deploy_azure.sh, azure_startup.sh, data-shaping and image scripts
docs/MODEL_CARD.md    what the models do, how they were evaluated, where they fail
docs/DEMO_RUNBOOK.md  presenter's script for the client demonstration
data/                 generated database and CSVs (not committed — see below)
```

---

## Getting started

### Prerequisites

- **Python 3.11** (the pinned numpy/pandas versions have no wheels for much newer Pythons)
- **Node.js 20+** and npm
- Git

### 1. Clone and install

macOS / Linux:

```bash
git clone https://github.com/Ashwanth5555/Magnum.git
cd Magnum
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install --prefix web
```

Windows (PowerShell):

```powershell
git clone https://github.com/Ashwanth5555/Magnum.git
cd Magnum
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install --prefix web
```

### 2. Generate the data

The database is **not** in the repository (it is ~325 MB and fully
reproducible). Build it once — deterministic, no network, a minute or two:

```bash
python generator/generate.py
python scripts/shape_demo_seasonality.py
python scripts/shape_store_flavours.py
```

The generator writes `data/magnum.db`, the CSVs and `data/data_quality.json`,
and exits non-zero if any of its quality checks fail. The two shaping scripts
give the demo households a full-season history and each store its own flavour
mix; both are idempotent.

### 3. Build the UI and run

```bash
npm run build --prefix web
python -m uvicorn server.main:app --port 8000
```

Open **http://localhost:8000**. The first start takes ~20–40 s while the store
builds; `GET /api/health` answers `{"status":"loading"}` until it reports `ok`.

On macOS / Linux, `scripts/start.sh` does both steps and rebuilds the UI only
when the source is newer than `web/dist`.

### Hot reload while editing the UI

```bash
python -m uvicorn server.main:app --port 8000   # terminal 1
npm run dev --prefix web                        # terminal 2 → http://localhost:5173
```

Vite proxies `/api` to port 8000. Python changes need a server restart; for the
single-port app at :8000, re-run `npm run build --prefix web` after UI changes.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port used by `scripts/start.sh` and on Azure |
| `MAGNUM_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API cross-origin (the built app is same-origin and needs none) |
| `UBER_ADAPTER_ENABLED` | `false` | Feature flag for the stubbed Uber integration — leave off |

---

## API overview

All routes are under `/api`; the compiled UI is served at `/`.

| Area | Routes |
|---|---|
| Health and metadata | `GET /health` · `/meta` · `/catalog` · `/reasons` · `/context/options` · `/demo/profiles` |
| Context | `POST /context/resolve` · `POST /context/sensitivity` (what-if sweep) |
| Shopping decisions | `POST /search` · `/cart/recommend` · `/offers/decide` · `/notify` · `GET /reorder/{customer_id}` |
| Demand and stock | `GET /forecast` · `/forecast/network` · `/inventory/{store_id}` |
| Impact | `GET /impact?recovery=&scale=&sub_save=` |
| Analysis | `GET /analysis/overview` · `/uplift` · `/policy-eval` · `/forecast-accuracy` · `/demand-drivers` · `/stockouts` · `/validation` · `/clusters` |
| Customer | `GET /customer/{customer_id}/analytics` |
| Data explorer | `GET /data/tables` · `/data/table/{name}` |
| Events and demo | `POST /events` · `GET /events/recent` · `POST /demo/reset` |
| Integrations | `GET /integrations/uber/status` (stub, disabled) |

Interactive docs are at `/docs` when the server is running.

---

## Deploying to Azure

`scripts/deploy_azure.sh` is the whole procedure and is idempotent: rebuild the
UI, zip only what the app needs (`server`, `magnum_core`, `generator`,
`data/magnum.db`, `data/data_quality.json`, `web/dist`, `requirements.txt`,
`scripts/azure_startup.sh`), push it, and wait for `/api/health` to report `ok`.

```bash
az login
RG=rg-magnumnow-demo-ci APP=magnum-now-demo-v2 bash scripts/deploy_azure.sh
```

App Service settings the app relies on: Python 3.11, startup command
`bash scripts/azure_startup.sh`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`,
`WEBSITES_CONTAINER_START_TIME_LIMIT=600`, `UBER_ADAPTER_ENABLED=false`.

Notes that cost time to learn (details in BUILD.md §23):

- **Keep one worker and one instance.** The store is in-process memory over a
  read-only SQLite file (~0.6 GB per app).
- **Zip with forward slashes.** A zip built with Windows `\` paths does not
  extract into folders on Linux; package with Python's `zipfile` or from Git Bash.
- **Don't change app settings while a deploy is in flight** — it restarts the
  deployment container and kills the push.
- Both `magnum-now-demo` and `magnum-now-demo-v2` run on the same
  `asp-magnumnow-demo` B2 plan in `rg-magnumnow-demo-ci`; deploying to one
  does not touch the other.

---

## Ground rules held throughout

- **Synthetic only.** The generator writes every row. Nothing is scraped,
  licensed or imported.
- **No secrets.** No tokens, OAuth credentials, production IDs or personal
  emails in source, logs or deliverables.
- **Held-out tables.** `latent_traits` and `ground_truth` are evaluation-only.
  The application never reads them; the data explorer returns `403` for both.
- **Uber adapter is off.** `/api/integrations/uber/status` is a stub behind
  `UBER_ADAPTER_ENABLED`, default `false`. Nothing in this build calls an
  external service.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Page stuck on "Starting the console…" | The server is still building its in-memory store (~20–40 s on first start). Wait for `/api/health` to say `ok`. |
| Old charts after a deploy | The browser cached the previous page. Hard-refresh with Ctrl + F5. |
| `pip install` fails building numpy/pandas | You are on a Python newer than 3.11. Create the venv with Python 3.11. |
| `data/magnum.db not found` on start | Run the three data commands in *Generate the data*. |
| UI changes don't show at :8000 | The app serves `web/dist`. Run `npm run build --prefix web`, then reload. |

---

## Further reading

- [BUILD.md](BUILD.md) — full specification, decision logic, architecture and the append-only change log
- [docs/MODEL_CARD.md](docs/MODEL_CARD.md) — evaluation and limitations
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) — presenter's script for the client demo
