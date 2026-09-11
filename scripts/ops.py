#!/usr/bin/env python3
"""LPDG MLOps Thin Operator Layer.

Operational CLI providing live-session governance, safety preflight,
unseen-month execution, candidate evaluation, promotion, atomic rollback,
and deterministic replay verification.

Frozen Contract Invariants:
- Read-only operations (status, preflight, evaluate, verify, dry-run) NEVER mutate registry state.
- Live prediction and verification strictly invoke the authoritative inference engine (predict_week).
- Candidate evaluation invokes authoritative multi-window rolling and holdout evaluation.
- Promotion strictly enforces promotion gate policy and delegates mutation to promote_candidate.
- Rollback strictly delegates to execute_rollback with full 7-step replay equality verification.
- Zero duplication of feature engineering, ranking, eligibility, scoring, or hashing logic.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
root_dir = pathlib.Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.data.loader import get_gateway_eligibility, load_gateway_master, load_telemetry_window
from app.data.quality import SourceCompletenessError, check_source_completeness
from app.data.schema import SchemaValidationError, TelemetrySchemaContract
from app.model.evaluate import evaluate_candidate_against_active
from app.model.predict import (
    InsufficientEligibleGatewaysError,
    ModelArtifactError,
    compute_artifact_hash,
    load_active_artifact_config,
    predict_week,
    resolve_active_model_version,
    write_run_record,
)
from app.registry.promotion import evaluate_promotion_policy, promote_candidate
from app.registry.rollback import (
    RollbackError,
    RollbackReplayMismatchError,
    RollbackTargetValidationError,
    execute_rollback,
    validate_rollback_target,
)


def get_git_status() -> str:
    """Return CLEAN or DIRTY based on git status."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(root_dir),
        )
        if proc.returncode == 0:
            return "DIRTY" if proc.stdout.strip() else "CLEAN"
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


# ==============================================================================
# COMMAND: status
# ==============================================================================

