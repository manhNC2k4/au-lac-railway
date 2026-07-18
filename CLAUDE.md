# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**Âu Lạc Railway** — an AI passenger revenue-management demo for Vietnam Railways (VNR): leg-splitting (cắt chặng), gap-merging (ghép chặng), and flexible pricing (giá vé linh hoạt). Everything domain-facing is **Vietnamese** — schema columns, config keys, rule IDs, enums (`che_do_gia`, `gia_cuoi`, `NGOI_MEM_DH`). Keep it that way; these identifiers are intentional, not placeholders to anglicize.

The repo has **three tiers** that must not blur together:

1. **`generated_data/`** — a synthetic 12-month dataset generator (`generate_data.py`, ~4 GB output, gitignored). Offline calibration source only.
2. **`app/` + `models/` + `eval/`** (repo root) — a separate, frozen-contract offline implementation of the full 5-subproblem decomposition (BT1–BT5: forecast, seat-state matrix, allocation/DLP, merging, pricing). Reads `generated_data/data/` directly (needs pandas/sklearn). Produces artifacts in `models/artifacts/`, including a real trained model (`bt1_forecast_hgb.joblib`, HistGradientBoostingRegressor). This is **not** the runtime API — see `BACKEND_GUIDE.md` and `NOTE_DEV.md` for how it maps to (3).
3. **The MVP backend + `web/`** (`backend/src/`) — the actual runtime API, running one golden train scenario end-to-end off the tiny committed `backend/seed/` package. This is what `docker compose up` serves.

Tier 2 and tier 3 were built independently by different owners and later reconciled — read `NOTE_DEV.md` before assuming a number or algorithm in one matches the other (index convention, bid-price method, and pricing-rule calibration differ; see its comparison table).

## THE load-bearing invariant: dataset ≠ runtime

> **STATUS (2026-07-18): this invariant is intentionally SUSPENDED.** The golden-gap
> demo was retired for a different demo, and the runtime Postgres DB is now
> mock-loaded from one month (2026-06) of the V1-shaped export via
> `backend/scripts/load_mock_from_dataset.py` (clears + rebuilds all ~23 tables;
> deterministic; `--self-check`/`--month`/`--sold-only`). The section below
> documents the *original* design and the loader can restore it, but do NOT
> assume the DB currently holds the golden seed. See that script's header for
> what is exactly inverted vs. deterministically fabricated.

> The 12-month dataset **never connects to the app runtime (tier 3). Ever.**

```
generated_data/data/*.parquet  (~4 GB, gitignored)
        │  extracted/calibrated OFFLINE by app/ + models/ (tier 2)
        ▼
   backend/seed/  (~50 KB JSON — committed to git)
        ▼
  PostgreSQL  ──►  API v1 (backend/src)  ──►  Frontend
```

- No request path in `backend/src/` ever does `import pandas`. Tier 2 (`app/`, `models/`, `eval/`) is where pandas/sklearn/scipy live; it is an offline calibration + evidence pipeline, not a database.
- `backend/seed/` is **built from spec, not extracted verbatim** (40 seats ≠ 448, 8 stations ≠ 22 → any raw extract is a lossy downsample; the golden gap must be constructed deliberately). Dataset and tier-2 model outputs only *calibrate the numbers* in `backend/seed/`.
- CI gate: `grep -r "_ground_truth" backend/src/` must be empty. `_ground_truth/` (demand_true, wtp, offline_optimum.bid_price) is scoring-only, usable only by `eval/`/tier-2 backtest, never by runtime.

## Golden scenario (shared constants — every module uses these)

> **NOTE (2026-07-18):** the live DB no longer contains this golden run — it was
> overwritten by the 1-month dataset load (see the suspended invariant above).
> These constants still define the *reference* scenario the code and tests were
> built around; re-seed from `backend/seed/` to get them back in the DB.

