# Live Evaluator Session Operational Rehearsal Guide

This guide documents the authoritative execution sequence for live evaluation sessions with technical evaluators and the Operations Manager.

---

## 1. Operating Principles & Evaluator Handover Interface

1. **Unseen Operational Data**:
   During the live session, the evaluator hands over an unseen dataset directory (containing new telemetry partitions and updated gateway master records) along with a target Monday scoring date:
   ```bash
   LIVE_DATA="/path/to/unseen_evaluator_dataset"
   LIVE_WEEK="2026-05-04"   # Example: week from evaluator's unseen month
   ```
2. **Data-Agnostic Production Pipeline**:
   The live operator commands do not hardcode April 2026, March 2026, or the original 8 challenge weeks. April 2026 in `tests/fixtures/unseen_month_fixture.py` serves strictly as an automated test fixture proving support for:
   - Gateway IDs never seen during training (`AA0000000001`).
   - Gateways with established history that go completely silent in the live month (`0639EA000002`).
   - Canonical telemetry schema compliance without pipeline crashes.
3. **Primary Live Operator Shortcuts**:
   For live demonstration sessions, use the high-level orchestration shortcuts `ops-change` and `ops-rollback-to`. Lower-level commands (`ops-evaluate`, `ops-promote`, `ops-rollback`) are preserved for granular diagnostic investigations.
4. **Certified Baseline vs. Live Mutation**:
   - **During the live session**: Registry pointer transitions (`active.json`) and audit trail appends (`history.jsonl`) are **expected and desirable** to demonstrate atomic promotion, candidate rejection enforcement, and compensating rollback.
   - **Before/After the rehearsal**: The repository baseline is protected via a cryptographically bound read-only snapshot export (`make ops-snapshot`) and safe restoration (`make ops-restore`).

---

## 2. Certified Baseline Snapshot (Pre-Session)

Before launching the live rehearsal, record the certified baseline state (active model `v0001`):

```bash
# Export read-only certified baseline snapshot with cryptographic bindings
make ops-snapshot
# Outputs: Snapshot exported to: registry_certified_baseline.json
```

The exported snapshot cryptographically binds to:
- `production_version` (`v0001`)
- `artifact_hash` (SHA-256 of active model package)
- repository Git commit SHA
- `active.json` SHA-256 digest
- `history.jsonl` SHA-256 digest

---

## 3. Primary Live Evaluator Demonstration Sequence

Configure the session environment variables pointing to the evaluator's unseen dataset:

```bash
LIVE_DATA="/path/to/evaluator_unseen_month"
LIVE_WEEK="2026-05-04"  # Replace with the evaluator's designated Monday week
```

The live evaluator's primary sequence is:

```bash
make ops-status
make ops-preflight LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-change CANDIDATE=v0002 LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-change CANDIDATE=v_promotable LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-rollback-to VERSION=v0001 LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
make ops-verify LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK" TARGET=v0001
```

---

### Step 1: Operator Status Summary (Read-Only)
Inspect the active model pointer, artifact hash integrity, and registry status:
```bash
make ops-status
```
*Expected Output:*
- Active model: `v0001`
- Artifact integrity: `PASS`
- Registry: `PASS`
- Schema contract: `PASS`
- Git tree: `CLEAN`

---

### Step 2: Preflight Safety & Contract Check (Read-Only)
Verify that the evaluator's unseen data satisfies schema contracts and source completeness before running inference:
```bash
make ops-preflight LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- `PREFLIGHT: PASS` (Production state unchanged)

---

### Step 3: Run Live Prediction with Baseline Model (`v0001`)
Generate top-15 dispatches for the unseen week using the frozen active production model:
```bash
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Active model: `v0001`
- Eligible gateways inspected
- Selected: 15 dispatches
- Replay hash: Provenance SHA-256 generated
- Status: `PASS`

---

