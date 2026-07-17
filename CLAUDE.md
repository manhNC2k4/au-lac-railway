# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**Âu Lạc Railway** — an AI passenger revenue-management demo for Vietnam Railways (VNR): leg-splitting (cắt chặng), gap-merging (ghép chặng), and flexible pricing (giá vé linh hoạt). Everything domain-facing is **Vietnamese** — schema columns, config keys, rule IDs, enums (`che_do_gia`, `gia_cuoi`, `NGOI_MEM_DH`). Keep it that way; these identifiers are intentional, not placeholders to anglicize.

The repo has **two tiers that never touch at runtime** (this is the single most important fact — see below):

1. **`generated_data/`** — a synthetic 12-month dataset generator (`generate_data.py`, ~4 GB output, gitignored). Offline calibration source only.
2. **The MVP app** (backend + `web/`, mostly *not scaffolded yet* — see status below) — runs one golden train scenario end-to-end off a tiny committed `seed/` package.

Current physical state (17/07/2026): `generated_data/` code + `plan/` + `docs/` exist; `backend/` has DB schema + docker-compose only (no Python app yet); `demo/` has reusable analysis modules; `src/`, `web/`, `seed/`, `openapi.yaml`, `requirements.txt` are **planned, not created**.

## THE load-bearing invariant: dataset ≠ runtime

> The 12-month dataset **never connects to the app runtime. Ever.**

```
generated_data/data/*.parquet  (~4 GB, gitignored, on no one's machine)
        │  extracted ONCE, offline, before demo start
        ▼
   seed/  (~50 KB JSON — committed to git)
        ▼
  PostgreSQL  ──►  API v1  ──►  Frontend
```

- No app request path ever does `import pandas`. Parquet is an offline analysis tool, not a database.
- `seed/` is **built from spec, not extracted** from the dataset (40 seats ≠ 448, 8 stations ≠ 22 → any extract is a lossy downsample; the golden gap must be constructed deliberately). Dataset only *calibrates the numbers* in `seed/` (lead-time dist, load factor/leg, fare-by-distance), never copied.
- Consequence: the golden path never blocks on the generator running. Only the seed-extractor role needs the 4 GB data or pandas.

## Golden scenario (shared constants — every module uses these)

- `service_run_id = SE1_2026-06-15_LE`, run date **2026-06-15** (this is in **AI** pricing regime, post the 2026-05-01 break — not LUAT).
- **8 stations / 7 legs**, `segment_id ∈ {1..7}`, **1-based everywhere** (never 0-based, including seeds). `seat_plan` uses `[segment_from, segment_to]` **inclusive**.
- **40 seats** class `NGOI_MEM_DH`, `seat_id` format `C{2-digit car}-S{3-digit seat}` → `C01-S001`…`C01-S040`.
- Golden gap: seat `C01-S017` is SOLD L1–L2, **FREE L3–L4 (THO→DHO)**, SOLD L5–L7. The demo request `THO→DHO` is what the baseline rejects and Âu Lạc serves on one seat across two legs.

## Hard invariants (cheap to violate, expensive to find late)

- **`_ground_truth/` is poison at runtime.** `demand_true`, `wtp`, `offline_optimum.bid_price` are scoring-only. CI gate: `grep -r "_ground_truth" src/` must be empty. The MVP computes its own bid price at runtime (Master Plan §2.1) — call it "demo bid-price approximation", never claim EMSR-b.
- **Social-policy (CSXH) discounts apply LAST, use `max` not product.** Điều 40 NĐ 16/2026: discount is on the actual (post-dynamic) selling price; one highest discount per ticket, never stacked. Wrong operator order = wrong revenue *and* wrong entitlement.
- **Money is `int64` đồng**, `round_to_1k` at every exit. No floats (they break floor/cap auditing).
- **`PricingContext` must not see `PassengerSafetyContext`** — pricing cannot know elderly/disabled/lone-minor status, nor `so_lan_tim_kiem`, `user_id`, device, IP, purchase history. Enforced by test (`test_price_invariant_to_search_count`, `test_pricing_features_exclude_sensitive`), not by who writes the code.
- **Central version invariant.** Every step of one offer uses the *same* `service_run_id`, `matrix_version`, `forecast_version`, `policy_version`. The frontend never composes a business decision from separate allocation/merging/pricing responses — the backend returns the completed decision.
- **Dataset has two deliberately out-of-tolerance moments** (M8b Tết/year ratio, M9 Apr load factor) — accepted on purpose, documented in `generated_data/README_data.md`. Do **not** "fix" the dataset in scope. Golden path (15/06, not Tết) is unaffected.

## Decision pipeline (fixed order)

`load consistent snapshot → map O-D to leg span → find continuous same-seat option → base O-D fare → scarcity price → hard guardrail (floor/ceiling/max-delta/round-1k/freeze) → compare final fare vs Σ leg bid-price → immutable Offer (no seat held) → POST /holds CAS all cells in ONE txn (any fail ⇒ rollback all) → idempotent HELD→SOLD confirm reusing the hold's exact price/plan → append DecisionRecord`.

