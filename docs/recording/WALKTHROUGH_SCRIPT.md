# 6–8 Minute Operational Walkthrough Recording Script & Cue-Sheet

Written for the Operations Manager, Dispatch Planners, and Technical Reviewers.
Conforming strictly to Challenge Brief Part 1 Section 7 and ARCHITECTURE_v25_FREEZE.md Section 17.

---

## Technical Overview & Presentation Structure

| Timestamp | Storyline Chapter | Visual Demonstration | Operations-Manager Dialogue Focus |
| :--- | :--- | :--- | :--- |
| **0:00 – 1:00** | Problem & Lifecycle Governance | Console Header & `make ops-status` | Defending €45,600 truck-roll budget against unvetted black-box changes |
| **1:00 – 2:15** | Reviewer Verification & Submission Pipeline | Clean clone `make run` | 120 validated visits across 8 weeks (`validate_submission.py: OK`), CSV 6-decimal storage |
| **2:15 – 3:30** | Fleet Operations & Priority Dispatches | Console `#operations` View & `make ops-predictions` | Clean integer scores (`43`, `26`), uncompromised decision audit reasons, data health |
| **3:30 – 4:45** | Multi-Window Evidence Gate & Rejection | Console `#governance` View & `make ops-evaluate` | Candidate `v0002` rejection (`REJECT_GROUPED_DISAGREEMENT`), holdout regression (18 vs 17), `DECISION FINAL` |
| **4:45 – 5:45** | Backlog Fleet Risk & Deferral Intelligence | Console `#backlog` View & Deferral Inspector | 15 dispatches/week capacity ceiling, 275 deferred assets, single-pass continuity without score re-invention |
| **5:45 – 7:15** | Live Model Change & Atomic Rollback Proof | Console `#safety` View & `make ops-change` / `ops-rollback-to` | Controlled candidate deployment, target validation, atomic pointer swap, bit-for-bit replay equality verification |
| **7:15 – 8:00** | Empirical Fleet Boundaries & Two-Week Delta | `LIMITATIONS.md` & Production Handover | Measured 12-gateway blind spot (3.61%), honest reporting, operational roadmap |

---

## Detailed Minute-by-Minute Cue-Sheet

### 0:00 – 1:00: The Problem in One Sentence & Track F Rationale
- **Screen Action**: Display RESQ Operations Console (`http://127.0.0.1:8080`) showing the `TRACK F • MLOps` brand badge and `ACTIVE MODEL: v0001`, alongside a terminal displaying `make ops-status`.
- **Terminal Command**:
  ```bash
  make ops-status
  ```
- **Spoken Dialogue**:
  > *"Good morning. As an Operations Manager for LPDG, my responsibility every Monday morning is allocating our fixed technician fleet: exactly 15 truck rolls per week across 8 operational weeks, committing €45,600 in physical technician costs, while mitigating €600 weekly penalties for broken customer gateways.
  >
  > We deliberately chose MLOps Architecture (Track F) over chasing uncalibrated machine learning algorithms. In field operations, deploying a complex model without cryptographic replay determinism, schema drift protection, or verified atomic rollback creates unacceptable service risks. Our core deliverable is total lifecycle governance: ensuring every technician dispatch is defensible, auditable, and fail-closed.
  >
  > Running `make ops-status` establishes our certified baseline: active model is v0001, model artifact is cryptographically valid, schema contract passes, and working tree is clean."*

---

### 1:00 – 2:15: Clean Clone Execution & Canonical Entry Point (`make run`)
- **Screen Action**: In an empty terminal, clone the repository into a clean temporary directory, invoke literal `make run`, and observe output.
- **Terminal Commands**:
  ```bash
  git clone https://github.com/ak-bharadwaj/lpdg-challenge.git clean_review
  cd clean_review
  make run
  ```
- **Spoken Dialogue**:
  > *"To prove reproducibility to reviewers, everything runs through a single canonical command: `make run`.
  > 
  > Notice what happens: in a completely clean environment without cached state, `make run` ingests telemetry through our Monday 00:00 UTC temporal firewall, ranks eligible gateways, applies our 15-visit weekly cap, generates `predictions.csv`, and executes the official challenge validator `validate_submission.py`.
  > 
  > The result is immediate: exactly 120 dispatches across 8 weeks from February 2 to March 23, 2026, formatted to 6 decimals with operations-ready explanation strings under 300 characters. Result: `predictions.csv: OK`."*

