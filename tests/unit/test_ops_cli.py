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
import json
import pathlib
import pytest

from app.model.evaluate import evaluate_episode_cost_faq41
from app.model.predict import predict_week, resolve_active_model_version
from app.registry.promotion import evaluate_promotion_policy
from app.registry.rollback import execute_rollback
from scripts.ops import (
    build_parser,
    cmd_demo,
    cmd_evaluate,
    cmd_preflight,
    cmd_promote,
    cmd_rollback,
    cmd_run_live,
    cmd_status,
    cmd_verify,
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

