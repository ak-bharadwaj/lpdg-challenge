# System Limitations & Operational Boundaries (LIMITATIONS.md)

Written for the Operations Manager, Dispatch Planners, and Engineering Leadership.
In strict accordance with Challenge Part 1 deliverables and ARCHITECTURE_v25_FREEZE.md Sections 14 and 18.

---

## 1. Measured Telemetry-Coverage Blind Spot (Fleet Non-Coverage)

- **Audited Fleet Measurement**:
  - **Total Fleet Size**: 332 smart meter gateways registered in `gateway_master.csv`.
  - **Active Reporting Fleet**: 320 gateways have at least one valid telemetry record.
  - **Institutional Blind Spot**: **12 gateways (3.61% of fleet)** have **zero historical telemetry records** across the entire operational recording period.
  - **Affected Gateway Identifiers**:
    `02BCBAD30D53`, `02E1C70E46D1`, `02F25E3EAE98`, `0686FFF4B846`, `06C662180A40`, `06F44C2A64BD`, `06FEDE0E7789`, `0AD39BC595EF`, `0AEF2E5A50F0`, `0E4056A2CD08`, `0E8417B08FC9`, `0ED11B64810A`.
- **Operational Handling & Impact**:
  - Per Section 2B and Rule 6, these units are strictly classified as `NO_TELEMETRY` and excluded from scoring rather than fabricated as "calm" (zero anomaly risk).
  - In the 8 scored submission weeks (February 2, 2026 through March 23, 2026), eligible fleet count expands from 290 to 308 gateways. Exactly 1 gateway experienced recent silence in each of weeks 2026-02-09, 2026-03-02, and 2026-03-09; these were scored using the candidate silence penalty.
  - **Limitation**: The system cannot detect degradation on the 12 uninstrumented gateways. Dispatching technicians to these units requires external cellular provisioning audits rather than algorithmic telemetry scoring.

---

## 2. Retrospective Degradation Detection vs Leading Onset Forecasting

- **Limitation**: The scoring engine detects already-degraded gateways based on accumulated retrospective evidence (chronic reboot loops, elevated disconnect counts, multi-day cellular silence) over a 28-day baseline and 7-day recent window. It does **not** forecast degradation weeks before symptoms manifest.
- **Economic Consequence**: Because €600 accrues each week a gateway remains broken, detecting degradation only after persistence incurs 1–2 weeks of fault penalty before dispatch occurs.
- **Rationale**: Development period data (`field_visits.csv`) reliably supports retrospective audit of established failures, but lacks high-frequency precursor labeling required for statistical onset hazard estimation.

---

## 3. Operational Selection Bias in Historical Field Visits

- **Limitation**: Historical ground-truth evidence in `field_visits.csv` only records gateways that operational personnel already chose to inspect.
  - Of 628 historical visits through January 31, 2026, 382 visits (60.8%) were false alarms (`Kein Fehler gefunden`).
  - Only 218 visits involved confirmed physical component replacements (`Fehler behoben`).
  - Crucially, no record exists for gateways that failed silently and were never inspected by technicians.
- **Operational Consequence**: Any simulated cost-avoidance metric (€600/week fault penalty delta) measures precision-oriented performance on observed operational dispatches under an internal retrospective proxy, with zero fleet-wide recall guarantees. All reported figures were dynamically recomputed from the supplied data; the field-visit evaluation is explicitly treated as a selection-biased retrospective proxy.
- **Pre-Cutoff Meter-Read Evidence**: The latest available pre-cutoff week is 2026-01-26 (as meter_read_success.csv ends on 2026-01-26; no 2026-02-02 meter data exists), where dispatched gateways had an 18.76 percentage-point lower mean meter-read success rate (66.87% vs 85.63%).
- **Engineer Review Subset**: Of the 120 dispatched gateways, 27 were present in the independent engineer review audit (ngineer_review_2026-02.xlsx). 12 were rated *Schlecht* (confirmed hardware defect) and 3 *nach Tausch stabil* (recent physical replacement), representing 15 / 27 = 55.6% of the reviewed subset (not a fleet-wide confirmation).