---

### 2:15 – 3:30: Operations Cockpit & Top-15 Dispatches
- **Screen Action**: Switch browser to `#operations` view in the RESQ Operations Console (`http://127.0.0.1:8080/#operations`). Highlight the KPI strip and the uncompromised table columns. In the terminal, show `make ops-predictions`.
- **Terminal Commands**:
  ```bash
  make ops-predictions
  ```
- **Spoken Dialogue**:
  > *"Here in the Operations View of our console, the dispatch team has immediate clarity for the selected evaluation week.
  > 
  > Our KPI cards confirm 290 eligible gateways, 15 out of 15 visits allocated under the €5,700 weekly capacity ceiling, and data health verified PASS.
  > 
  > Look at the dispatch priority table: notice that while the underlying submission file stores exact 6-decimal values for mathematical compliance, our operations console renders clean integer scores—such as 43, 26, 23—making priority tiers instantly legible.
  > 
  > Crucially, our table layout protects the operational reason column with generous horizontal space, giving technicians the exact decision audit: baseline deviation, breach metric, and hour count without cramping."*

---

### 3:30 – 4:45: Model Governance & Authoritative Rejection of `v0002`
- **Screen Action**: Click the **Governance** tab (`#governance`). Show the verdict banner (`GATE: REJECT`, `REJECT_GROUPED_DISAGREEMENT`, `DECISION FINAL`). Click the blue **View Evidence** button to display the modal drill-down. In the terminal, run `make ops-evaluate CANDIDATE=v0002`.
- **Terminal Commands**:
  ```bash
  make ops-evaluate CANDIDATE=v0002
  ```
- **Spoken Dialogue**:
  > *"Now for the central operational governance decision: why did we NOT deploy candidate model `v0002`?
  >
  > In the Governance View, notice the banner: `GATE: REJECT` with status `DECISION FINAL`. The candidate was NOT deployed; active model v0001 remains protected.
  >
  > When we open the Evidence Review drawer, we see why. Across three historical development windows—November, December, and January—v0002 reduced missed broken weeks from 71 to 60, a 15.49% improvement.
  >
  > However, our frozen policy enforces Section 8: an isolated grouped holdout of 59 physical gateways that the model never saw during training. On that holdout fleet, v0002 regressed, missing 18 broken weeks versus 17 under active baseline v0001.
  >
  > Under our governance rules, aggregate gains cannot overwrite holdout regression. The promotion gate issued an authoritative `REJECT_GROUPED_DISAGREEMENT`. Rejection here is a successful safety outcome."*

---

### 4:45 – 5:45: Backlog Fleet Risk & Deferral Intelligence
- **Screen Action**: Click the **Backlog** tab (`#backlog`). Point out the capacity allocation bar (15 Dispatched / 275 Deferred), the gateway deferral inspector, and the Single Ranked Object Continuity flow diagram.
- **Console Action**: Click the sample chip `0639EA5602C1 (Rank 169 Deferred)` in the Gateway Deferral Inspector to demonstrate instant lookup.
- **Spoken Dialogue**:
  > *"Because our truck-roll budget strictly caps visits at 15 per week, what happens to gateway rank 16 and beyond?
  >
  > In the Backlog View, we see that 275 gateways are deferred, with 245 units exhibiting elevated risk totaling 1,523 proxy anomaly hours. Notice our data honesty principle: proxy hours represent telemetry deviation—they are never reported as realized euro savings.
  >
  > The Gateway Deferral Inspector allows dispatch planners to audit any gateway. Clicking rank 169 shows it was deferred due to capacity rationing, not absence of anomalies.
  >
  > At the bottom, our Single Ranked Object Continuity diagram highlights Rule 9A: a single scoring pass feeds both `predictions.csv` and `backlog_report.json`. Neither output independently re-scores or invents data."*

---