### Step 4: Deliberate Negative Test: Model Change Attempt on Rejected Candidate (`v0002`)
Prove that attempting to change production to candidate `v0002` triggers the frozen promotion policy, fails closed, and leaves production unchanged:
```bash
make ops-change CANDIDATE=v0002 LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
# Or equivalent lower-level command:
# python scripts/ops.py promote --candidate v0002 --data "$LIVE_DATA" --yes
```
*Expected Result:*
- Decision: `REJECT (REJECT_GROUPED_DISAGREEMENT)`
- Production state: `UNCHANGED (registry/active.json remains on v0001)`
- Expected result: `REJECT` / exit code `1`.
- **Note**: This non-zero exit is intentional and is not a rehearsal failure. It proves that production is protected against unvetted candidates.

---

### Step 5: High-Level Model Change with Validated Candidate (`v_promotable`)
Orchestrate end-to-end model change through the authoritative lifecycle (preflight -> candidate validation -> gate evaluation -> confirmation -> atomic promotion -> post-verification):
```bash
make ops-change CANDIDATE=v_promotable LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Candidate validation: `PASS`
- Gate decision: `PROMOTE`
- Transition: `v0001 -> v_promotable`
- Post-verification: `PASS (15 dispatches scored)`
- Audit event: `PROMOTED` appended to `registry/history.jsonl`
- Exit code: `0`

---

### Step 6: Live Prediction with Changed Active Model
Execute live prediction on the evaluator's unseen week under the new active model, proving operational score changes:
```bash
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Active model: `v_promotable`
- Replay hash: Distinct from Step 3

---

### Step 7: Atomic Rollback to Baseline Model (`v0001`)
Execute atomic rollback wrapping the existing rollback engine with automated 7-step replay equality verification:
```bash
make ops-rollback-to VERSION=v0001 LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Target validation: `PASS`
- Atomic switch: `PASS`
- Replay equality: `PASS`
- Active model: `v0001` restored
- Audit event: `ROLLED_BACK` appended to `registry/history.jsonl`
- Status: `PASS`

---

### Step 8: Replay Verification & Bit-for-Bit Determinism Proof
Verify that restored model `v0001` reproduces bit-for-bit identical outputs on the unseen week:
```bash
make ops-verify LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK" TARGET=v0001
```
*Expected Output:*
- Version: `v0001`
- Replay hash: Exact match with Step 3
- Determinism: `PASS`
- Registry: `UNCHANGED`

---

## 4. Diagnostic Low-Level Commands Reference

For deep diagnostic inspections during evaluation or auditing, the lower-level CLI commands remain fully supported:

- **`make ops-evaluate CANDIDATE=<ver>`**: Evaluates candidate multi-window rolling and grouped holdout evidence without modifying any registry state.
- **`make ops-promote CANDIDATE=<ver>`**: Evaluates promotion gate and performs atomic switch with explicit confirmation prompt.
- **`make ops-rollback TARGET=<ver>`**: Direct low-level rollback engine execution with replay comparison.

---

## 5. Post-Rehearsal Certified Baseline Restoration vs. Production Rollback

Following the live demonstration, safely restore the repository to the pre-rehearsal certified baseline before hand-in:

```bash
make ops-restore
# Outputs:
# Registry state safely restored from certified snapshot: registry_certified_baseline.json
# Active model restored: v0001
# Artifact hash verified: ...
# Model artifacts untouched: verified read-only
```

Confirm repository status:
```bash
make ops-status
```
*Expected Output:*
- Active model: `v0001`
- Registry: `PASS`
- Artifact integrity: `PASS`
- Git tree: `CLEAN`

### Authoritative Architecture Disclosure:
> **The rehearsal deliberately restores the repository to the pre-rehearsal certified baseline before hand-in.**
> 
> In a real production deployment, a rollback would **never** erase its audit trail. The actual live rollback appends the `ROLLED_BACK` event to `registry/history.jsonl` and preserves that complete audit trail. `registry/active.json` is the authoritative active pointer, while `registry/history.jsonl` is the immutable lifecycle audit evidence.
