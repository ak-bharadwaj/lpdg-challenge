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
3. **Certified Baseline vs. Live Mutation**:
   - **During the live session**: Registry pointer transitions (`active.json`) and audit trail appends (`history.jsonl`) are **expected and desirable** to demonstrate atomic promotion, candidate rejection enforcement, and compensating rollback.
   - **Before/After the session**: The repository baseline is protected via a read-only snapshot export (`make ops-snapshot`) and safe restoration (`make ops-restore`), eliminating reliance on arbitrary `git checkout`.

---

## 2. Certified Baseline Snapshot (Pre-Session)

Before launching the live session, record the certified baseline state (active model `v0001`):

```bash
# Export read-only certified baseline snapshot
make ops-snapshot
# Outputs: Snapshot exported to: registry_certified_baseline.json
```

---

## 3. Step-by-Step Live Evaluator Demonstration Sequence

Configure the session environment variables pointing to the evaluator's unseen dataset:

```bash
LIVE_DATA="/path/to/evaluator_unseen_month"
LIVE_WEEK="2026-05-04"  # Replace with the evaluator's designated Monday week
```

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

---

### Step 2: Preflight Safety & Contract Check (Read-Only)
Verify that the evaluator's unseen data satisfies schema contracts and source completeness before running inference:
```bash
make ops-preflight LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- `PREFLIGHT: PASS` (Production state unchanged)

---

### Step 3: Run Live Prediction with Active Model (`v0001`)
Generate top-15 dispatches for the unseen week using the frozen active production model:
```bash
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Active model: `v0001`
- Eligible gateways inspected
- Selected: 15 dispatches
- Replay hash: SHA256 provenance generated
- Status: `PASS`

---

### Step 4: Evaluate Candidate Model (`v0002`) Against Promotion Policy
Evaluate experimental candidate `v0002` across multi-window temporal backtests and the 59-gateway grouped holdout:
```bash
make ops-evaluate CANDIDATE=v0002
```
*Expected Output:*
- Rolling evidence: Nov (+6), Dec (+4), Jan (+1)
- Grouped evidence: 17 active vs 18 candidate (diff: -1, DISAGREED)
- Aggregate result: 71 vs 60 (+15.49% improvement)
- Decision: `REJECT (REJECT_GROUPED_DISAGREEMENT)`
- Production state: `UNCHANGED`

---

### Step 5: Verify That Promotion Gate Strictly Blocks Rejected Candidate
Prove that attempting to promote rejected candidate `v0002` fails closed and does not mutate production:
```bash
python scripts/ops.py promote --candidate v0002 --data "$LIVE_DATA" --yes
```
*Expected Output:*
- `REJECTION ENFORCED: Candidate v0002 was REJECTED (REJECT_GROUPED_DISAGREEMENT)`
- `Production state: UNCHANGED (registry/active.json remains on v0001)`
- Exit code: `1`

---

### Step 6: Atomically Promote Validated Demonstration Fixture (`v_promotable`)
Demonstrate successful atomic promotion using the committed, pre-validated demonstration fixture:
```bash
make ops-promote CANDIDATE=v_promotable DATA="$LIVE_DATA"
```
*Expected Output:*
- Candidate validation: `PASS`
- Decision: `PROMOTE`
- Atomic switch: `active.json` updated to `v_promotable`
- History appended: `PROMOTED` event recorded

---

### Step 7: Live Prediction with Promoted Active Model
Execute live prediction on the evaluator's unseen week under the new active model, proving operational score changes:
```bash
make ops-live LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Active model: `v_promotable`
- Replay hash: Distinct from Step 3

---

### Step 8: Execute Atomic Rollback to Baseline Model (`v0001`)
Execute atomic rollback with automated replay equality verification:
```bash
make ops-rollback TARGET=v0001 LIVE_DATA="$LIVE_DATA" LIVE_WEEK="$LIVE_WEEK"
```
*Expected Output:*
- Target validation: `PASS`
- Atomic switch: `PASS`
- Replay equality: `PASS`
- Active model: `v0001` restored
- Status: `PASS`

---

### Step 9: Replay Verification & Bit-for-Bit Determinism Proof
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

## 4. Post-Session Certified Baseline Restoration

Following the live demonstration, safely restore the certified baseline from the snapshot:

```bash
make ops-restore
# Outputs:
# Registry state safely restored from snapshot: registry_certified_baseline.json
# Active model restored: v0001
```

Confirm repository status:
```bash
make ops-status
git status
```
*Expected Output:*
- Active model: `v0001`
- Working tree: `CLEAN`