### 5:45 – 7:15: Live Model Change & Atomic Rollback Verification
- **Screen Action**: Click the **Safety** tab (`#safety`). Show the Model Lifecycle Journey and the Rollback Safety & Proof Panel. In the terminal, execute the authoritative live change sequence: `make ops-change`, `make ops-rollback-to`, and `make ops-verify`.
- **Terminal Commands**:
  ```powershell
  # 1. Controlled demonstration of candidate promotion to fixture v_promotable
  .\make ops-change CANDIDATE=v_promotable

  # 2. Authoritative operator rollback to restore certified baseline v0001
  .\make ops-rollback-to VERSION=v0001

  # 3. Final cryptographic verification
  .\make ops-verify
  ```
- **Spoken Dialogue**:
  > *"The Safety View presents our model lifecycle journey and rollback safety proof: validated model rollback, transactional pointer safety, and deterministic replay verification.
  >
  > To prove our rollback mechanism without violating governance rules or falsely deploying rejected candidate v0002, we execute `make ops-change` using our committed test fixture `v_promotable`. This is the deterministic v_promotable lifecycle fixture, not evidence that v0002 should be promoted.
  >
  > Then, we execute our authoritative operator rollback: `make ops-rollback-to VERSION=v0001`.
  >
  > Observe the terminal proof:
  > 1. Target Validation: Package v0001 is validated before touching the registry.
  > 2. Atomic Pointer Switch: Swaps `registry/active.json` atomically in under 1 millisecond.
  > 3. Replay Equality Proof: Runs inference and proves bit-for-bit replay hash equality against the baseline checkpoint.
  > 4. Verified Restoration: Running `make ops-verify` confirms active model is restored to v0001 and output matches byte-for-byte."*

---

### 7:15 – 8:00: Empirical Fleet Boundaries & Two-Week Operational Delta
- **Screen Action**: Display `LIMITATIONS.md` Sections 1 and 5.
- **Spoken Dialogue**:
  > *"We close with operational honesty. In `LIMITATIONS.md`, we disclose that of 332 registered gateways, exactly 12 units—3.61% of our fleet—have zero historical telemetry records. We classify them as `NO_TELEMETRY` rather than inventing calm scores.
  >
  > If given two additional operational weeks, our priorities are clear:
  > 1. Ingest fresh, synchronized meter-read telemetry to eliminate the 2026-01-26 snapshot lag.
  > 2. Implement dual-channel silence detection to catch complete communication blackouts before they drop into the backlog.
  > 3. Jointly optimize dispatch by weighting anomaly persistence with customer unread meter exposure.
  > 4. Audit carrier cellular SIM provisioning to bring the 12 blind-spot units online.
  >
  > In conclusion: Track F delivers not just predictions, but complete lifecycle governance. The system is deterministic, auditable, and designed for controlled operational deployment. Thank you."*

---

## Live Operator Quick-Reference Card

### Windows / PowerShell Rehearsal & Live Evaluation

For local rehearsal in Windows PowerShell:

```powershell
# Set local rehearsal environment variables (PowerShell)
$env:LIVE_DATA = ".\data"
$env:LIVE_WEEK = "2026-02-02"

# 1. Check certified baseline status
.\make ops-status

# 2. Safety preflight check (validates schema, telemetry, data path)
.\make ops-preflight

# 3. Live inference & prediction inspection
.\make ops-live
.\make ops-predictions

# 4. Candidate evaluation (proves v0002 rejection on holdout)
.\make ops-evaluate CANDIDATE=v0002

# 5. Live change demonstration (staged fixture v_promotable)
.\make ops-change CANDIDATE=v_promotable

# 6. Authoritative rollback & equality verification
.\make ops-rollback-to VERSION=v0001
.\make ops-verify
```

### Unseen Evaluator Dataset (PowerShell)

For an evaluator testing arbitrary unseen evaluation weeks or alternative data paths without hard-coded dates:

```powershell
# Set evaluator environment variables
$env:LIVE_DATA = "C:\path\to\evaluator_dataset"
$env:LIVE_WEEK = "2026-05-04"

# 1. Inspect status and preflight against unseen dataset
.\make ops-status
.\make ops-preflight

# 2. Run live inference and inspect predictions
.\make ops-live
.\make ops-predictions

# 3. Evaluate candidate model
.\make ops-evaluate CANDIDATE=v0002

# 4. Controlled promotion of test fixture v_promotable
.\make ops-change CANDIDATE=v_promotable

# 5. Immediate rollback to certified baseline v0001 and bit-for-bit replay verification
.\make ops-rollback-to VERSION=v0001
.\make ops-verify
```
