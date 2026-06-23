#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List
from agent_relation_core_v1 import Scenario, MemoryCase


def mem(case_id: str, action: str, tags=(), constraints=(), outcome="success", verified=True, same_constraints=True, stale=False, poisoned=False):
    return MemoryCase(case_id, case_id.replace("_", " "), action, set(tags), set(constraints), outcome, verified, same_constraints, stale, poisoned)


M = [
    mem("verified_reporting_fix", "patch_reporting", ["diagnostics_missing", "artifact_mismatch", "metrics_csv_missing_diagnostics"]),
    mem("verified_import_wiring", "patch_import_wiring", ["import_error", "module_move", "path_wiring"]),
    mem("verified_secret_filter", "patch_secret_filter", ["secret_leak", "filter_leak"]),
    mem("verified_context_reindex", "reindex_context", ["stale_context", "context_pack_stale", "symbol_missing"]),
    mem("verified_context_patch", "patch_context_pack", ["context_pack_stale", "index_bug", "localized_context_pack"]),
    mem("verified_core_patch", "patch_core_logic", ["core_logic_error", "algorithm_bug", "unit_test_failure"]),
    mem("verified_rollback", "rollback", ["dirty_guard", "regression_after_patch", "user_changes_conflict"], ["dirty_guard"]),
    mem("failed_core_on_reporting", "patch_core_logic", ["diagnostics_missing", "artifact_mismatch"], outcome="fail"),
    mem("failed_config_on_secret", "patch_config", ["secret_leak", "filter_leak"], outcome="fail"),
]