---

## 4. Structural Schema Validation vs Continuous Concept Drift

- **Limitation**: Structural schema correctness (column presence, strict dtypes, timestamp granularity, and fleet-wide absence rate) is monitored by `scripts/check_drift.py` (`make drift`) and enforced at the ingestion boundary (`app/data/schema.py` and `app/data/quality.py`). However, the system does not track continuous multivariate statistical concept drift (e.g. Population Stability Index or Wasserstein distance across all 57 raw telemetry signals).
- **Operational Consequence**: Subtle fleet-wide environmental degradation or gradual firmware distribution shifts that do not break schema constraints will not trigger a drift alert.

---

## 5. What Two Additional Weeks of Operational & Engineering Time Would Change

If granted two additional weeks of engineering and operational development time, the following enhancements would be prioritized directly based on our empirical Part 1 audit findings:

1. **Fresh Meter-Read Telemetry Ingestion & Lag Elimination**:
   - Ingest synchronized meter-read telemetry post-January 26, 2026 to eliminate the static snapshot lag in `meter_read_success.csv`.
   - **Operational Benefit**: Resolves whether deferred gateways with read rates under 80% (such as `0A55DA266F71`) persisted in customer-impacting failure states or recovered naturally.

2. **Dual-Channel Silence & Blackout Detection**:
   - Implement an authoritative missingness detector that flags sustained telemetry communication blackout (e.g. >48 consecutive missing hourly records) as an independent high-severity dispatch trigger.
   - **Reliability Benefit**: Eliminates the 3-sigma baseline's "silent failure blindness," preventing completely dead gateways (such as `02423E0E6E9F`, which had 91–113 missing hours and confirmed physical repairs) from dropping to ranks 64–202.

3. **Customer Revenue & Billing Exposure Calibration**:
   - Jointly optimize dispatch priority by weighting anomaly persistence with unread meter exposure ($\text{unread\_meters} = n\_meters \times (1 - \text{read\_rate})$).
   - **Economic Benefit**: Prioritizes high-density gateways (>400 meters) in partial failure over low-density gateways (<50 meters) with minor intermittent blips, directly protecting utility billing SLAs.

4. **Lead-Time Pre-Failure Hazard Modeling & Blind-Spot SIM Audit**:
   - Fit a calibrated survival analysis model on confirmed hardware repair episodes to predict failure 7–14 days prior to collapse.
   - Audit mobile carrier SIM provisioning to diagnose and bring online the 12 zero-telemetry blind-spot units (3.61% of fleet).

---

## 6. Model Rollback Demonstration via Committed Fixture (`v_promotable`)

- **Limitation**: In real candidate evaluation against actual challenge data, candidate `v0002` failed the promotion gate due to holdout disagreement (`REJECT_GROUPED_DISAGREEMENT`: 71 → 60 development, but 17 → 18 holdout regression) and was never deployed to production. Production remained safely anchored on baseline `v0001`. Consequently, a production rollback from `v0002` cannot and must not occur.
- **Operational Handling**: To verify that the atomic rollback machinery (`scripts/rollback.py`, `make rollback`, `make ops-rollback-to`) functions correctly under production failure conditions, the repository provides a committed, deterministic model package fixture: `v_promotable` (`models/v_promotable`). `v_promotable` is a **deterministic rollback-demo fixture whose promotion decision is intentionally preconstructed for lifecycle rehearsal**. Its synthetic evaluation numbers (e.g. synthetic holdout 17 → 14) are **not production model performance**, **do not represent the official hidden-ground-truth score**, and **are not evidence that `v0002` should be promoted**.
- **Governance Separation**:
  - **REAL CANDIDATE**: `v0002` → `REJECT_GROUPED_DISAGREEMENT` (production remains securely on `v0001`)
  - **ROLLBACK FIXTURE**: `v_promotable` → deterministic `PROMOTE` fixture used strictly to exercise rollback and bit-for-bit replay recovery without compromising production governance.
