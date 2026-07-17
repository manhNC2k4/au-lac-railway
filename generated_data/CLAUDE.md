# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Specification-only. No code, no build system, no git. Four documents in `Synthetic_DATA_guide/` define a **synthetic dataset generator** for Vietnam Railways (VNR) passenger revenue management — leg-splitting (cắt chặng), gap-merging (ghép chặng), and flexible pricing (giá vé linh hoạt).

Everything is in Vietnamese: prose, schema columns, config keys, rule IDs. **Keep it that way** — code identifiers in the spec (`chuyen_id`, `khu_gian`, `gia_cuoi`, `che_do_gia`) are the intended names, not placeholders to anglicize.

Data cutoff for all facts: **2026-07-17**.

## Documents and their authority

Read in order; each constrains the next.

| File | Role | Authority |
|---|---|---|
| `01_BAO_CAO_TINH_HINH_THUC_TE.md` | Real-world facts: VNR financials, timetable, pricing rules, disaster events, legal framework | **Ground truth.** Every number traces to a cited source (§8). Do not invent or adjust. |
| `02_TOAN_HOC_HOA_XAY_DUNG_DATASET.md` | The data-generating process: gravity → mode logit → NHPP → nested logit → pricing/inventory loop | Math contract. Theorems 1–2 (§1.2, §1.3) drive the whole algorithmic design. |
| `03_QUY_TRINH_VA_KHUYEN_NGHI_KY_THUAT.md` | Build plan: 12 steps, directory layout, SQL DDL, QA gates, eval protocol, tech stack | Implementation spec. §5.2 is the schema; §12 is the test suite to write. |
| `04_THAM_SO_CAU_HINH_MO_PHONG.yaml` | Every numeric parameter | **Single source of truth for numbers.** A value changed in prose but not here (or vice versa) is a bug. |

`04`'s tags are load-bearing and appear nowhere else: `[THẬT]` sourced fact — never a free parameter; `[NEO]` constant derived by division from sourced facts; `[FIT]` free, estimated by SMM; `[GIẢ]` assumption needing sensitivity analysis. Before touching any number, check its tag — retuning a `[THẬT]` to make a fit converge is falsifying the calibration.

## The architecture in one paragraph

Exogenous inputs (calendar, weather, events, fuel price) drive latent O–D demand `Λ`, which emits a non-homogeneous Poisson request stream, which passes through a nested-logit choice model, which **feeds back into** pricing and inventory state and back into choice. That feedback loop is the point: price and seat availability at booking time `u` depend on sales history, and in turn drive purchase probability. Output splits in two — `data/` (observable, given to models) and `_ground_truth/` (true `Λ`, per-customer WTP, offline optimum; **scoring only**). A train-run is not one product; it is 231–595 O–D products sharing one seat inventory.

## Invariants that span multiple documents

These are the ones that are cheap to violate and expensive to discover late.

**Two policy regime breaks.** `2026-05-01` VNR switched on real AI flexible pricing (15–35% discount on unsold short legs); `2026-05-15` online refunds launched. Training across either without a `che_do_gia` / regime flag learns the average of two different policies. Full break list: `04` §4 `diem_gay_che_do`.

**Ground truth never touches features.** `03` §1 mandates a CI check: `grep -r "_ground_truth" src/ && exit 1`. Forbidden feature list at `03` §6.3.

**Social-policy discounts apply LAST and use `max`, not product.** Legal basis is Điều 40 Nghị định 16/2026/NĐ-CP: the discount applies to the actual selling price, i.e. after dynamic pricing. Beneficiaries get one highest discount, never stacked. Wrong operator order = wrong revenue *and* wrong passenger entitlement. Hard constraint, not a soft penalty.

**The incidence matrix is totally unimodular** (`02` §1.2, Theorem 1) — journeys cover consecutive segments, so the LP relaxation is already integral. Never reach for MILP on the quota core; HiGHS solves a train in <10ms. This is what makes the p95 < 200ms target reachable.

**Split by `ngay_chay` with a 169-day embargo, never by `thoi_diem_mua`, never randomly.** Tết tickets sell up to 169 days ahead, so buy-time splits leak across the booking horizon. `03` §9.1 calls this the subtlest trap in the spec.

**Calendar variables are lunar-relative.** Use `tau = D − mùng1(year)`, not month-of-year: Tết moves 21 days between 2025 (Jan 29) and 2026 (Feb 17), so "February" is post-Tết one year and pre-Tết the next. Same for lag features — `q_lag_364` means same lunar day, not same calendar day.

**Stations are SCD Type-2 by province.** Vietnam's 01/07/2025 merger to 34 provinces moved Tuy Hòa from Phú Yên to Đắk Lắk. Any population/tourism join must be an as-of join by date or every gravity variable breaks from that date on.

**Money is `int64` đồng.** Floats break floor/cap auditing.

**Disruptions block segments; they never cancel randomly.** A ticket is hit iff its journey `(i,j]` intersects the blockaded km range. This is what reproduces the selection effect — the Nov 2025 flood's average refund (615k) exceeds the annual average fare (514k) because long-distance tickets get hit more. If your simulated refund average ≈ the fare average, you cancelled uniformly and it's wrong.

**Cancellations are the supply side of gap-merging.** No refund model → no gaps → the merging problem does not exist.

## Calibration constants that gate everything

18 moments (M1–M18) in `04` §12, targets <5% relative error for M1–M9. The diagnostic ones:

- **M5 ≈ 514,000 đ** average fare per passenger; **M8 ≈ 714,000 đ** at Tết.
- **M8b = 1.39** — the strongest check in the spec. Tết fares rose only 4–5%, so ≥32 points of that 39% gap must come from **mix shift** (distance distribution moving toward >900km), not from raising prices. A simulation that hits M8 by raising prices is wrong even though the moment matches.
- **M14 = 615,000 đ** flood refund average, must exceed M5 (ratio target 1.10–1.40).
- **M15 = 20.7%** AI discount share of gross revenue. Note `04` §11 flags that VNR's published "10.36% of passengers" figure is inconsistent by division and must not be used as a constraint — anchor on 20.7% and the ~213,000 đ average discounted fare instead.

## When code starts

Nothing is scaffolded. `03` §1 fixes the layout (`ref/` real data → `rules/` declarative pricing rules → `config/` → `sim/` → `data/` + `_ground_truth/` → `features/` `baselines/` `eval/` `qa/`), and §11 the stack: Python + NumPy/Numba, HiGHS for LP, OR-Tools CP-SAT for group seating, Parquet + DuckDB, LightGBM (Poisson/Tweedie), EconML/DoubleML, pandera or Great Expectations for the DQ gates.

Two structural rules from the spec:

- **Pricing rules are declarative config, not Python.** `rules/pricing_rules.yaml` (`03` §3). Rules change every season, the brief requires policy-change logs and rollback, and the rule engine's per-pricing record *is* the audit trail and the XAI explanation.
- **Steps 1–4 are truth-gathering; 5–7 are simulation.** `03` §0 warns that writing the simulator before collecting reference data means rewriting it.

Test names to implement are enumerated in `03` §12 — physical invariants, legal compliance, calibration, leakage. No test runner is chosen yet.

## Open question

`ref/bieu_gia_co_ban.csv` is meant to be scraped from dsvn.vn (`03` §2.2, ≤1 req/s, respect robots.txt). Until then, per-seat-count and specific fare figures in `01` §2.3 come from agents/aggregators, not VNR directly, and `01` §8 flags them as needing replacement before final calibration.