- `service_run_id = SE1_2026-06-15_LE`, run date **2026-06-15** (AI pricing regime, post the 2026-05-01 break — not LUAT).
- **8 stations / 7 legs**, `segment_id ∈ {1..7}`, **1-based everywhere in `backend/`** (never 0-based). `seat_plan` uses `[segment_from, segment_to]` **inclusive**. (Tier-2 `app/bt2_ssm.py` uses 0-based half-open `[a,b)` internally — a deliberate convention difference, reconciled at the `integration/` boundary before anything reaches seed.)
- **40 seats** class `NGOI_MEM_DH`, `seat_id` format `C{2-digit car}-S{3-digit seat}` → `C01-S001`…`C01-S040`.
- Golden gap: seat `C01-S017` is SOLD L1–L2, **FREE L3–L4 (THO→DHO)**, SOLD L5–L7. The demo request `THO→DHO` is what the baseline rejects and Âu Lạc serves on one seat across two legs.

## Hard invariants (cheap to violate, expensive to find late)

- **`_ground_truth/` is poison at runtime.** Scoring-only. `/offers` computes bid price via a real DLP dual (`app/bt3_allocation.py`, live-imported through `backend/src/allocation/cache.py` + `integration/ssm_from_postgres.py` shim, cached per `(service_run_id, matrix_version, forecast_version)` — not solved per-request). Call it "DLP bid price (LP dual)", never claim EMSR-b. `backend/src/forecast/bid_price.py` (scarcity-formula approximation) still backs the offline backtest replay (`backend/src/backtest/engine.py`) only — not the live route.
- **Social-policy (CSXH) discounts apply LAST, use `max` not product.** Điều 40 NĐ 16/2026: discount is on the actual (post-dynamic) selling price; one highest discount per ticket, never stacked. Enforced in `backend/src/pricing/engine.py::csxh_apply`.
- **Money is `int64` đồng**, `round_to_1k` at every exit. No floats.
- **`PricingContext` must not see `SafetyContext`** (`backend/src/pricing/context.py`) — pricing cannot know elderly/disabled/lone-minor status, search count, device, IP, purchase history. Enforced by `__post_init__` assertion against `FORBIDDEN_PRICING_FEATURES`, not by convention.
- **Central version invariant.** Every step of one offer uses the *same* `service_run_id`, `matrix_version`, `forecast_version`, `policy_version`. The frontend never composes a business decision from separate allocation/merging/pricing responses — the backend returns the completed decision.
- **Dataset has two deliberately out-of-tolerance moments** (M8b Tết/year ratio, M9 Apr load factor) — accepted on purpose, documented in `generated_data/README_data.md`. Do not "fix" the dataset in scope.
- **Priority passengers never get a seat-change plan.** `merging/resolver.py` filters `requires_seat_change` options when `priority_passenger=True`; multi-seat merging (`integration/resolver_multiseat.py`, tier-2 supplied) is opt-in and requires explicit customer consent + disclosure UI before use.

## Decision pipeline (fixed order, `backend/src/`)

`load consistent snapshot (SeatStateManager) → merging.resolver same-seat scan → base O-D fare (fare_product) → forecast.bid_price scarcity per leg → pricing.engine (rules YAML → guardrail → CSXH max-last) → compare gia_cuoi vs Σ leg bid-price → offer.service builds immutable Offer + DecisionRecord (no seat held) → POST /holds CAS all cells in ONE txn (any fail ⇒ rollback all) → idempotent HELD→SOLD confirm reusing the hold's exact price/plan → append DecisionRecord`.

Wired in `backend/src/api/routes_offers.py`; each stage is a real module now (`merging/`, `pricing/`, `offer/`, `forecast/`), not the inline shortcut that once lived in that file (see `plan/BE_INTEGRATION_PLAN.md` T1–T6 for the migration history if the wiring looks off).

## Commands

