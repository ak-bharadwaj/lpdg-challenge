# RESQ-MLOps: LPDG Innovation Hub Selection Challenge 2026 (Track F)

Contract-governed MLOps lifecycle system for smart meter gateway risk scoring, field visit prioritization, and verified atomic model transitions.

---

### 6–8 Minute Walkthrough Video

[Watch the unlisted walkthrough](https://drive.google.com/file/d/1nhDNCVTOJcUWqhECWM5fvCwlnSp2hyIt/view?usp=sharing)

- **External Video**: The walkthrough is hosted externally on Google Drive as an unlisted video (runtime: 6:30). In strict compliance with challenge guidelines, no bulky video binaries (`.mp4`) are committed to the git repository.
- **Verbatim Cue-Sheet & Script**: [`docs/recording/WALKTHROUGH_SCRIPT.md`](docs/recording/WALKTHROUGH_SCRIPT.md) (complete minute-by-minute dialogue, console navigation, and command cue-sheet).
- **Live Evaluator Rehearsal Runbook**: [`docs/recording/LIVE_OPERATOR_REHEARSAL.md`](docs/recording/LIVE_OPERATOR_REHEARSAL.md) (authoritative live session execution runbook and PowerShell reference card).

#### Walkthrough Storyline & Console Progression

1. **0:00 – 1:00: Operations Baseline & Lifecycle Governance**: Operations Manager responsibility allocating the €45,600 technician budget (15 visits/week across 8 challenge weeks); baseline status check via `make ops-status` establishing certified baseline `v0001`, clean working tree, and verified artifact/schema contracts.
2. **1:00 – 2:15: Reviewer Verification & Canonical Entry Point**: Clean clone execution via literal `make run` ingesting telemetry under the Monday 00:00 UTC temporal firewall, generating `predictions.csv` (120 dispatches across 8 weeks), and passing official `validate_submission.py: OK`.
3. **2:15 – 3:30: Operations Cockpit & Top-15 Dispatches**: Console `#operations` view and `make ops-predictions`; clean integer scores (`43`, `26`, `23`) rendered for technician legibility (with exact 6-decimal precision preserved in `predictions.csv`), and uncompromised decision audit reasons.
4. **3:30 – 4:45: Model Governance & Rejection of `v0002`**: Console `#governance` view and `make ops-evaluate CANDIDATE=v0002`; gate decision `GATE: REJECT` with status `DECISION FINAL`. Explains that while `v0002` reduced missed broken weeks from 71 to 60 in historical retrospective backtesting, Section 8 grouped holdout evaluation on 59 unseen physical gateways regressed (18 vs 17 missed broken weeks). Rejection is a successful safety outcome preserving baseline `v0001`.
5. **4:45 – 5:45: Backlog Fleet Risk & Deferral Intelligence**: Console `#backlog` view; capacity rationing (15 dispatched / 275 deferred), Gateway Deferral Inspector, and Rule 9A Single Ranked Object Continuity proving that a single scoring pass feeds both `predictions.csv` and `backlog_report.json`. Proxy anomaly hours represent telemetry deviation, never realized monetary savings.
6. **5:45 – 7:15: Live Model Change & Atomic Rollback Verification**: Console `#safety` view; controlled live change demonstration (`make ops-change CANDIDATE=v_promotable`), followed by authoritative operator rollback (`make ops-rollback-to VERSION=v0001`) and cryptographic replay verification (`make ops-verify`). Emphasizes that `v_promotable` is a deterministic lifecycle fixture, not evidence to promote `v0002`. Proves atomic pointer switch under 1ms and bit-for-bit replay equality.
7. **7:15 – 8:00: Empirical Fleet Boundaries & Operational Roadmap**: [`LIMITATIONS.md`](LIMITATIONS.md) disclosure of the 12 unprovisioned gateways (3.61% blind spot) classified as `NO_TELEMETRY` rather than inventing calm scores; two-week operational delta roadmap.

---

## Reviewer Verification

### Part 1: Canonical Submission Entry Point

As specified in the Challenge Brief and Section 5A of the architecture freeze, reviewer verification requires only:

```bash
# 1. Install dependencies
pip install -r requirements.lock

# 2. Place raw challenge files in data/
# (data/telemetry, data/gateway_master.csv, data/field_visits.csv, data/meter_read_success.csv)

# 3. Run canonical submission pipeline
make run
```

`make run` executes the canonical submission pipeline:
1. Validates the environment and ingests master data under CP1252 encoding with single-path ID normalization.
2. Ingests telemetry strictly before the Monday 00:00 UTC temporal firewall for each challenge week.
3. Scores eligible gateways with active production baseline `v0001` across all 8 challenge weeks (2026-02-02 through 2026-03-23).
4. Emits `predictions.csv` (strictly 120 dispatches: 8 weeks × 15 top visits) and `backlog_report.json` (deferred risk ranking).
5. Executes the official challenge submission validator:
   ```bash
   python validate_submission.py predictions.csv
   ```
   Output: `predictions.csv: OK`

### Part 2: Unified MLOps Lifecycle in the Same Project

Part 2 is not a detached repository or separate deliverable; it is the production MLOps governance layer built directly into this project. Reviewers can verify the complete operational lifecycle using authoritative operator commands:

```powershell
# Read-only operator status summary
make ops-status

# Read-only safety preflight check
make ops-preflight

# Live prediction inspection for operator week
make ops-live
make ops-predictions

# Candidate evaluation against frozen promotion gate (v0002 rejection)
make ops-evaluate CANDIDATE=v0002

# Controlled candidate change demonstration (v_promotable fixture)
make ops-change CANDIDATE=v_promotable

# Authoritative operator rollback to certified baseline v0001
make ops-rollback-to VERSION=v0001

# Bit-for-bit replay equality verification
make ops-verify
```

---

## Testing & Verification

- **Full Regression Suite**: Latest verified run passes **331 passed** (0 failed, 0 skipped) across all unit, integration, and contract tests (`python -m pytest tests/`).
- **Official Submission Validator**: `python validate_submission.py predictions.csv` validated with status `OK`.
- **Certified Baseline State** (`make ops-status`):
  - **Active Model**: `v0001`
  - **Registry State**: `PASS` (`registry/active.json`)
  - **Artifact Integrity**: `PASS` (SHA-256: `19baaf437a2e6158fe4cbb542ddc7a7a61474076d74839eaea932d4d3c94ff5f`)
  - **Schema Contract**: `PASS` (`models/v0001/schema.json`)
  - **Git Working Tree**: `CLEAN`
- **Core Governance Invariants**:
  - **Monotonic Temporal Authority**: Zero system clock calls in core inference, ranking, and evaluation pipelines.
  - **Monday 00:00 UTC Temporal Firewall**: Telemetry strictly filtered strictly before cutoff timestamp (`ts < cutoff_utc`).
  - **Single Canonical ID Normalizer**: Authoritative uppercase 12-hex representation (`^[0-9A-F]{12}$`) across master, visits, and telemetry.
  - **Atomic Registry Transitions**: Sub-millisecond atomic swaps of `registry/active.json` with compensating transactional rollback.

---

## Key Governance & Factual Distinctions

1. **`v0002` Gate Rejection**: Candidate `v0002` was rejected because the Section 8 grouped holdout evaluation on 59 unseen physical gateways regressed (missing 18 broken weeks versus 17 under baseline `v0001`). Rejection is an authoritative safety success.
2. **Retrospective Development Result (71 $\to$ 60)**: The reduction from 71 to 60 missed broken weeks is an internal retrospective development proxy across historical backtest windows (November 2025 – January 2026), NOT hidden challenge performance.
3. **`v_promotable` Fixture Purpose**: `v_promotable` is a dedicated, deterministic lifecycle fixture used exclusively to demonstrate candidate promotion and atomic rollback. It is NOT evidence that `v0002` should be promoted and carries no production performance claims (see [`DECISIONS.md`](DECISIONS.md) Section 4 and [`MLOPS.md`](MLOPS.md)).
4. **Backlog Proxy Hours**: Proxy anomaly hours in `backlog_report.json` reflect telemetry deviation across deferred gateways under capacity rationing—they are never presented as realized euro savings.

---

## Core Architecture & Operator Commands

| Command | Lifecycle Phase | Description |
| :--- | :--- | :--- |
| `make run` | Submission / P0 | Canonical reviewer entry point: runs inference and validates `predictions.csv`. |
| `make ops-status` | Monitoring / Audit | Read-only inspection of active model, artifact integrity, schema contract, and git state. |
| `make ops-preflight` | Safety Preflight | Read-only validation of active package, data directory, live week, and schema contracts. |
| `make ops-live` | Live Inference | Generates live dispatches and backlog report for arbitrary operator week (`LIVE_WEEK`). |
| `make ops-predictions`| Output Validation | Strictly inspects and validates the live prediction artifact table and provenance. |
| `make ops-evaluate` | Governance Gate | Evaluates candidate model against multi-window rolling and grouped holdout policy. |
| `make ops-change` | Model Transition | Authoritative candidate promotion through frozen gate (`CANDIDATE=...`). |
| `make ops-rollback-to`| Atomic Rollback | Restores target model with target validation, atomic pointer swap, and replay proof. |
| `make ops-verify` | Replay Verification | Read-only double-inference pass proving bit-for-bit replay hash equality. |
| `make test` | Quality Assurance | Executes full automated test suite (331 tests). |

---

## Project Structure

```
lpdg-challenge/
|-- app/
|   |-- data/          # Ingestion, CP1252 parsing, ID normalization, eligibility, quality guards
|   |-- features/      # Feature extraction, holdout splitting, Monday 00:00 UTC firewall
|   |-- model/         # v0001 baseline & v0002 candidate inference, ranking, tie-breaking
|   |-- registry/      # Filesystem registry, promotion gate policy, atomic rollback engine
|   `-- monitoring/    # Structural schema drift monitor and reporting
|-- scripts/
|   |-- ops.py         # Authoritative operator CLI (status, preflight, live, evaluate, change, rollback)
|   |-- make_submission.py # Canonical Part 1 entry point for predictions.csv generation
|   |-- predict.py     # Batch and single-week prediction entry point
|   |-- train.py       # Candidate model training and packaging
|   |-- promote.py     # Promotion gate CLI wrapper
|   |-- rollback.py    # Standalone rollback CLI wrapper
|   `-- check_drift.py # Structural schema drift verification
|-- models/            # Immutable model packages (v0001, v0002, v_promotable)
|-- registry/          # active.json, history.jsonl
|-- policy.json        # Frozen promotion policy (10% threshold, holdout agreement, no regression)
|-- tests/             # Automated test suite (unit, integration, contracts)
|-- docs/
|   `-- recording/
|       |-- WALKTHROUGH_SCRIPT.md     # Verbatim 6–8 minute recording script & cue-sheet
|       `-- LIVE_OPERATOR_REHEARSAL.md # Authoritative live evaluator execution runbook
|-- DECISIONS.md       # Architectural decisions and governance rationale
|-- MLOPS.md           # Detailed system design, contracts, and state machines
|-- LIMITATIONS.md     # Measured fleet boundaries (12-gateway blind spot)
`-- AI-USAGE.md        # AI assistance disclosure and verification log
```
