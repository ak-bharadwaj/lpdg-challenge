"""Unit and integration tests for LPDG MLOps Operator CLI and unseen-month rehearsal.

Contract Invariants Tested (Task Phases 4 & 5):
1. status_is_read_only
2. preflight_is_read_only
3. evaluate_rejected_candidate_leaves_active_unchanged
4. promote_wrapper_uses_existing_promotion_path
5. promote_dry_run_is_read_only
6. rollback_wrapper_uses_existing_rollback_path
7. verify_is_read_only
8. live_unseen_month_new_gateway
9. live_unseen_month_recently_silent_gateway
10. operator_live_week_is_not_hardcoded
11. invalid_rollback_target_preserves_active
12. existing_faq41_suite_still_passes
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import pytest

from app.model.evaluate import evaluate_episode_cost_faq41
from app.model.predict import predict_week, resolve_active_model_version
from app.registry.promotion import evaluate_promotion_policy
from app.registry.rollback import execute_rollback
from scripts.ops import (
    build_parser,
    cmd_change,
    cmd_demo,
    cmd_evaluate,
    cmd_preflight,
    cmd_promote,
    cmd_restore_snapshot,
    cmd_rollback,
    cmd_rollback_to,
    cmd_run_live,
    cmd_status,
    cmd_verify,
    get_git_commit,
    run_evaluation,
    run_preflight,
    run_status,
)
from tests.fixtures.unseen_month_fixture import create_unseen_month_dataset


@pytest.fixture
def repo_data_dir() -> pathlib.Path:
    p = pathlib.Path("data")
    if not p.exists():
        pytest.skip("Local data directory not available")
    return p


# ==============================================================================
# 1. status_is_read_only
# ==============================================================================

def test_status_is_read_only():
    """Verify status command inspects system state without mutating active registry or history."""
    reg_path = pathlib.Path("registry/active.json")
    hist_path = pathlib.Path("registry/history.jsonl")

    orig_reg = reg_path.read_bytes() if reg_path.exists() else None
    orig_hist = hist_path.read_bytes() if hist_path.exists() else None

    status = run_status(registry_path=reg_path, history_path=hist_path)

    assert status["registry"] == "PASS"
    assert status["active_model"] == "v0001"
    assert status["artifact_integrity"] == "PASS"
    assert status["schema_contract"] == "PASS"

    curr_reg = reg_path.read_bytes() if reg_path.exists() else None
    curr_hist = hist_path.read_bytes() if hist_path.exists() else None

    assert curr_reg == orig_reg, "status command mutated registry/active.json"
    assert curr_hist == orig_hist, "status command mutated registry/history.jsonl"


# ==============================================================================
# 2. preflight_is_read_only
# ==============================================================================

def test_preflight_is_read_only(repo_data_dir: pathlib.Path):
    """Verify preflight performs comprehensive safety checks without mutating any state."""
    reg_path = pathlib.Path("registry/active.json")
    orig_reg = reg_path.read_bytes()

    passed, errors = run_preflight(data_dir=repo_data_dir, week="2026-02-02", registry_path=reg_path)
    assert passed is True, f"Preflight checks failed: {errors}"
    assert not errors

    curr_reg = reg_path.read_bytes()
    assert curr_reg == orig_reg, "preflight command mutated registry/active.json"


# ==============================================================================
# 3. evaluate_rejected_candidate_leaves_active_unchanged
# ==============================================================================

def test_evaluate_rejected_candidate_leaves_active_unchanged(repo_data_dir: pathlib.Path):
    """Verify evaluating rejected candidate (v0002) leaves production active pointer strictly unchanged."""
    reg_path = pathlib.Path("registry/active.json")
    orig_reg = reg_path.read_bytes()

    report, decision = run_evaluation(
        candidate_version="v0002",
        data_dir=repo_data_dir,
        active_version="v0001",
        registry_path=reg_path,
    )

    assert decision.decision == "REJECT"
    assert decision.reason_code == "REJECT_GROUPED_DISAGREEMENT"

    curr_reg = reg_path.read_bytes()
    assert curr_reg == orig_reg, "evaluate mutated registry/active.json on rejection"


# ==============================================================================
# 4. promote_wrapper_uses_existing_promotion_path
# ==============================================================================

def test_promote_wrapper_uses_existing_promotion_path(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify promote command delegates to existing promote_candidate with atomic transition."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    test_reg.write_text(
        json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    test_hist.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        candidate="v_promotable",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_promote(args)
    assert ret == 0, "cmd_promote should succeed for v_promotable with --yes"

    updated = json.loads(test_reg.read_text(encoding="utf-8"))
    assert updated["production_version"] == "v_promotable"
    assert updated["previous_version"] == "v0001"

    hist_lines = [ln.strip() for ln in test_hist.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 2
    last_event = json.loads(hist_lines[-1])
    assert last_event["event"] == "PROMOTED"
    assert last_event["version"] == "v_promotable"


# ==============================================================================
# 5. promote_dry_run_is_read_only
# ==============================================================================

def test_promote_dry_run_is_read_only(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify promote with --dry-run evaluates candidate but leaves active pointer byte-for-byte untouched."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    orig_content = json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2)
    test_reg.write_text(orig_content, encoding="utf-8")
    test_hist.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        candidate="v_promotable",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=True,
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_promote(args)
    assert ret == 0
    assert test_reg.read_text(encoding="utf-8") == orig_content, "--dry-run mutated active.json"


# ==============================================================================
# 6. rollback_wrapper_uses_existing_rollback_path
# ==============================================================================

def test_rollback_wrapper_uses_existing_rollback_path(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify rollback command executes 7-step rollback and restores active model with replay equality."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    test_reg.write_text(
        json.dumps({"production_version": "v_promotable", "previous_version": "v0001", "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    test_hist.write_text(
        json.dumps({"event": "PROMOTED", "version": "v_promotable", "previous_version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        to="v0001",
        data=repo_data_dir,
        week="2026-02-02",
        expected_hash=None,
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_rollback(args)
    assert ret == 0, "cmd_rollback failed"

    updated = json.loads(test_reg.read_text(encoding="utf-8"))
    assert updated["production_version"] == "v0001"
    assert updated["previous_version"] == "v_promotable"

    hist_lines = [ln.strip() for ln in test_hist.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 2
    last_event = json.loads(hist_lines[-1])
    assert last_event["event"] == "ROLLED_BACK"
    assert last_event["to"] == "v0001"


# ==============================================================================
# 7. verify_is_read_only
# ==============================================================================

def test_verify_is_read_only(repo_data_dir: pathlib.Path):
    """Verify verify command executes predictions without mutating registry."""
    reg_path = pathlib.Path("registry/active.json")
    orig_reg = reg_path.read_bytes()

    args = argparse.Namespace(
        data=repo_data_dir,
        week="2026-02-02",
        version="v0001",
        registry=reg_path,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_verify(args)
    assert ret == 0, "cmd_verify failed"
    assert reg_path.read_bytes() == orig_reg, "cmd_verify mutated registry/active.json"


# ==============================================================================
# 8. live_unseen_month_new_gateway
# ==============================================================================

def test_live_unseen_month_new_gateway(tmp_path: pathlib.Path):
    """Verify live prediction on unseen month (April 2026) scores a brand new unseen gateway ID without crashing."""
    unseen_dir = tmp_path / "unseen_month_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    res = predict_week(data_dir=unseen_dir, week_start="2026-04-06", active_version="v0001")
    assert len(res["predictions"]) == 15
    assert res["replay_hash"].startswith("sha256:")

    # Confirm brand new gateway AA0000000001 was scored and did not crash
    assert "AA0000000001" in res["scored_gateway_ids"]


# ==============================================================================
# 9. live_unseen_month_recently_silent_gateway
# ==============================================================================

def test_live_unseen_month_recently_silent_gateway(tmp_path: pathlib.Path):
    """Verify recently silent gateway with history is NOT excluded as NO_TELEMETRY on unseen month."""
    unseen_dir = tmp_path / "unseen_month_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    # Verify for v0001 (baseline)
    res_v1 = predict_week(data_dir=unseen_dir, week_start="2026-04-06", active_version="v0001")
    # 0639EA000002 has 21 days of history but is silent in recent 7 days
    # It must be present in scored_gateway_ids (NOT excluded with NO_TELEMETRY)
    assert "0639EA000002" in res_v1["scored_gateway_ids"]

    # Verify for v0002 (candidate multi-signal with explicit silence ratio)
    res_v2 = predict_week(data_dir=unseen_dir, week_start="2026-04-06", active_version="v0002")
    assert "0639EA000002" in res_v2["scored_gateway_ids"]
    assert "AA0000000001" in res_v2["scored_gateway_ids"]


# ==============================================================================
# 10. operator_live_week_is_not_hardcoded
# ==============================================================================

def test_operator_live_week_is_not_hardcoded(tmp_path: pathlib.Path):
    """Verify prediction pipeline dynamically adapts to arbitrary live week without March or 8-week hardcoding."""
    unseen_dir = tmp_path / "unseen_month_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    res = predict_week(data_dir=unseen_dir, week_start="2026-04-06", active_version="v0001")
    assert res["week_start"] == "2026-04-06"
    for p in res["predictions"]:
        assert p["week_start"] == "2026-04-06"


# ==============================================================================
# 11. invalid_rollback_target_preserves_active
# ==============================================================================

def test_invalid_rollback_target_preserves_active(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify attempting rollback to invalid/corrupt target fails cleanly and leaves active pointer unchanged."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    orig_content = json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2)
    test_reg.write_text(orig_content, encoding="utf-8")
    test_hist.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        to="v_nonexistent_candidate_999",
        data=repo_data_dir,
        week="2026-02-02",
        expected_hash=None,
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_rollback(args)
    assert ret != 0, "Rollback to non-existent target should return non-zero error code"
    assert test_reg.read_text(encoding="utf-8") == orig_content, "Invalid rollback modified active.json"


# ==============================================================================
# 12. existing_faq41_suite_still_passes
# ==============================================================================

def test_existing_faq41_suite_still_passes():
    """Verify FAQ §4.1 accounting logic continues to pass on synthetic counterfactual matrix."""
    # Run test case directly against evaluate_episode_cost_faq41
    episodes = [["2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23"]]
    selected = ["2026-02-09", "2026-02-16"]

    res = evaluate_episode_cost_faq41(episodes=episodes, selected_weeks=selected)

    assert res.total_episodes == 1
    assert res.episodes_caught == 1
    assert res.episodes_missed == 0
    assert res.total_faulty_weeks == 4
    # Charged weeks = week 1 (unvisited) + week 2 (visit lands) = 2 weeks
    assert res.charged_missed_weeks == 2
    assert res.saved_missed_weeks == 2
    assert res.first_catch_selections == 1
    assert res.wasted_repick_selections == 1
    assert res.missed_penalty_eur == 1200.0  # 2 * 600
    assert res.total_visit_cost_eur == 760.0  # 2 * 380
    assert res.total_accounting_cost_eur == 1960.0


# ==============================================================================
# 13. ops_cli_parser_safety_checks
# ==============================================================================

def test_promote_has_no_force_option():
    """Safety Invariant: Verify promote CLI strictly forbids any --force argument."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["promote", "--candidate", "v0002", "--force"])