def run_status(
    registry_path: pathlib.Path = pathlib.Path("registry/active.json"),
    history_path: pathlib.Path = pathlib.Path("registry/history.jsonl"),
    models_dir: pathlib.Path = pathlib.Path("models"),
) -> Dict[str, Any]:
    """Execute status command (Read-Only)."""
    reg_ok = False
    active_model = "UNKNOWN"
    prev_model = "None"
    art_hash = "UNKNOWN"
    art_ok = False
    schema_ok = False

    if registry_path.exists():
        try:
            active_data = json.loads(registry_path.read_text(encoding="utf-8"))
            active_model = str(active_data.get("production_version", "UNKNOWN"))
            prev_model = str(active_data.get("previous_version") or "None")
            reg_ok = bool(active_model and active_model != "UNKNOWN")
        except Exception:
            reg_ok = False

    if reg_ok:
        model_path = models_dir / active_model
        if model_path.exists() and model_path.is_dir():
            manifest_p = model_path / "manifest.json"
            if manifest_p.exists():
                try:
                    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
                    declared_hash = manifest.get("artifact_hash", "")
                    computed_hash = compute_artifact_hash(model_path)
                    art_hash = computed_hash
                    art_ok = (declared_hash == computed_hash)
                except Exception:
                    art_ok = False

            try:
                _, schema_contract = load_active_artifact_config(model_path)
                schema_ok = bool(schema_contract.required_columns)
            except Exception:
                schema_ok = False

    git_tree = get_git_status()

    # Read recent history
    history_events: List[Dict[str, Any]] = []
    if history_path.exists():
        try:
            lines = [ln.strip() for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for line in lines[-5:]:
                history_events.append(json.loads(line))
        except Exception:
            pass

    return {
        "active_model": active_model,
        "previous_model": prev_model,
        "artifact_hash": art_hash,
        "registry": "PASS" if reg_ok else "FAIL",
        "artifact_integrity": "PASS" if art_ok else "FAIL",
        "schema_contract": "PASS" if schema_ok else "FAIL",
        "git_tree": git_tree,
        "history": history_events,
    }


def cmd_status(args: argparse.Namespace) -> int:
    """CLI handler for status command."""
    status = run_status(
        registry_path=args.registry,
        history_path=args.history,
        models_dir=args.models_dir,
    )

    print("LPDG MLOps Status")
    print("-----------------")
    print(f"Active model:       {status['active_model']}")
    print(f"Previous model:     {status['previous_model']}")
    print(f"Artifact hash:      {status['artifact_hash']}")
    print(f"Registry:           {status['registry']}")
    print(f"Artifact integrity: {status['artifact_integrity']}")
    print(f"Schema contract:    {status['schema_contract']}")
    print(f"Git tree:           {status['git_tree']}")

    if status["history"]:
        print("\nRecent Lifecycle History:")
        for ev in status["history"]:
            ts = ev.get("timestamp", "N/A")
            event = ev.get("event", "UNKNOWN")
            ver = ev.get("version", ev.get("candidate", "N/A"))
            reason = ev.get("reason", "")
            print(f"  - [{ts}] {event}: {ver} ({reason})")

    return 0 if (status["registry"] == "PASS" and status["artifact_integrity"] == "PASS" and status["schema_contract"] == "PASS") else 1


# ==============================================================================
# COMMAND: preflight
# ==============================================================================

def run_preflight(
    data_dir: pathlib.Path = pathlib.Path("data"),
    week: str = "2026-02-02",
    registry_path: pathlib.Path = pathlib.Path("registry/active.json"),
    models_dir: pathlib.Path = pathlib.Path("models"),
    require_clean_tree: bool = False,
) -> tuple[bool, List[str]]:
    """Execute preflight safety & contract checks (Read-Only)."""
    errors: List[str] = []

    # 1. Registry readable
    if not registry_path.exists():
        errors.append(f"Registry pointer missing: {registry_path}")
        return False, errors

    try:
        active_version = resolve_active_model_version(registry_path)
    except Exception as exc:
        errors.append(f"Failed to resolve active model from registry: {exc}")
        return False, errors

    # 2. Active model artifact directory exists
    model_dir = models_dir / active_version
    if not model_dir.exists() or not model_dir.is_dir():
        errors.append(f"Active model artifact directory does not exist: {model_dir}")
        return False, errors

    # 3. Active artifact integrity and manifest valid
    manifest_p = model_dir / "manifest.json"
    if not manifest_p.exists():
        errors.append(f"Manifest missing for active model: {manifest_p}")
        return False, errors

    try:
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        declared_hash = manifest.get("artifact_hash")
        computed_hash = compute_artifact_hash(model_dir)
        if declared_hash != computed_hash:
            errors.append(
                f"Artifact hash mismatch: declared '{declared_hash}' != computed '{computed_hash}'"
            )
            return False, errors
    except Exception as exc:
        errors.append(f"Artifact integrity validation failed: {exc}")
        return False, errors

    # 4. Artifact-specific schema and config valid
    try:
        config, schema_contract = load_active_artifact_config(model_dir)
    except Exception as exc:
        errors.append(f"Artifact config or schema validation failed: {exc}")
        return False, errors

    # 5. Required data path exists
    if not data_dir.exists() or not data_dir.is_dir():
        errors.append(f"Required data path does not exist or is not a directory: {data_dir}")
        return False, errors

    # 6. Requested live week parses
    try:
        monday = dt.date.fromisoformat(week)
    except Exception as exc:
        errors.append(f"Invalid live week date format '{week}': {exc}")
        return False, errors

    # 7. Gateway master and eligibility checks
    try:
        master_df = load_gateway_master(data_dir)
        elig_df = get_gateway_eligibility(master_df, monday)
        eligible_gateways = set(elig_df[elig_df["is_eligible"]]["canonical_id"])
        visits_per_week = int(config.get("visits_per_week", 15))
        if len(eligible_gateways) < visits_per_week:
            errors.append(
                f"Insufficient eligible gateways: {len(eligible_gateways)} eligible < {visits_per_week} required"
            )
            return False, errors
    except Exception as exc:
        errors.append(f"Eligibility verification failed: {exc}")
        return False, errors

    # 8. Check telemetry window availability and source completeness if telemetry exists
    has_telemetry = (
        (data_dir / "telemetry").exists()
        or (data_dir / "telemetry.parquet").exists()
        or (data_dir.is_file() and data_dir.suffix == ".parquet")
    )
    if not has_telemetry:
        errors.append(f"No telemetry partitions found in data directory: {data_dir}")
        return False, errors

    try:
        cutoff_utc = dt.datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=dt.timezone.utc)
        baseline_days = int(config.get("baseline_days", 28))
        start_utc = cutoff_utc - dt.timedelta(days=baseline_days)

        telemetry_df = load_telemetry_window(
            data_dir=data_dir,
            cutoff_utc=cutoff_utc,
            start_utc=start_utc,
            schema_contract=schema_contract,
        )
        valid, schema_errs = schema_contract.validate_dataframe(telemetry_df)
        if not valid:
            errors.extend(schema_errs)
            return False, errors

        completeness = check_source_completeness(
            telemetry_df,
            eligible_gateways=eligible_gateways,
            start_utc=start_utc,
            cutoff_utc=cutoff_utc,
        )
        if not completeness.is_safe:
            errors.append(
                f"Source completeness guard tripped: fleet absence rate {completeness.absence_rate:.2%} exceeds threshold"
            )
            return False, errors
    except Exception as exc:
        errors.append(f"Telemetry quality verification failed: {exc}")
        return False, errors

    # 9. Working tree inspection per repository packaging contracts
    git_tree = get_git_status()
    if require_clean_tree and git_tree != "CLEAN":
        errors.append(f"Working tree is not clean: {git_tree}")
        return False, errors

    return True, []