def cases() -> List[Scenario]:
    S: List[Scenario] = []
    add = S.append

    add(Scenario("A01_no_logs_unknown_failure", "unknown test failure, no logs/context loaded", {"unknown_failure", "need_logs"}, set(), set(), M, {"job_result", "smart_context"}, {"patch_core_logic", "patch_reporting", "short_rerun"}))
    add(Scenario("A02_logs_loaded_unknown_failure", "logs loaded but no symbol/localization yet", {"unknown_failure", "need_context"}, {"job_result_available"}, set(), M, {"read_symbol", "deep_compare", "smart_context"}, {"patch_core_logic", "patch_reporting"}))
    add(Scenario("A03_artifact_mismatch_need_compare", "two artifacts disagree, no compare yet", {"artifact_mismatch", "diagnostics_missing"}, {"job_result_available", "metrics_csv_missing_diagnostics"}, set(), M, {"deep_compare", "read_metrics_aggregation"}, {"patch_reporting"}))
    add(Scenario("A04_symbol_missing_due_to_stale_index", "read_symbol cannot find symbol because context index is stale", {"symbol_missing", "stale_context"}, {"symbol_missing", "context_pack_stale"}, {"stale_context"}, M, {"reindex_context"}, {"patch_context_pack", "patch_core_logic"}))
    add(Scenario("A05_symbol_missing_but_generator_localized", "symbol missing traced to context pack generator bug, localized", {"symbol_missing", "context_pack_stale", "index_bug"}, {"context_pack_stale", "localized_context_pack"}, set(), M, {"patch_context_pack"}, {"reindex_context", "patch_core_logic"}))

    add(Scenario("B01_reporting_patch_ready", "diagnostics missing in metrics.csv while final_report has them; reporting localized", {"diagnostics_missing", "artifact_mismatch"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting", "deep_compare_done"}, set(), M, {"patch_reporting"}, {"patch_core_logic", "patch_config"}))
    add(Scenario("B02_import_patch_ready", "module moved; import path localized", {"import_error", "module_move", "path_wiring"}, {"job_result_available", "import_error", "localized_import", "read_symbol_done"}, set(), M, {"patch_import_wiring"}, {"patch_core_logic", "patch_config"}))
    add(Scenario("B03_secret_patch_ready", "secret leak localized to redaction filter", {"secret_leak", "filter_leak"}, {"job_result_available", "secret_leak", "localized_secret_filter"}, set(), M, {"patch_secret_filter"}, {"patch_config", "patch_core_logic"}))
    add(Scenario("B04_core_patch_ready_high_blast", "unit test localizes real algorithm bug", {"core_logic_error", "algorithm_bug", "unit_test_failure"}, {"job_result_available", "core_logic_error", "localized_core", "deep_compare_done"}, set(), M, {"patch_core_logic"}, {"patch_reporting", "patch_config"}))
    add(Scenario("B05_config_patch_ready", "config mismatch localized", {"config_error", "env_mismatch"}, {"job_result_available", "config_error", "localized_config"}, set(), [mem("verified_config_patch", "patch_config", ["config_error", "env_mismatch"])], {"patch_config"}, {"patch_core_logic"}))

    add(Scenario("C01_dirty_guard_blocks_reporting_patch", "diagnostics evidence complete but user changes conflict; do not patch", {"diagnostics_missing", "artifact_mismatch", "user_changes_conflict"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, {"dirty_guard", "user_changes_conflict"}, M, {"rollback"}, {"patch_reporting", "patch_core_logic", "short_rerun"}))
    add(Scenario("C02_user_no_changes_blocks_all", "user asked only inspect, no file changes or rerun", {"diagnostics_missing", "user_no_changes"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, {"user_no_changes"}, M, {"stop_noop", "inspect_constraints"}, {"patch_reporting", "short_rerun", "full_rerun"}))
    add(Scenario("C03_ambiguous_blocks_patch", "ambiguous request, may be export field or diagnostics", {"diagnostics_missing", "ambiguous_requirement"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, {"ambiguous_requirement"}, M, {"ask_user"}, {"patch_reporting", "patch_config"}))
    add(Scenario("C04_permission_needed_blocks_dependency_config", "config fix may add dependency; permission required", {"config_error", "permission_needed"}, {"job_result_available", "config_error", "localized_config"}, {"permission_needed"}, [mem("verified_config_patch", "patch_config", ["config_error"])], {"ask_user"}, {"patch_config"}))
    add(Scenario("C05_job_running_blocks_patch_and_verify", "job still running, wait before any patch or verify", {"job_running", "diagnostics_missing"}, {"final_report_has_diagnostics", "metrics_csv_missing_diagnostics"}, {"job_running"}, M, {"wait_job"}, {"patch_reporting", "short_rerun", "full_rerun"}))
    add(Scenario("C06_protected_secret_scope", "secret leak is in protected compliance file", {"secret_leak", "filter_leak", "protected_file"}, {"job_result_available", "secret_leak", "localized_secret_filter"}, {"protected_file", "permission_needed"}, M, {"ask_user"}, {"patch_secret_filter", "patch_core_logic"}))
    add(Scenario("C07_protected_core_file", "core bug localized but protected file requires permission", {"core_logic_error", "protected_file"}, {"job_result_available", "core_logic_error", "localized_core"}, {"protected_file", "permission_needed"}, M, {"ask_user"}, {"patch_core_logic"}))
    add(Scenario("C08_already_fixed_stop_even_memory_says_patch", "latest result already contains expected diagnostics", {"already_fixed", "no_op", "diagnostics_missing"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_has_diagnostics"}, {"already_fixed"}, M + [mem("old_success_reporting", "patch_reporting", ["diagnostics_missing"])], {"stop_noop"}, {"patch_reporting", "short_rerun"}))

    add(Scenario("D01_small_patch_needs_short_rerun", "small patch applied; verify with short rerun", {"verify_needed"}, {"patch_applied"}, set(), M, {"short_rerun"}, {"full_rerun", "patch_core_logic"}))
    add(Scenario("D02_wide_change_needs_full_rerun", "wide patch touched several modules", {"wide_change", "full_validation_needed"}, {"patch_applied", "full_validation_needed"}, set(), M, {"full_rerun"}, {"patch_core_logic", "patch_reporting"}))
    add(Scenario("D03_regression_after_patch_needs_rollback", "after patch, regression appears", {"regression_after_patch"}, {"patch_applied", "job_result_available", "regression_after_patch", "deep_compare_done"}, set(), M, {"rollback"}, {"patch_core_logic", "full_rerun"}))
    add(Scenario("D04_flaky_timeout_after_patch", "verification timed out once; can rerun short or wait", {"flaky_timeout", "verify_needed"}, {"patch_applied"}, set(), M, {"short_rerun", "wait_job"}, {"patch_core_logic", "full_rerun"}))

    add(Scenario("E01_poison_success_same_text_wrong_action", "diagnostics task with poisoned old success saying patch_config", {"diagnostics_missing", "artifact_mismatch"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, set(), [mem("poison_success_config", "patch_config", ["diagnostics_missing", "artifact_mismatch"], outcome="success", verified=False, same_constraints=False, poisoned=True), mem("verified_reporting", "patch_reporting", ["diagnostics_missing", "artifact_mismatch"], outcome="success", verified=True)], {"patch_reporting"}, {"patch_config", "patch_core_logic"}))
    add(Scenario("E02_stale_success_import_now_core", "same import-looking error but current evidence says core logic", {"import_error", "core_logic_error", "algorithm_bug"}, {"job_result_available", "core_logic_error", "localized_core", "deep_compare_done"}, set(), [mem("stale_import_success", "patch_import_wiring", ["import_error"], outcome="success", verified=True, stale=True), mem("verified_core_current", "patch_core_logic", ["core_logic_error", "algorithm_bug"], outcome="success", verified=True)], {"patch_core_logic"}, {"patch_import_wiring"}))
    add(Scenario("E03_failed_same_action_memory_blocks_commit", "reporting evidence complete but recent verified same-action failed trace under same constraints", {"diagnostics_missing", "artifact_mismatch"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, set(), [mem("recent_reporting_failed", "patch_reporting", ["diagnostics_missing", "artifact_mismatch"], outcome="fail", verified=True, same_constraints=True), mem("old_reporting_success", "patch_reporting", ["diagnostics_missing"], outcome="success", verified=True, stale=True)], {"deep_compare", "read_metrics_aggregation", "smart_context"}, {"patch_reporting"}))
    add(Scenario("E04_memory_empty_but_evidence_ready", "no memory exists but evidence is sufficient for reporting patch", {"diagnostics_missing", "artifact_mismatch"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, set(), [], {"patch_reporting"}, {"patch_core_logic"}))

    add(Scenario("F01_diagnostics_text_but_rollback_kind", "diagnostics-looking task, but uncommitted user changes conflict with patch", {"diagnostics_missing", "artifact_mismatch", "user_changes_conflict"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, {"dirty_guard", "user_changes_conflict"}, [mem("poison_reporting_dirty", "patch_reporting", ["diagnostics_missing"], ["dirty_guard"], outcome="success", verified=False, poisoned=True), mem("verified_dirty_rollback", "rollback", ["dirty_guard", "user_changes_conflict"], ["dirty_guard"], outcome="success")], {"rollback"}, {"patch_reporting"}))
    add(Scenario("F02_secret_text_but_already_fixed", "secret leak mentioned but latest logs show redaction fixed", {"secret_leak", "already_fixed", "no_op"}, {"job_result_available", "metrics_csv_has_diagnostics"}, {"already_fixed"}, [mem("old_secret_patch", "patch_secret_filter", ["secret_leak"], outcome="success")], {"stop_noop"}, {"patch_secret_filter"}))
    add(Scenario("F03_import_text_but_stale_index", "import symbol not found because index stale, not code error", {"import_error", "symbol_missing", "stale_context"}, {"symbol_missing", "context_pack_stale"}, {"stale_context"}, [mem("old_import_patch", "patch_import_wiring", ["import_error"], outcome="success")], {"reindex_context"}, {"patch_import_wiring"}))
    add(Scenario("F04_core_logic_and_dirty_guard", "core logic error localized but dirty guard active", {"core_logic_error", "algorithm_bug", "user_changes_conflict"}, {"job_result_available", "core_logic_error", "localized_core"}, {"dirty_guard", "user_changes_conflict"}, M, {"rollback"}, {"patch_core_logic"}))
    add(Scenario("F05_wide_change_and_job_running", "wide verification needed but job is still running", {"wide_change", "full_validation_needed", "job_running"}, {"patch_applied", "full_validation_needed"}, {"job_running"}, M, {"wait_job"}, {"full_rerun", "short_rerun"}))

    add(Scenario("G01_reporting_ready_but_deep_compare_missing_optional", "reporting evidence complete but deep compare not done; patch should still be okay", {"diagnostics_missing", "artifact_mismatch"}, {"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, set(), M, {"patch_reporting"}, {"deep_compare", "patch_core_logic"}))
    add(Scenario("G02_core_high_blast_need_compare", "core bug suspected but no deep compare yet", {"core_logic_error", "algorithm_bug"}, {"job_result_available", "core_logic_error", "localized_core"}, set(), M, {"deep_compare", "read_symbol"}, {"patch_core_logic"}))
    add(Scenario("G03_secret_leak_no_localization", "secret leak detected but filter code not localized", {"secret_leak", "filter_leak"}, {"job_result_available", "secret_leak"}, set(), M, {"smart_context", "read_symbol"}, {"patch_secret_filter"}))
    add(Scenario("G04_config_error_no_permission_issue", "config env mismatch localized, no permission needed", {"config_error", "env_mismatch"}, {"job_result_available", "config_error", "localized_config"}, set(), [mem("verified_config_patch", "patch_config", ["config_error", "env_mismatch"])], {"patch_config"}, {"ask_user"}))
    add(Scenario("G05_unknown_failure_with_conflicting_memories", "unknown failure with many irrelevant successful memories", {"unknown_failure"}, {"job_result_available"}, set(), M + [mem("irrelevant_secret_success", "patch_secret_filter", ["secret_leak"], outcome="success"), mem("irrelevant_reporting_success", "patch_reporting", ["diagnostics_missing"], outcome="success")], {"read_symbol", "deep_compare", "smart_context"}, {"patch_secret_filter", "patch_reporting", "patch_core_logic"}))

    add(Scenario("H01_no_patch_no_rerun_user_scope", "user asks explain only; no change and no rerun", {"user_no_changes", "no_op"}, set(), {"user_no_changes"}, M, {"stop_noop", "inspect_constraints"}, {"patch_reporting", "short_rerun", "full_rerun"}))
    add(Scenario("H02_full_rerun_not_justified", "small patch already applied; do not full rerun", {"verify_needed"}, {"patch_applied"}, set(), M, {"short_rerun"}, {"full_rerun"}))
    add(Scenario("H03_patch_not_justified_without_evidence", "user says maybe metrics wrong but no logs/artifacts loaded", {"diagnostics_missing"}, set(), set(), M, {"job_result", "smart_context"}, {"patch_reporting", "patch_core_logic"}))
    add(Scenario("H04_stop_when_no_op_even_with_stale_memory", "current state no-op; stale memory suggests patch", {"already_fixed", "no_op"}, {"job_result_available"}, {"already_fixed"}, [mem("stale_reporting_success", "patch_reporting", ["diagnostics_missing"], stale=True)], {"stop_noop"}, {"patch_reporting"}))

    return S