## Commands

Backend DB + migrations (already exist; **do not recreate** — service is named `db`, postgres:15-alpine, Flyway V1/V2):

```bash
cd backend && docker compose up -d db flyway   # postgres on :5432, aulac_user/aulac_password/aulac_db
```

Dataset generator (only the extractor role needs this; requires numpy/pandas/pyarrow/yaml, optionally scipy + lunardate):

```bash
cd generated_data
python generate_data.py                                      # full 12 months (~30–90 min, unmeasured)
python generate_data.py --start ... --end ... --skip-lp      # subset / skip LP
```

Reusable demo analysis (read `data/` only, gitignored so needs a local dataset):

```bash
python demo/ssm/seat_state_matrix.py --date 2026-05-20 --trains SE1,SE7
python demo/build_forecast_features.py          # → demo/features/*.parquet
python demo/eda_dataset_for_5_subproblems.py    # calibration numbers for seed/
```

There is no app build/test runner, `requirements.txt`, venv, or `openapi.yaml` yet — the first backend task creates them.

## Reuse before rewriting (already built — do not reimplement)

| File | Provides | For |
|---|---|---|
| `demo/ssm/ssm_contract.py` | Frozen SSM contract: `MACRO_CLASS`, cell states, `SeatStateMatrixAPI` Protocol | backend state layer |
| `demo/ssm/seat_state_matrix.py` | In-memory seat×segment model + atomic `first_fit`/`assign` — **port to Postgres, keep semantics** | backend state layer |
| `demo/build_forecast_features.py` | Leakage-safe pickup features, `U_FORECAST=14`, 01/05 split, MASE | forecast |
| `demo/eda_dataset_for_5_subproblems.py` | Calibration numbers for `seed/` | seed extractor |
| `generate_data.py` class `Pricer` (~line 404) | **Correct legal pricing order**: F0 → δ → clip floor/ceiling → CSXH `max` last. Copy the logic, not the batch structure (MVP is per-request) | pricing |
| `generate_data.py` `solve_dlp_and_bid_price` (~line 544) | DLP reference for bid-price approximation | bid price |
| `generated_data/Synthetic_DATA_guide/04_THAM_SO_CAU_HINH_MO_PHONG.yaml` | **Single source of truth for all numbers**: `kappa0`, `theta`, `varsigma`, `gia_neo`, `diem_gay_che_do` | pricing, seed |

## Authority of documents (read in order; each constrains the next)

- `plan/00_MASTER_PLAN.md` — the operative build plan (5 devs / 30h): scenario constants, traps, `seed/` contract, file ownership, timeline. **Start here.**
- `plan/AuLac_Railway_Final_Plan_Review.md` — the locked contract the master plan links to.
- `docs/API_Contract.md` — REST v1 draft (endpoints, error codes, canonical JSON). Base `/api/v1`. Truth source is `openapi.yaml` once BE1 freezes it; on conflict, openapi wins.
- `generated_data/CLAUDE.md` + `generated_data/Synthetic_DATA_guide/*.md` — dataset-generator spec only. The four guide docs are the *dataset's* spec, not the *app's*; read only to look up a parameter.

## API v1 surface (see `docs/API_Contract.md` for shapes)

`POST /demo/scenarios/{id}/reset` (deterministic, returns checksum + all versions) · `POST /demo/forecasts/refresh` · `GET /demo/{overview,seatmap,analytics}` (read-only) · `POST /offers` (returns 3-tier price breakdown + per-leg bid + 4 versions + expiry; **holds no seat**) · `POST /holds` (`Idempotency-Key`, `expected_matrix_version`, all-or-nothing CAS) · `POST /bookings/{hold_id}/confirm` (never re-prices; idempotent; 410 if expired) · `POST /backtests` + `GET /backtests/{id}` (≥5 seeds, median + range) · `GET /decisions/{id}`.

Enums: `SeatState FREE|HELD|SOLD` · `OfferDecision ACCEPT|REJECT` · `HoldStatus ACTIVE|CONFIRMED|EXPIRED|CANCELLED`. Errors: `NO_SAME_SEAT_OPTION, SOLD_OUT_TRUE, ALLOCATION_REJECTED(422), STALE_SNAPSHOT, SEAT_CONFLICT(409), OFFER_EXPIRED, HOLD_EXPIRED(410), POLICY_UNAVAILABLE(503)`. Never silently fall back to a default price — fail closed with 503.

## Conventions specific to this repo

- **File ownership is enforced** (Master Plan §5.1) — one owner per path; a contract change needs an impact list + BE1 approval. `plan/progress.md` is append-only (every dev appends on each P0 done; never edit another's line).
- **Vietnamese in domain code, English in infra/prose is fine.** Rule IDs like `R_HE2026_XA_NGAY` are load-bearing audit strings.
- Timestamps are the scenario's **demo clock** (2026-06-15 UTC), not wall time.
- Windows/PowerShell is the primary shell; bash `&` backgrounding does not apply — use `Start-Process` or a separate terminal to run the generator.