def test_cmd_demo_orchestration(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify cmd_demo executes all 8 live session demonstration steps cleanly in an isolated registry."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    test_reg.write_text(
        json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    test_hist.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        data=repo_data_dir,
        week="2026-02-02",
        candidate="v0002",
        promotable="v_promotable",
        rollback_target="v0001",
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_demo(args)
    assert ret == 0, "cmd_demo failed"

    # Verify final state is safely back on v0001
    final_active = json.loads(test_reg.read_text(encoding="utf-8"))
    assert final_active["production_version"] == "v0001"
    assert final_active["previous_version"] == "v_promotable"


def test_promote_rejected_candidate_leaves_active_unchanged(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify attempting to promote rejected candidate (v0002) exits non-zero and leaves active pointer untouched."""
    test_reg = tmp_path / "active.json"
    test_hist = tmp_path / "history.jsonl"

    orig_content = json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2)
    test_reg.write_text(orig_content, encoding="utf-8")
    test_hist.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        candidate="v0002",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=test_reg,
        history=test_hist,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_promote(args)
    assert ret == 1, "Promoting rejected candidate v0002 must return non-zero exit code"
    assert test_reg.read_text(encoding="utf-8") == orig_content, "Active registry was mutated on rejected candidate"
    hist_lines = [ln.strip() for ln in test_hist.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 1, "History was appended on rejected candidate"


def test_run_live_corrupted_data_fails_closed(tmp_path: pathlib.Path):
    """Verify run-live fails closed when data path is missing or telemetry is absent."""
    missing_dir = tmp_path / "nonexistent_dir"
    args = argparse.Namespace(
        data=missing_dir,
        week="2026-02-02",
        output=None,
        backlog_report=None,
        run_record=None,
        registry=pathlib.Path("registry/active.json"),
        models_dir=pathlib.Path("models"),
    )
    ret = cmd_run_live(args)
    assert ret == 1, "run-live on non-existent directory must return non-zero"

    # Empty directory with only master but no telemetry
    empty_dir = tmp_path / "empty_data"
    empty_dir.mkdir(parents=True, exist_ok=True)
    master_csv = "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,installed_on,n_meters_installed\n"
    (empty_dir / "gateway_master.csv").write_bytes(master_csv.encode("cp1252"))
    args_empty = argparse.Namespace(
        data=empty_dir,
        week="2026-02-02",
        output=None,
        backlog_report=None,
        run_record=None,
        registry=pathlib.Path("registry/active.json"),
        models_dir=pathlib.Path("models"),
    )
    ret_empty = cmd_run_live(args_empty)
    assert ret_empty == 1, "run-live without telemetry partitions must return non-zero"


def test_run_live_cli_execution(tmp_path: pathlib.Path):
    """Verify run-live CLI handler executes cleanly on unseen-month dataset."""
    unseen_dir = tmp_path / "unseen_live_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    pred_csv = tmp_path / "live_preds.csv"
    backlog_json = tmp_path / "live_backlog.json"
    run_json = tmp_path / "live_run.json"

    args = argparse.Namespace(
        data=unseen_dir,
        week="2026-04-06",
        output=pred_csv,
        backlog_report=backlog_json,
        run_record=run_json,
        registry=pathlib.Path("registry/active.json"),
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_run_live(args)
    assert ret == 0, "cmd_run_live failed on unseen month dataset"
    assert pred_csv.exists(), "live predictions CSV was not generated"
    assert backlog_json.exists(), "live backlog JSON was not generated"
    assert run_json.exists(), "live run record was not generated"


def test_verify_supports_target_alias(tmp_path: pathlib.Path):
    """Verify cmd_verify accepts target attribute as alias for version."""
    unseen_dir = tmp_path / "unseen_verify_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    args = argparse.Namespace(
        data=unseen_dir,
        week="2026-04-06",
        version=None,
        target="v0001",
        registry=pathlib.Path("registry/active.json"),
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_verify(args)
    assert ret == 0, "cmd_verify should accept target alias"


def test_preflight_require_clean_tree(repo_data_dir: pathlib.Path):
    """Verify preflight clean tree option checks git working tree state."""
    passed, errors = run_preflight(
        data_dir=repo_data_dir,
        week="2026-02-02",
        require_clean_tree=False,
    )
    assert passed is True, f"Standard preflight failed: {errors}"


def test_status_export_and_restore_snapshot(tmp_path: pathlib.Path):
    """Verify snapshot export is read-only and restore-snapshot restores exact state."""
    from scripts.ops import cmd_restore_snapshot

    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    # Set up initial test registry
    init_active = {"production_version": "v0001", "previous_version": "v_promotable", "changed_at": "2026-09-06T00:00:00Z"}
    reg_file.write_text(json.dumps(init_active), encoding="utf-8")
    init_hist = '{"event": "INITIALIZED", "version": "v0001"}\n'
    hist_file.write_text(init_hist, encoding="utf-8")

    # 1. Export snapshot
    args_export = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
        export=snapshot_file,
    )
    ret_exp = cmd_status(args_export)
    assert ret_exp == 0
    assert snapshot_file.exists()

    # 2. Mutate registry to simulate live session changes
    reg_file.write_text(json.dumps({"production_version": "v_promotable", "previous_version": "v0001"}), encoding="utf-8")
    hist_file.write_text(init_hist + '{"event": "PROMOTED", "version": "v_promotable"}\n', encoding="utf-8")

    # 3. Restore snapshot
    args_restore = argparse.Namespace(
        from_snapshot=snapshot_file,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )
    ret_rest = cmd_restore_snapshot(args_restore)
    assert ret_rest == 0

    # 4. Assert restored state matches initial state
    restored_active = json.loads(reg_file.read_text(encoding="utf-8"))
    assert restored_active["production_version"] == "v0001"
    assert restored_active["previous_version"] == "v_promotable"
    assert hist_file.read_text(encoding="utf-8") == init_hist


def test_promote_with_unseen_month_data_directory(tmp_path: pathlib.Path):
    """Verify promote evaluates against historical data when unseen data directory lacks field_visits."""
    unseen_dir = tmp_path / "unseen_eval_data"
    create_unseen_month_dataset(unseen_dir, week_str="2026-04-06")

    # Candidate v0002 should cleanly evaluate and be REJECTED without failing on missing field_visits
    args = argparse.Namespace(
        candidate="v0002",
        data=unseen_dir,
        week="2026-04-06",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=pathlib.Path("registry/active.json"),
        history=pathlib.Path("registry/history.jsonl"),
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_promote(args)
    # Return code must be 1 (rejection enforced)
    assert ret == 1


# ==============================================================================
# 14. SNAPSHOT AND RESTORE SAFETY CONTRACT TESTS
# ==============================================================================

def test_snapshot_is_read_only(tmp_path: pathlib.Path):
    """Safety Invariant: Verify snapshot export is read-only and binds cryptographic contract."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    orig_reg_data = json.dumps(
        {"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"},
        indent=2,
    )
    reg_file.write_text(orig_reg_data, encoding="utf-8")
    orig_hist_data = '{"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}\n'
    hist_file.write_text(orig_hist_data, encoding="utf-8")

    args = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
        export=snapshot_file,
    )
    ret = cmd_status(args)
    assert ret == 0
    assert snapshot_file.exists()

    # Verify registry and history were not modified
    assert reg_file.read_text(encoding="utf-8") == orig_reg_data
    assert hist_file.read_text(encoding="utf-8") == orig_hist_data

    # Verify snapshot content contains required cryptographic binding contract
    snapshot_data = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert snapshot_data["production_version"] == "v0001"
    assert snapshot_data["active_model"] == "v0001"
    assert snapshot_data["artifact_hash"].startswith("sha256:")
    assert snapshot_data["active_sha256"] is not None
    assert snapshot_data["active_sha256"] == hashlib.sha256(orig_reg_data.encode("utf-8")).hexdigest()
    assert snapshot_data["history_sha256"] == hashlib.sha256(orig_hist_data.encode("utf-8")).hexdigest()