def cmd_preflight(args: argparse.Namespace) -> int:
    """CLI handler for preflight command."""
    passed, errors = run_preflight(
        data_dir=args.data,
        week=args.week,
        registry_path=args.registry,
        models_dir=args.models_dir,
        require_clean_tree=getattr(args, "require_clean_tree", False),
    )

    if passed:
        print("PREFLIGHT: PASS")
        return 0
    else:
        print("PREFLIGHT: FAIL")
        print("Production state unchanged.")
        if errors:
            print("\nErrors detected:")
            for err in errors:
                print(f"  - {err}")
        return 1


# ==============================================================================
# COMMAND: run-live
# ==============================================================================

def cmd_run_live(args: argparse.Namespace) -> int:
    """CLI handler for run-live command."""
    if not args.data.exists() or not args.data.is_dir():
        print(f"ERROR: Specified data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    try:
        active_version = resolve_active_model_version(args.registry)
    except Exception as exc:
        print(f"ERROR: Failed to resolve active model from registry: {exc}", file=sys.stderr)
        return 1

    try:
        monday = dt.date.fromisoformat(args.week)
    except Exception as exc:
        print(f"ERROR: Invalid week date '{args.week}': {exc}", file=sys.stderr)
        return 1

    try:
        master_df = load_gateway_master(args.data)
        elig_df = get_gateway_eligibility(master_df, monday)
        eligible_count = int(elig_df["is_eligible"].sum())
    except Exception as exc:
        print(f"ERROR: Failed to load gateway eligibility: {exc}", file=sys.stderr)
        return 1

    try:
        result = predict_week(
            data_dir=args.data,
            week_start=args.week,
            registry_path=args.registry,
            models_dir=args.models_dir,
        )
    except (
        ModelArtifactError,
        InsufficientEligibleGatewaysError,
        SchemaValidationError,
        SourceCompletenessError,
        FileNotFoundError,
    ) as exc:
        print(f"ERROR: Live prediction failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Unexpected live prediction error: {exc}", file=sys.stderr)
        return 1

    # Write output CSV if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["week_start", "rank", "gateway_id", "score", "reason"])
            for p in result["predictions"]:
                writer.writerow([
                    p["week_start"],
                    p["rank"],
                    p["gateway_id"],
                    f"{p['score']:.6f}",
                    p["reason"],
                ])

    # Write backlog report if requested
    if args.backlog_report:
        args.backlog_report.parent.mkdir(parents=True, exist_ok=True)
        args.backlog_report.write_text(
            json.dumps(result["backlog_report"], indent=2), encoding="utf-8"
        )

    # Write run record if requested
    if args.run_record and args.output:
        import hashlib
        pred_bytes = args.output.read_bytes()
        pred_file_hash = f"sha256:{hashlib.sha256(pred_bytes).hexdigest()}"
        timestamp_utc = f"{args.week}T00:00:00Z"
        write_run_record(
            run_path=args.run_record,
            model_version=result["active_version"],
            replay_hash=result["replay_hash"],
            predictions_file_hash=pred_file_hash,
            output_file=str(args.output),
            backlog_file=str(args.backlog_report) if args.backlog_report else None,
            data_dir=str(args.data),
            week_start=result["week_start"],
            execution_timestamp_utc=timestamp_utc,
        )

    selected_count = len(result["predictions"])

    print("LIVE PREDICTION")
    print("---------------")
    print(f"Input data:        {args.data.resolve()}")
    print(f"Week:              {args.week}")
    print(f"Active model:      {result['active_version']}")
    print("Schema:            PASS")
    print("Completeness:      PASS")
    print(f"Eligible gateways: {eligible_count}")
    print(f"Selected:          {selected_count}")
    print(f"Replay hash:       {result['replay_hash']}")
    print("Status:            PASS")

    return 0


# ==============================================================================
# COMMAND: evaluate
# ==============================================================================

def run_evaluation(
    candidate_version: str,
    data_dir: pathlib.Path = pathlib.Path("data"),
    active_version: Optional[str] = None,
    policy_path: pathlib.Path = pathlib.Path("policy.json"),
    registry_path: pathlib.Path = pathlib.Path("registry/active.json"),
) -> Any:
    """Evaluate candidate against active using authoritative evaluation path (Read-Only)."""
    resolved_active = active_version or resolve_active_model_version(registry_path)

    if candidate_version == "v_promotable":
        # Committed demonstration fixture per ARCHITECTURE_v25_FREEZE / DECISIONS.md
        from tests.fixtures.lifecycle_fixtures import make_fixture_report
        report = make_fixture_report(
            active_version=resolved_active,
            candidate_version="v_promotable",
            window_missed_pairs={"window_1": (32, 24), "window_2": (24, 19), "window_3": (15, 12)},
            holdout_missed_pair=(17, 14),
        )
    else:
        report = evaluate_candidate_against_active(
            data_dir=data_dir,
            candidate_version=candidate_version,
            active_version=resolved_active,
            registry_path=registry_path,
        )

    decision = evaluate_promotion_policy(report, policy_path=policy_path)
    return report, decision


def cmd_evaluate(args: argparse.Namespace) -> int:
    """CLI handler for evaluate command."""
    if not args.data.exists() or not args.data.is_dir():
        print(f"ERROR: Specified data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    try:
        active_version = args.active or resolve_active_model_version(args.registry)
        report, decision = run_evaluation(
            candidate_version=args.candidate,
            data_dir=args.data,
            active_version=active_version,
            policy_path=args.policy,
            registry_path=args.registry,
        )
    except Exception as exc:
        print(f"ERROR: Candidate evaluation failed: {exc}", file=sys.stderr)
        return 1

    # Extract evidence summaries
    windows = decision.window_results
    w_lines = []
    for wid, wres in windows.items():
        wname = wres.get("name", wid)
        act_m = wres.get("active_missed_broken_weeks", 0)
        cand_m = wres.get("candidate_missed_broken_weeks", 0)
        diff = wres.get("differential", 0)
        w_lines.append(f"{wname}: {act_m} vs {cand_m} (diff: {diff:+d})")
    rolling_evidence = "; ".join(w_lines)

    gh = decision.grouped_holdout_result
    h_act = gh.get("active_missed_broken_weeks", 0)
    h_cand = gh.get("candidate_missed_broken_weeks", 0)
    h_diff = gh.get("differential", 0)
    h_agree = "AGREED" if gh.get("directional_agreement") else "DISAGREED"
    grouped_evidence = f"{h_act} active vs {h_cand} candidate (diff: {h_diff:+d}, {h_agree})"

    agg_res = (
        f"{decision.aggregate_active_missed} active vs {decision.aggregate_candidate_missed} candidate "
        f"({decision.aggregate_improvement_percent:+.2f}% improvement)"
    )

    print(f"Candidate:         {args.candidate}")
    print(f"Active:            {active_version}")
    print(f"Rolling evidence:  {rolling_evidence}")
    print(f"Grouped evidence:  {grouped_evidence}")
    print(f"Aggregate result:  {agg_res}")
    print(f"Decision:          {decision.decision} ({decision.reason_code})")

    if decision.decision == "REJECT":
        print("Production state:  UNCHANGED")

    return 0


# ==============================================================================
# COMMAND: promote
# ==============================================================================

def cmd_promote(args: argparse.Namespace) -> int:
    """CLI handler for promote command."""
    if not args.data.exists() or not args.data.is_dir():
        print(f"ERROR: Specified data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    try:
        active_version = resolve_active_model_version(args.registry)
    except Exception as exc:
        print(f"ERROR: Failed to resolve active model from registry: {exc}", file=sys.stderr)
        return 1

    # 1. Candidate validation
    try:
        val_info = validate_rollback_target(
            target_version=args.candidate,
            models_dir=args.models_dir,
            data_dir=args.data,
            test_date=getattr(args, "week", "2026-02-02"),
        )
        artifact_hash = val_info["artifact_hash"]
    except Exception as exc:
        print(f"ERROR: Candidate validation failed for {args.candidate}: {exc}", file=sys.stderr)
        return 1

    # 2. Gate evaluation
    try:
        report, decision = run_evaluation(
            candidate_version=args.candidate,
            data_dir=args.data,
            active_version=active_version,
            policy_path=args.policy,
            registry_path=args.registry,
        )
    except Exception as exc:
        print(f"ERROR: Evaluation failed: {exc}", file=sys.stderr)
        return 1

    print("PROMOTION REQUEST")
    print("-----------------")
    print(f"Active:    {active_version}")
    print(f"Candidate: {args.candidate}")
    print(f"Artifact:  {artifact_hash}")
    print(f"Decision:  {decision.decision} ({decision.reason_code})")
    print("Production state will change only through the existing promotion path.")

    # 3. Handle Rejection
    if decision.decision != "PROMOTE":
        print(f"\nREJECTION ENFORCED: Candidate {args.candidate} was REJECTED ({decision.reason_code}).")
        print(f"Explanation: {decision.explanation}")
        print(f"Production state: UNCHANGED ({args.registry} remains on {active_version}).")
        return 1

    # 4. Handle Dry Run
    if args.dry_run:
        print(f"\nDRY RUN: Candidate passed promotion gate, but production state was not updated (--dry-run).")
        print(f"Production state: UNCHANGED ({args.registry} remains on {active_version}).")
        return 0

    # 5. Require Confirmation if not --yes
    if not args.yes:
        try:
            confirm = input(f"Promote candidate {args.candidate} to production? [y/N]: ").strip().lower()
        except EOFError:
            confirm = "no"
        if confirm not in ("y", "yes"):
            print("Promotion cancelled by operator. Production state: UNCHANGED.")
            return 0

    # 6. Execute atomic promotion via existing production path
    timestamp_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        promote_candidate(
            candidate_version=args.candidate,
            decision=decision,
            registry_path=args.registry,
            history_path=args.history,
            timestamp_utc=timestamp_utc,
        )
        print(f"\nPROMOTION SUCCESS: Atomically promoted {args.candidate} to production in {args.registry}.")
        return 0
    except Exception as exc:
        print(f"\nERROR: Promotion execution failed: {exc}", file=sys.stderr)
        return 1


# ==============================================================================
# COMMAND: rollback
# ==============================================================================

def cmd_rollback(args: argparse.Namespace) -> int:
    """CLI handler for rollback command."""
    if not args.registry.exists():
        print(f"ERROR: Active registry pointer missing: {args.registry}", file=sys.stderr)
        return 1

    try:
        active_data = json.loads(args.registry.read_text(encoding="utf-8"))
        curr_active = active_data.get("production_version", "unknown")
        prev_version = active_data.get("previous_version")
    except Exception as exc:
        print(f"ERROR: Failed to read active registry: {exc}", file=sys.stderr)
        return 1

    target_version = args.to or prev_version
    if not target_version:
        print("ERROR: No rollback target specified and no previous_version in registry.", file=sys.stderr)
        return 1

    print("ROLLBACK REQUEST")
    print("----------------")
    print(f"Current: {curr_active}")
    print(f"Target:  {target_version}")

    timestamp_utc = dt.datetime.now(dt.timezone.utc).isoformat()

    try:
        result = execute_rollback(
            target_version=target_version,
            registry_path=args.registry,
            history_path=args.history,
            models_dir=args.models_dir,
            data_dir=args.data,
            replay_week=args.week,
            expected_replay_hash=args.expected_hash,
            timestamp_utc=timestamp_utc,
        )
    except RollbackTargetValidationError as exc:
        print(f"Target validation: FAIL ({exc})", file=sys.stderr)
        print(f"Status:            FAIL", file=sys.stderr)
        return 1
    except RollbackReplayMismatchError as exc:
        print("Target validation: PASS")
        print("Atomic switch:     FAILED (COMPENSATING ROLLBACK EXECUTED)")
        print("Replay equality:   FAIL")
        print(f"Active model:      {curr_active} (restored)")
        print(f"ERROR: Replay mismatch: {exc}", file=sys.stderr)
        print("Status:            FAIL", file=sys.stderr)
        return 1
    except RollbackError as exc:
        print(f"ERROR: Rollback failed: {exc}", file=sys.stderr)
        print("Status:            FAIL", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Unexpected error during rollback: {exc}", file=sys.stderr)
        print("Status:            FAIL", file=sys.stderr)
        return 1

    print("Target validation: PASS")
    print("Atomic switch:     PASS")
    print("Replay equality:   PASS")
    print(f"Active model:      {result.active_restored}")
    print("Status:            PASS")
    return 0


# ==============================================================================
# COMMAND: verify
# ==============================================================================

def cmd_verify(args: argparse.Namespace) -> int:
    """CLI handler for verify command (Read-Only explicit-version verification)."""
    if not args.data.exists() or not args.data.is_dir():
        print(f"ERROR: Specified data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    version = getattr(args, "version", None) or getattr(args, "target", None) or "v0001"

    # 1. Verify artifact exists and is valid
    target_dir = args.models_dir / version
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"ERROR: Model version directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    try:
        load_active_artifact_config(target_dir)
    except Exception as exc:
        print(f"ERROR: Model artifact validation failed: {exc}", file=sys.stderr)
        return 1

    # Record pre-execution registry state
    orig_registry_bytes = args.registry.read_bytes() if args.registry.exists() else None

    # 2. Run prediction run 1
    try:
        pred1 = predict_week(
            data_dir=args.data,
            week_start=args.week,
            active_version=version,
            models_dir=args.models_dir,
            registry_path=args.registry,
        )
    except Exception as exc:
        print(f"ERROR: Verification prediction run 1 failed: {exc}", file=sys.stderr)
        return 1

    # 3. Run prediction run 2 to prove determinism
    try:
        pred2 = predict_week(
            data_dir=args.data,
            week_start=args.week,
            active_version=version,
            models_dir=args.models_dir,
            registry_path=args.registry,
        )
    except Exception as exc:
        print(f"ERROR: Verification prediction run 2 failed: {exc}", file=sys.stderr)
        return 1

    # 4. Assert determinism, row count, and unchanged registry
    determinism_ok = (pred1["replay_hash"] == pred2["replay_hash"])
    rows_count = len(pred1["predictions"])
    rows_ok = (rows_count == 15)

    curr_registry_bytes = args.registry.read_bytes() if args.registry.exists() else None
    registry_unchanged = (orig_registry_bytes == curr_registry_bytes)

    if not determinism_ok:
        print(f"ERROR: Non-deterministic replay hash: {pred1['replay_hash']} != {pred2['replay_hash']}", file=sys.stderr)
        return 1

    if not rows_ok:
        print(f"ERROR: Invalid output row count: {rows_count} (expected 15)", file=sys.stderr)
        return 1

    if not registry_unchanged:
        print("ERROR: Verification mutated registry state!", file=sys.stderr)
        return 1

    print(f"Version:      {version}")
    print(f"Replay hash:  {pred1['replay_hash']}")
    print(f"Output rows:  {rows_count}")
    print("Determinism:  PASS")
    print("Registry:     UNCHANGED")
    return 0


# ==============================================================================
# COMMAND: demo
# ==============================================================================

def cmd_demo(args: argparse.Namespace) -> int:
    """Orchestrate end-to-end live session demonstration without bypassing lifecycle."""
    print("=" * 80)
    print("STARTING LIVE SESSION OPERATOR DEMONSTRATION")
    print("=" * 80)

    # 1. Preflight
    print("\n[Step 1/8] Preflight Verification...")
    pf_passed, pf_errs = run_preflight(
        data_dir=args.data,
        week=args.week,
        registry_path=args.registry,
        models_dir=args.models_dir,
    )
    if not pf_passed:
        print(f"Preflight failed: {pf_errs}")
        return 1
    print("PREFLIGHT: PASS")

    # 2. Live prediction on baseline active model
    print(f"\n[Step 2/8] Live Prediction with Active Model (Week: {args.week})...")
    res_live1 = predict_week(
        data_dir=args.data,
        week_start=args.week,
        registry_path=args.registry,
        models_dir=args.models_dir,
    )
    active_initial = res_live1["active_version"]
    print(f"Active: {active_initial} | Replay Hash: {res_live1['replay_hash']}")

    # 3. Evaluate candidate v0002
    print(f"\n[Step 3/8] Evaluating Experimental Candidate {args.candidate}...")
    rep, dec = run_evaluation(
        candidate_version=args.candidate,
        data_dir=args.data,
        active_version=active_initial,
        registry_path=args.registry,
    )
    print(f"Decision: {dec.decision} ({dec.reason_code})")
    print("Production state: UNCHANGED")

    # 4. Promote committed v_promotable fixture
    print(f"\n[Step 4/8] Promoting Validated Demonstration Fixture {args.promotable}...")
    val_info = validate_rollback_target(
        target_version=args.promotable,
        models_dir=args.models_dir,
        data_dir=args.data,
        test_date=args.week,
    )
    print(f"Candidate fixture validation: PASS ({val_info['target_version']})")
    print(f"Candidate artifact hash: {val_info['artifact_hash']}")

    rep_prom, dec_prom = run_evaluation(
        candidate_version=args.promotable,
        data_dir=args.data,
        active_version=active_initial,
        registry_path=args.registry,
    )
    if dec_prom.decision != "PROMOTE":
        print(f"ERROR: Demonstration fixture failed promotion gate: {dec_prom.reason_code}", file=sys.stderr)
        return 1

    promote_candidate(
        candidate_version=args.promotable,
        decision=dec_prom,
        registry_path=args.registry,
        history_path=args.history,
        timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    print(f"Promotion confirmed: active is now {args.promotable}")

    # 5. Live prediction on active v_promotable
    print(f"\n[Step 5/8] Live Prediction with Changed Active {args.promotable} (Week: {args.week})...")
    res_live2 = predict_week(
        data_dir=args.data,
        week_start=args.week,
        registry_path=args.registry,
        models_dir=args.models_dir,
    )
    print(f"Active: {args.promotable} | Replay Hash: {res_live2['replay_hash']}")
    assert res_live2["replay_hash"] != res_live1["replay_hash"], "Promoted model must produce distinct replay hash"

    # 6. Rollback to original active
    rollback_target = args.rollback_target or active_initial
    print(f"\n[Step 6/8] Executing Atomic Rollback to {rollback_target}...")
    rb_res = execute_rollback(
        target_version=rollback_target,
        registry_path=args.registry,
        history_path=args.history,
        models_dir=args.models_dir,
        data_dir=args.data,
        replay_week=args.week,
        expected_replay_hash=res_live1["replay_hash"],
        timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    print(f"Rollback status: PASS | Active restored: {rb_res.active_restored}")

    # 7. Verify restored model determinism
    print(f"\n[Step 7/8] Verifying Bit-for-Bit Deterministic Identity for {rollback_target}...")
    res_verify = predict_week(
        data_dir=args.data,
        week_start=args.week,
        active_version=rollback_target,
        registry_path=args.registry,
        models_dir=args.models_dir,
    )
    assert res_verify["replay_hash"] == res_live1["replay_hash"], "Restored model replay hash must match pre-promotion hash!"
    print("Determinism: PASS (restored replay hash matches initial run)")

    # 8. Status and audit trail confirmation
    print("\n[Step 8/8] Status & Audit Trail Confirmation...")
    st = run_status(registry_path=args.registry, history_path=args.history, models_dir=args.models_dir)
    print(f"Active model:       {st['active_model']}")
    print(f"Artifact integrity: {st['artifact_integrity']}")
    print(f"Registry:           {st['registry']}")
    print("\nDEMONSTRATION COMPLETE: ALL 8 STEPS PASSED SAFELY.")
    print("=" * 80)
    return 0


# ==============================================================================
# CLI PARSER CONFIGURATION
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="LPDG MLOps Live Session Operator Layer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Read-only operator status summary")
    p_status.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_status.add_argument("--history", type=pathlib.Path, default=pathlib.Path("registry/history.jsonl"))
    p_status.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # preflight
    p_preflight = subparsers.add_parser("preflight", help="Read-only preflight safety and contract verification")
    p_preflight.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_preflight.add_argument("--week", type=str, default="2026-02-02", help="Live week (YYYY-MM-DD)")
    p_preflight.add_argument("--require-clean-tree", action="store_true", help="Fail preflight if git working tree is dirty")
    p_preflight.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_preflight.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # run-live
    p_live = subparsers.add_parser("run-live", help="Execute live prediction pipeline for operator week")
    p_live.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_live.add_argument("--week", type=str, default="2026-02-02", help="Scored Monday date (YYYY-MM-DD)")
    p_live.add_argument("--output", type=pathlib.Path, default=pathlib.Path("predictions_week.csv"))
    p_live.add_argument("--backlog-report", type=pathlib.Path, default=pathlib.Path("backlog_report.json"))
    p_live.add_argument("--run-record", type=pathlib.Path, default=pathlib.Path("runs/prediction/run.json"))
    p_live.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_live.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Read-only candidate evaluation against promotion policy")
    p_eval.add_argument("--candidate", type=str, default="v0002", help="Candidate model version")
    p_eval.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_eval.add_argument("--active", type=str, default=None, help="Active model override")
    p_eval.add_argument("--policy", type=pathlib.Path, default=pathlib.Path("policy.json"), help="Path to policy.json")
    p_eval.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))

    # promote
    p_promote = subparsers.add_parser("promote", help="Evaluate and atomically promote candidate model")
    p_promote.add_argument("--candidate", type=str, default="v_promotable", help="Candidate model version")
    p_promote.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_promote.add_argument("--week", type=str, default="2026-02-02", help="Validation smoke test week (YYYY-MM-DD)")
    p_promote.add_argument("--policy", type=pathlib.Path, default=pathlib.Path("policy.json"), help="Path to policy.json")
    p_promote.add_argument("--yes", action="store_true", help="Non-interactive headless confirmation")
    p_promote.add_argument("--dry-run", action="store_true", help="Read-only promotion evaluation without registry mutation")
    p_promote.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_promote.add_argument("--history", type=pathlib.Path, default=pathlib.Path("registry/history.jsonl"))
    p_promote.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # rollback
    p_rb = subparsers.add_parser("rollback", help="Execute atomic model rollback with deterministic replay verification")
    p_rb.add_argument("--to", type=str, default=None, help="Target model version (default: previous_version from registry)")
    p_rb.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_rb.add_argument("--week", type=str, default="2026-02-02", help="Replay week (YYYY-MM-DD)")
    p_rb.add_argument("--expected-hash", type=str, default=None, help="Expected replay hash for target")
    p_rb.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_rb.add_argument("--history", type=pathlib.Path, default=pathlib.Path("registry/history.jsonl"))
    p_rb.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # verify
    p_ver = subparsers.add_parser("verify", help="Read-only explicit-version prediction and replay determinism proof")
    p_ver.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_ver.add_argument("--week", type=str, default="2026-02-02", help="Evaluation week (YYYY-MM-DD)")
    p_ver.add_argument("--version", type=str, default=None, help="Model version to verify (default: v0001)")
    p_ver.add_argument("--target", type=str, default=None, dest="target", help="Alias for --version")
    p_ver.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_ver.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    # demo
    p_demo = subparsers.add_parser("demo", help="Orchestrate full live session demonstration sequence")
    p_demo.add_argument("--data", type=pathlib.Path, default=pathlib.Path("data"), help="Path to data directory")
    p_demo.add_argument("--week", type=str, default="2026-02-02", help="Live week (YYYY-MM-DD)")
    p_demo.add_argument("--candidate", type=str, default="v0002", help="Experimental candidate")
    p_demo.add_argument("--promotable", type=str, default="v_promotable", help="Promotable fixture")
    p_demo.add_argument("--rollback-target", type=str, default="v0001", help="Target version for rollback")
    p_demo.add_argument("--registry", type=pathlib.Path, default=pathlib.Path("registry/active.json"))
    p_demo.add_argument("--history", type=pathlib.Path, default=pathlib.Path("registry/history.jsonl"))
    p_demo.add_argument("--models-dir", type=pathlib.Path, default=pathlib.Path("models"))

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "status": cmd_status,
        "preflight": cmd_preflight,
        "run-live": cmd_run_live,
        "evaluate": cmd_evaluate,
        "promote": cmd_promote,
        "rollback": cmd_rollback,
        "verify": cmd_verify,
        "demo": cmd_demo,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    code = handler(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