**Backend DB + API** (Postgres 15-alpine + Flyway, service names `db`/`flyway`/`backend`):
```bash
cd backend && docker compose up -d db flyway   # postgres :5432, aulac_user/aulac_password/aulac_db
docker compose up -d                            # also builds/runs the API on :8000
curl localhost:8000/api/v1/demo/overview?service_run_id=SE1_2026-06-15_LE
```

**Backend tests** (need `db`/`flyway` running first — `conftest.py` resets the golden scenario on Postgres per test):
```bash
cd backend && pytest tests/ -v                  # full suite
cd backend && pytest tests/test_pricing.py -v   # single file
cd backend && pytest tests/test_offer.py::test_reject_when_price_below_bid -v   # single test
```

**Tier-2 model + 5-subproblem pipeline** (repo root, needs `pip install -r requirements.txt`; pandas/sklearn/scipy — never run inside `backend/`):
```bash
python models/export_bt5_params.py          # -> bt5_pricing_params.json
python models/train_bt1_forecast.py         # -> bt1_forecast_hgb.joblib (real ML) + spec + contract
python models/build_bt1_curves.py           # -> bt1_booking_curves.json
python models/estimate_elasticity.py        # -> elasticity_params.json (real ML, logistic demand curve)
python run_all.py                           # run all 5 subproblems -> models/artifacts/run_all_outputs.json
python models/make_backtest_forecast.py --cutoff 2026-02-01 --dates 2026-02-14
python eval/backtest.py --dates 2026-02-14,2026-05-20 --trains SE1,SE3,SE5,SE7
uvicorn app.api:app --port 8001              # standalone demo API for tier 2, docs at /docs (8001, not 8000 — 8000 is tier-3 backend/docker-compose)
python tests/test_invariants.py             # 9 invariants for tier-2 (guardrail, CSXH, atomicity, determinism...)
```

**Dataset generator** (only the extractor role needs this; requires numpy/pandas/pyarrow/yaml, optionally scipy + lunardate):
```bash
cd generated_data
python generate_data.py                                      # full 12 months (~30–90 min)
python generate_data.py --start ... --end ... --skip-lp      # subset / skip LP
```

There is no `web/` frontend scaffolded yet, and no repo-root build/lint runner — Python only, no package.json.

## Reuse before rewriting (already built — do not reimplement)

| File | Provides | For |
|---|---|---|
| `backend/src/state/seat_state_manager.py` | Postgres-backed seat×segment state, atomic CAS assign/hold/confirm | any state-touching change |
| `backend/src/merging/resolver.py` | `best_same_seat`/`resolve_same_seat_options` — numpy same-seat scan, best-fit ranking | offer/allocation changes |
| `backend/src/pricing/engine.py` + `context.py` | `PricingEngine` (rules YAML → guardrail → CSXH-last), `PricingContext`/`SafetyContext` split | any pricing change |
| `backend/src/allocation/cache.py` + `integration/ssm_from_postgres.py` | Live DLP bid price (`app.bt3_allocation.analyze_run`), cached per version | bid/allocation changes |
| `backend/src/forecast/bid_price.py` + `forecast.py` | Scarcity-formula approximation (backtest replay only, not live `/offers`), deterministic pickup-curve forecast | backtest/forecast changes |
| `backend/src/offer/service.py` | `OfferService.build_offer` — assembles Offer + append-only DecisionRecord with input_hash/explanation | offer pipeline changes |
| `backend/src/backtest/engine.py` | Runs committed `backend/seed/backtest/events-seed-*.jsonl`, AI vs baseline revenue | backtest/evidence work |
| `app/contracts.py` (tier 2) | Frozen dataclass contracts between the 5 subproblems (offline reference) | understanding intended shapes before they hit `backend/seed` |
| `models/artifacts/*` | Pre-trained forecast model + elasticity + backtest report (offline evidence, not loaded by `backend/`) | citing accuracy/revenue numbers in the pitch |
| `NOTE_DEV.md` | Concept↔code map between tier-2 (`app/`) and tier-3 (`backend/`), and exactly what still diverges | reconciling a number or algorithm between the two tiers |
| `generated_data/generate_data.py` class `Pricer` (~line 404) | Legal pricing order reference: F0 → δ → clip floor/ceiling → CSXH max last | pricing logic origin |