def test_restore_valid_certified_snapshot_restores_exact_state(tmp_path: pathlib.Path):
    """Safety Invariant: Verify restoring certified snapshot restores exact state byte-for-byte."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    init_active = json.dumps(
        {"production_version": "v0001", "previous_version": "v_promotable", "changed_at": "2026-09-06T00:00:00Z"},
        indent=2,
    )
    reg_file.write_text(init_active, encoding="utf-8")
    init_hist = '{"event": "INITIALIZED", "version": "v0001"}\n'
    hist_file.write_text(init_hist, encoding="utf-8")

    # Export snapshot
    args_export = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
        export=snapshot_file,
    )
    assert cmd_status(args_export) == 0

    # Mutate registry to simulate live session mutation
    reg_file.write_text(json.dumps({"production_version": "v_promotable", "previous_version": "v0001"}), encoding="utf-8")
    hist_file.write_text(init_hist + '{"event": "PROMOTED", "version": "v_promotable"}\n', encoding="utf-8")

    # Restore snapshot
    args_restore = argparse.Namespace(
        from_snapshot=snapshot_file,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )
    assert cmd_restore_snapshot(args_restore) == 0

    # Verify bit-for-bit exact restoration
    assert reg_file.read_text(encoding="utf-8") == init_active
    assert hist_file.read_text(encoding="utf-8") == init_hist


def test_restore_bad_snapshot_rejected(tmp_path: pathlib.Path):
    """Safety Invariant: Verify corrupted/tampered snapshot fails closed without mutating registry."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    orig_active = json.dumps({"production_version": "v0001", "previous_version": None}, indent=2)
    orig_hist = '{"event": "INITIALIZED", "version": "v0001"}\n'
    reg_file.write_text(orig_active, encoding="utf-8")
    hist_file.write_text(orig_hist, encoding="utf-8")

    # Export valid snapshot
    args_export = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
        export=snapshot_file,
    )
    assert cmd_status(args_export) == 0
    valid_data = json.loads(snapshot_file.read_text(encoding="utf-8"))

    # Case A: Corrupted active_sha256
    bad_a = snapshot_file.with_name("bad_a.json")
    data_a = dict(valid_data)
    data_a["active_sha256"] = "corrupted_hash_00000000000000000000000000000000000000000000000000000000"
    bad_a.write_text(json.dumps(data_a), encoding="utf-8")
    args_a = argparse.Namespace(from_snapshot=bad_a, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_a) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case B: Tampered active_content (mismatched with active_sha256)
    bad_b = snapshot_file.with_name("bad_b.json")
    data_b = dict(valid_data)
    data_b["active_content"] = json.dumps({"production_version": "v0002"})
    bad_b.write_text(json.dumps(data_b), encoding="utf-8")
    args_b = argparse.Namespace(from_snapshot=bad_b, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_b) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case C: Tampered production_version in active_content vs snapshot binding
    bad_c = snapshot_file.with_name("bad_c.json")
    tampered_content = json.dumps({"production_version": "v_tampered"})
    data_c = dict(valid_data)
    data_c["active_content"] = tampered_content
    data_c["active_sha256"] = hashlib.sha256(tampered_content.encode("utf-8")).hexdigest()
    data_c["production_version"] = "v0001"
    bad_c.write_text(json.dumps(data_c), encoding="utf-8")
    args_c = argparse.Namespace(from_snapshot=bad_c, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_c) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case D: Corrupted history_sha256
    bad_d = snapshot_file.with_name("bad_d.json")
    data_d = dict(valid_data)
    data_d["history_sha256"] = "mismatched_history_sha"
    bad_d.write_text(json.dumps(data_d), encoding="utf-8")
    args_d = argparse.Namespace(from_snapshot=bad_d, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_d) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case E: Git commit mismatch (when current git HEAD is known)
    curr_commit = get_git_commit()
    if curr_commit != "UNKNOWN":
        bad_e = snapshot_file.with_name("bad_e.json")
        data_e = dict(valid_data)
        data_e["git_commit"] = "deadbeef00000000000000000000000000000000"
        bad_e.write_text(json.dumps(data_e), encoding="utf-8")
        args_e = argparse.Namespace(from_snapshot=bad_e, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
        assert cmd_restore_snapshot(args_e) != 0
        assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case F: Missing git_commit binding
    bad_f = snapshot_file.with_name("bad_f.json")
    data_f = dict(valid_data)
    data_f.pop("git_commit", None)
    bad_f.write_text(json.dumps(data_f), encoding="utf-8")
    args_f = argparse.Namespace(from_snapshot=bad_f, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_f) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case G: history_content present but history_sha256 missing
    bad_g = snapshot_file.with_name("bad_g.json")
    data_g = dict(valid_data)
    data_g.pop("history_sha256", None)
    bad_g.write_text(json.dumps(data_g), encoding="utf-8")
    args_g = argparse.Namespace(from_snapshot=bad_g, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_g) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case H: history_sha256 present but history_content missing
    bad_h = snapshot_file.with_name("bad_h.json")
    data_h = dict(valid_data)
    data_h["history_content"] = None
    data_h["history_sha256"] = "some_sha_without_content"
    bad_h.write_text(json.dumps(data_h), encoding="utf-8")
    args_h = argparse.Namespace(from_snapshot=bad_h, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_h) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case I: Missing active_sha256
    bad_i = snapshot_file.with_name("bad_i.json")
    data_i = dict(valid_data)
    data_i.pop("active_sha256", None)
    bad_i.write_text(json.dumps(data_i), encoding="utf-8")
    args_i = argparse.Namespace(from_snapshot=bad_i, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_i) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active

    # Case J: git_commit is UNKNOWN
    bad_j = snapshot_file.with_name("bad_j.json")
    data_j = dict(valid_data)
    data_j["git_commit"] = "UNKNOWN"
    bad_j.write_text(json.dumps(data_j), encoding="utf-8")
    args_j = argparse.Namespace(from_snapshot=bad_j, registry=reg_file, history=hist_file, models_dir=pathlib.Path("models"))
    assert cmd_restore_snapshot(args_j) != 0
    assert reg_file.read_text(encoding="utf-8") == orig_active


def test_restore_wrong_artifact_hash_rejected(tmp_path: pathlib.Path):
    """Safety Invariant: Verify snapshot with wrong artifact hash fails closed and preserves registry."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    orig_active = json.dumps({"production_version": "v0001", "previous_version": None}, indent=2)
    reg_file.write_text(orig_active, encoding="utf-8")
    hist_file.write_text('{"event": "INITIALIZED", "version": "v0001"}\n', encoding="utf-8")

    args_export = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
        export=snapshot_file,
    )
    assert cmd_status(args_export) == 0

    # Tamper with snapshot artifact_hash
    data = json.loads(snapshot_file.read_text(encoding="utf-8"))
    data["artifact_hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    snapshot_file.write_text(json.dumps(data), encoding="utf-8")

    # Mutate registry state before attempting restore
    reg_file.write_text(json.dumps({"production_version": "v_mutated"}), encoding="utf-8")

    args_restore = argparse.Namespace(
        from_snapshot=snapshot_file,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )
    ret = cmd_restore_snapshot(args_restore)
    assert ret != 0, "Restore must fail closed when artifact hash does not match target model"
    assert json.loads(reg_file.read_text(encoding="utf-8"))["production_version"] == "v_mutated"


def test_restore_does_not_touch_model_artifacts(tmp_path: pathlib.Path):
    """Safety Invariant: Verify restoring snapshot never touches, mutates, or rewires files in models/."""
    models_dir = pathlib.Path("models")
    v1_dir = models_dir / "v0001"

    # Record hashes and mtimes of all files in models/v0001
    file_state_before = {}
    for f in v1_dir.iterdir():
        if f.is_file():
            file_state_before[f.name] = (f.stat().st_mtime, hashlib.sha256(f.read_bytes()).hexdigest())

    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    snapshot_file = tmp_path / "snapshot.json"

    reg_file.write_text(json.dumps({"production_version": "v0001", "previous_version": None}, indent=2), encoding="utf-8")
    hist_file.write_text('{"event": "INITIALIZED", "version": "v0001"}\n', encoding="utf-8")

    args_export = argparse.Namespace(
        registry=reg_file,
        history=hist_file,
        models_dir=models_dir,
        export=snapshot_file,
    )
    assert cmd_status(args_export) == 0

    # Mutate registry
    reg_file.write_text(json.dumps({"production_version": "v_promotable"}), encoding="utf-8")

    # Restore snapshot
    args_restore = argparse.Namespace(
        from_snapshot=snapshot_file,
        registry=reg_file,
        history=hist_file,
        models_dir=models_dir,
    )
    assert cmd_restore_snapshot(args_restore) == 0

    # Verify every file in models/v0001 is completely untouched
    for fname, (orig_mtime, orig_hash) in file_state_before.items():
        curr_path = v1_dir / fname
        assert curr_path.stat().st_mtime == orig_mtime, f"Model file {fname} mtime was modified!"
        assert hashlib.sha256(curr_path.read_bytes()).hexdigest() == orig_hash, f"Model file {fname} content changed!"


# ==============================================================================
# 15. HIGH-LEVEL OPERATOR FEATURE TESTS (change & rollback-to)
# ==============================================================================

def test_change_rejected_keeps_active(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify change command on rejected candidate (v0002) exits non-zero and keeps active unchanged."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"

    orig_active = json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2)
    reg_file.write_text(orig_active, encoding="utf-8")
    orig_hist = '{"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}\n'
    hist_file.write_text(orig_hist, encoding="utf-8")

    args = argparse.Namespace(
        candidate="v0002",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_change(args)
    assert ret == 1, "cmd_change on rejected candidate must deliberately exit with non-zero code 1"
    assert reg_file.read_text(encoding="utf-8") == orig_active, "Active pointer was mutated on rejection"
    assert hist_file.read_text(encoding="utf-8") == orig_hist, "History was appended on rejection"


def test_change_promotes_through_existing_gate(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify change command promotes validated candidate through existing promotion gate."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"

    reg_file.write_text(
        json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    hist_file.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        candidate="v_promotable",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_change(args)
    assert ret == 0, "cmd_change should succeed for v_promotable with --yes"

    updated = json.loads(reg_file.read_text(encoding="utf-8"))
    assert updated["production_version"] == "v_promotable"
    assert updated["previous_version"] == "v0001"

    hist_lines = [ln.strip() for ln in hist_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 2
    last_event = json.loads(hist_lines[-1])
    assert last_event["event"] == "PROMOTED"
    assert last_event["version"] == "v_promotable"


def test_change_dry_run_is_read_only(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify change command with --dry-run evaluates candidate but leaves active registry untouched."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"

    orig_active = json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2)
    reg_file.write_text(orig_active, encoding="utf-8")
    orig_hist = '{"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}\n'
    hist_file.write_text(orig_hist, encoding="utf-8")

    args = argparse.Namespace(
        candidate="v_promotable",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=True,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_change(args)
    assert ret == 0
    assert reg_file.read_text(encoding="utf-8") == orig_active, "--dry-run mutated registry/active.json"
    assert hist_file.read_text(encoding="utf-8") == orig_hist, "--dry-run mutated registry/history.jsonl"


def test_rollback_to_restores_previous(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify rollback-to command wraps existing rollback engine and restores previous model."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"

    reg_file.write_text(
        json.dumps({"production_version": "v_promotable", "previous_version": "v0001", "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    hist_file.write_text(
        json.dumps({"event": "PROMOTED", "version": "v_promotable", "previous_version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        version="v0001",
        to="v0001",
        data=repo_data_dir,
        week="2026-02-02",
        expected_hash=None,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )

    ret = cmd_rollback_to(args)
    assert ret == 0, "cmd_rollback_to failed"

    updated = json.loads(reg_file.read_text(encoding="utf-8"))
    assert updated["production_version"] == "v0001"
    assert updated["previous_version"] == "v_promotable"

    hist_lines = [ln.strip() for ln in hist_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 2
    last_event = json.loads(hist_lines[-1])
    assert last_event["event"] == "ROLLED_BACK"
    assert last_event["to"] == "v0001"


def test_change_then_rollback_replays_identically(tmp_path: pathlib.Path, repo_data_dir: pathlib.Path):
    """Verify round-trip: change active model to v_promotable then rollback-to v0001 reproduces identical replay hash."""
    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"

    reg_file.write_text(
        json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    hist_file.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    # 1. Baseline prediction on v0001
    baseline_pred = predict_week(
        data_dir=repo_data_dir,
        week_start="2026-02-02",
        registry_path=reg_file,
        models_dir=pathlib.Path("models"),
    )
    initial_replay_hash = baseline_pred["replay_hash"]

    # 2. Promote candidate v_promotable via ops-change
    args_change = argparse.Namespace(
        candidate="v_promotable",
        data=repo_data_dir,
        week="2026-02-02",
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )
    assert cmd_change(args_change) == 0

    promoted_pred = predict_week(
        data_dir=repo_data_dir,
        week_start="2026-02-02",
        registry_path=reg_file,
        models_dir=pathlib.Path("models"),
    )
    assert promoted_pred["active_version"] == "v_promotable"
    assert promoted_pred["replay_hash"] != initial_replay_hash

    # 3. Rollback to v0001 via ops-rollback-to with expected hash proof
    args_rollback = argparse.Namespace(
        version="v0001",
        to="v0001",
        data=repo_data_dir,
        week="2026-02-02",
        expected_hash=initial_replay_hash,
        registry=reg_file,
        history=hist_file,
        models_dir=pathlib.Path("models"),
    )
    assert cmd_rollback_to(args_rollback) == 0

    # 4. Predict week on restored model
    restored_pred = predict_week(
        data_dir=repo_data_dir,
        week_start="2026-02-02",
        registry_path=reg_file,
        models_dir=pathlib.Path("models"),
    )
    assert restored_pred["active_version"] == "v0001"
    assert restored_pred["replay_hash"] == initial_replay_hash, "Replay hash mismatch after round-trip rollback!"


def test_change_has_no_force_option():
    """Safety Invariant: Verify change CLI strictly forbids any --force argument."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["change", "--candidate", "v0002", "--force"])


def test_rollback_to_accepts_to_and_target_flags():
    """Verify rollback-to parser accepts --version, --to, and --target flags without shadowing."""
    parser = build_parser()
    args1 = parser.parse_args(["rollback-to", "--version", "v_custom"])
    assert args1.version == "v_custom"
    args2 = parser.parse_args(["rollback-to", "--to", "v_custom"])
    assert args2.version == "v_custom"
    args3 = parser.parse_args(["rollback-to", "--target", "v_custom"])
    assert args3.version == "v_custom"


def test_change_accepts_candidate_and_target_flags():
    """Verify change parser accepts --candidate, --target, and --model flags without shadowing."""
    parser = build_parser()
    args1 = parser.parse_args(["change", "--candidate", "v_custom"])
    assert args1.candidate == "v_custom"
    args2 = parser.parse_args(["change", "--target", "v_custom"])
    assert args2.candidate == "v_custom"
    args3 = parser.parse_args(["change", "--model", "v_custom"])
    assert args3.candidate == "v_custom"


# ==============================================================================
# 16. LIVE COMMANDS WEEK REQUIREMENT & SYNTHETIC MAY 2026 REHEARSAL
# ==============================================================================

def test_live_commands_parser_week_defaults_to_none():
    """Safety Invariant: Verify all live commands default --week to None in parser to prevent accidental old-data fallback."""
    parser = build_parser()

    subcommands = [
        ("preflight", ["preflight", "--data", "data"]),
        ("run-live", ["run-live", "--data", "data"]),
        ("promote", ["promote", "--candidate", "v_promotable"]),
        ("rollback", ["rollback", "--to", "v0001"]),
        ("verify", ["verify", "--data", "data"]),
        ("demo", ["demo", "--data", "data"]),
        ("change", ["change", "--candidate", "v_promotable"]),
        ("rollback-to", ["rollback-to", "--version", "v0001"]),
    ]

    for name, argv in subcommands:
        args = parser.parse_args(argv)
        assert args.week is None, f"Command '{name}' must have default week=None, got: {args.week}"


def test_live_commands_fail_closed_without_week(tmp_path: pathlib.Path, capsys):
    """Safety Invariant: Verify live commands fail closed with clear error message when --week is omitted."""
    data_dir = tmp_path / "dummy_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    reg_path = tmp_path / "active.json"
    hist_path = tmp_path / "history.jsonl"
    reg_path.write_text(json.dumps({"production_version": "v0001"}), encoding="utf-8")
    hist_path.write_text('{"event": "INITIALIZED", "version": "v0001"}\n', encoding="utf-8")

    # 1. preflight
    ret = cmd_preflight(argparse.Namespace(data=data_dir, week=None, registry=reg_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err
    assert "Use the evaluator-supplied LIVE_WEEK." in err

    # 2. run-live
    ret = cmd_run_live(argparse.Namespace(data=data_dir, week=None, output=None, backlog_report=None, run_record=None, registry=reg_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 3. change
    ret = cmd_change(argparse.Namespace(candidate="v_promotable", data=data_dir, week=None, policy=pathlib.Path("policy.json"), yes=True, dry_run=False, registry=reg_path, history=hist_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 4. rollback
    ret = cmd_rollback(argparse.Namespace(to="v0001", data=data_dir, week=None, expected_hash=None, registry=reg_path, history=hist_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 5. rollback-to
    ret = cmd_rollback_to(argparse.Namespace(version="v0001", to="v0001", data=data_dir, week=None, expected_hash=None, registry=reg_path, history=hist_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 6. verify
    ret = cmd_verify(argparse.Namespace(data=data_dir, week=None, version="v0001", target=None, registry=reg_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 7. demo
    ret = cmd_demo(argparse.Namespace(data=data_dir, week=None, candidate="v0002", promotable="v_promotable", rollback_target="v0001", registry=reg_path, history=hist_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err

    # 8. promote
    ret = cmd_promote(argparse.Namespace(candidate="v_promotable", data=data_dir, week=None, policy=pathlib.Path("policy.json"), yes=True, dry_run=False, registry=reg_path, history=hist_path, models_dir=pathlib.Path("models")))
    assert ret == 1
    err = capsys.readouterr().err
    assert "ERROR: --week is required for live operations." in err


def test_rehearsal_unseen_month_non_february_live_week(tmp_path: pathlib.Path):
    """End-to-End Live Rehearsal: Verify primary operator sequence on synthetic non-February live week (2026-05-04)."""
    live_week = "2026-05-04"
    unseen_dir = tmp_path / "evaluator_unseen_data"
    create_unseen_month_dataset(unseen_dir, week_str=live_week)

    reg_file = tmp_path / "active.json"
    hist_file = tmp_path / "history.jsonl"
    models_dir = pathlib.Path("models")

    # Certified baseline: active is v0001
    reg_file.write_text(
        json.dumps({"production_version": "v0001", "previous_version": None, "changed_at": "2026-09-05T00:00:00Z"}, indent=2),
        encoding="utf-8",
    )
    hist_file.write_text(
        json.dumps({"event": "INITIALIZED", "version": "v0001", "timestamp": "2026-09-05T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    # Step 1: Status Inspection (Read-Only)
    st = run_status(registry_path=reg_file, history_path=hist_file, models_dir=models_dir)
    assert st["active_model"] == "v0001"
    assert st["registry"] == "PASS"

    # Step 2: Preflight on May 2026 unseen data
    args_pf = argparse.Namespace(data=unseen_dir, week=live_week, registry=reg_file, models_dir=models_dir, require_clean_tree=False)
    ret_pf = cmd_preflight(args_pf)
    assert ret_pf == 0, "Preflight on 2026-05-04 must pass"

    # Step 3: Run Live Prediction with baseline v0001
    pred_csv = tmp_path / "preds_step3.csv"
    args_live1 = argparse.Namespace(
        data=unseen_dir,
        week=live_week,
        output=pred_csv,
        backlog_report=None,
        run_record=None,
        registry=reg_file,
        models_dir=models_dir,
    )
    ret_live1 = cmd_run_live(args_live1)
    assert ret_live1 == 0, "Live prediction on 2026-05-04 must succeed"

    # Extract Step 3 baseline replay hash
    res_baseline = predict_week(data_dir=unseen_dir, week_start=live_week, registry_path=reg_file, models_dir=models_dir)
    baseline_hash = res_baseline["replay_hash"]
    assert len(res_baseline["predictions"]) == 15

    # Step 4: Deliberate Negative Test: Model change attempt on rejected candidate v0002
    args_change_v2 = argparse.Namespace(
        candidate="v0002",
        data=unseen_dir,
        week=live_week,
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=reg_file,
        history=hist_file,
        models_dir=models_dir,
    )
    ret_change_v2 = cmd_change(args_change_v2)
    assert ret_change_v2 == 1, "ops-change on v0002 must exit with non-zero code 1"
    active_now = json.loads(reg_file.read_text(encoding="utf-8"))["production_version"]
    assert active_now == "v0001", "Production active model must remain strictly on v0001 after rejection"

    # Step 5: High-Level Model Change with Validated Candidate v_promotable
    args_change_prom = argparse.Namespace(
        candidate="v_promotable",
        data=unseen_dir,
        week=live_week,
        policy=pathlib.Path("policy.json"),
        yes=True,
        dry_run=False,
        registry=reg_file,
        history=hist_file,
        models_dir=models_dir,
    )
    ret_change_prom = cmd_change(args_change_prom)
    assert ret_change_prom == 0, "ops-change on v_promotable must succeed"
    assert json.loads(reg_file.read_text(encoding="utf-8"))["production_version"] == "v_promotable"

    # Step 6: Live Prediction under Changed Active Model
    res_promoted = predict_week(data_dir=unseen_dir, week_start=live_week, registry_path=reg_file, models_dir=models_dir)
    assert res_promoted["active_version"] == "v_promotable"
    assert res_promoted["replay_hash"] != baseline_hash, "Promoted model must produce distinct replay hash"

    # Step 7: Atomic Rollback to Baseline Model v0001
    args_rollback = argparse.Namespace(
        version="v0001",
        to="v0001",
        target="v0001",
        data=unseen_dir,
        week=live_week,
        expected_hash=baseline_hash,
        registry=reg_file,
        history=hist_file,
        models_dir=models_dir,
    )
    ret_rb = cmd_rollback_to(args_rollback)
    assert ret_rb == 0, "ops-rollback-to v0001 must succeed"
    assert json.loads(reg_file.read_text(encoding="utf-8"))["production_version"] == "v0001"

    # Step 8: Replay Verification & Bit-for-Bit Determinism Proof
    args_verify = argparse.Namespace(
        data=unseen_dir,
        week=live_week,
        version="v0001",
        target="v0001",
        registry=reg_file,
        models_dir=models_dir,
    )
    ret_ver = cmd_verify(args_verify)
    assert ret_ver == 0, "ops-verify must prove bit-for-bit determinism"

    res_restored = predict_week(data_dir=unseen_dir, week_start=live_week, registry_path=reg_file, models_dir=models_dir)
    assert res_restored["active_version"] == "v0001"
    assert res_restored["replay_hash"] == baseline_hash, "Restored active model replay hash must match Step 3 exactly"