## Authority of documents (read in order; each constrains the next)

- `plan/00_MASTER_PLAN.md` — the operative build plan: scenario constants, traps, `seed/` contract, file ownership, timeline.
- `plan/BE_INTEGRATION_PLAN.md` — the T1–T6 plan that wired tier-2/tier-3 modules into the live `/offers` route (mostly executed already — diff against current `routes_offers.py` if something looks like the old shortcut).
- `NOTE_DEV.md` — what the tier-2 (`app/`) owner changed to match `backend/`, and what's still a recommended-vs-required delta (multi-seat merging, elasticity-calibrated pricing rules, model-backed forecast seed).
- `BACKEND_GUIDE.md` — how a backend would integrate the tier-2 `app/` layer directly (boot sequence, invariants, endpoints) — written for a *different* integration path than the one `backend/src` actually took; useful for the algorithm contracts, not for the current wiring.
- `docs/API_Contract.md` / `docs/TECHNICAL_OVERVIEW.md` — REST v1 draft and current technical state. Base `/api/v1`. On conflict with `openapi.yaml`, openapi wins once frozen.
- `generated_data/CLAUDE.md` + `generated_data/Synthetic_DATA_guide/*.md` — dataset-generator spec only; read only to look up a calibration parameter.

## API v1 surface (see `docs/API_Contract.md` for shapes)

`POST /demo/scenarios/{id}/reset` (deterministic, returns checksum + all versions) · `POST /demo/forecasts/refresh` · `GET /demo/{overview,seatmap,analytics}` (read-only) · `POST /offers` (returns 3-tier price breakdown + per-leg bid + 4 versions + expiry; holds no seat) · `POST /holds` (`Idempotency-Key`, `expected_matrix_version`, all-or-nothing CAS) · `POST /bookings/{hold_id}/confirm` (never re-prices; idempotent; 410 if expired) · `POST /backtests` + `GET /backtests/{id}` (runs committed 5-seed event streams, median + range) · `GET /decisions/{id}`.

Enums: `SeatState FREE|HELD|SOLD` · `OfferDecision ACCEPT|REJECT` · `HoldStatus ACTIVE|CONFIRMED|EXPIRED|CANCELLED`. Errors: `NO_SAME_SEAT_OPTION, SOLD_OUT_TRUE, ALLOCATION_REJECTED(422), STALE_SNAPSHOT, SEAT_CONFLICT(409), OFFER_EXPIRED, HOLD_EXPIRED(410), POLICY_UNAVAILABLE(503)`. Never silently fall back to a default price — fail closed with 503 (`pricing/engine.py::PolicyUnavailableError`).

## Conventions specific to this repo

- **File ownership is enforced** (Master Plan §5.1) — one owner per path; a contract change needs an impact list + BE1 approval. `plan/progress.md` is append-only (every dev appends on each P0 done; never edit another's line). Tier-2 (`app/`, `models/`, `eval/`, `integration/`) owner does **not** edit `backend/` files directly — hand-offs happen through `integration/` + `NOTE_DEV.md`.
- **Vietnamese in domain code, English in infra/prose is fine.** Rule IDs like `R_HE2026_XA_NGAY` are load-bearing audit strings.
- Timestamps are the scenario's **demo clock** (2026-06-15 UTC), not wall time (`backend/src/state/clock.py::FixedClock` in tests).
- Windows/PowerShell is the primary shell; bash `&` backgrounding does not apply — use `Start-Process` or a separate terminal to run the generator or long-running scripts.
