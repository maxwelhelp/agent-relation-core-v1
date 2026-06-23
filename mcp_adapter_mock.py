#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from agent_relation_core_v1 import MemoryCase, Scenario
from relation_core_redteam_scenarios import M


@dataclass(frozen=True)
class MCPEvent:
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)


def text_tags(text: str) -> Set[str]:
    s = text.lower()
    tags: Set[str] = set()
    if "diagnostic" in s or "metrics" in s:
        tags.add("diagnostics_missing")
    if "metrics.csv" in s and "missing" in s:
        tags.add("metrics_csv_missing_diagnostics")
    if "final_report" in s and ("has" in s or "contains" in s):
        tags.add("final_report_has_diagnostics")
    if "import" in s or "module" in s:
        tags.add("import_error")
    if "secret" in s or "redaction" in s:
        tags.add("secret_leak")
    if "context" in s and ("stale" in s or "index" in s):
        tags.add("stale_context")
    if "core" in s or "algorithm" in s:
        tags.add("core_logic_error")
    if "dirty" in s or "uncommitted" in s or "user changes" in s:
        tags.add("user_changes_conflict")
    if "protected" in s:
        tags.add("protected_file")
    if "ambiguous" in s or "unclear" in s:
        tags.add("ambiguous_requirement")
    if "permission" in s:
        tags.add("permission_needed")
    if "running" in s:
        tags.add("job_running")
    if "already fixed" in s or "no-op" in s:
        tags.add("already_fixed")
    return tags


def events_to_scenario(
    task_id: str,
    events: List[MCPEvent],
    memories: List[MemoryCase] | None = None,
) -> Scenario:
    tags: Set[str] = set()
    evidence: Set[str] = set()
    constraints: Set[str] = set()
    summary_parts: List[str] = []

    for ev in events:
        data = ev.data
        text = " ".join(str(v) for v in data.values() if isinstance(v, (str, int, float)))
        tags |= text_tags(text)
        if text:
            summary_parts.append(f"{ev.kind}: {text}")

        if ev.kind == "task_start":
            tags |= set(data.get("tags", []))
            constraints |= set(data.get("constraints", []))

        elif ev.kind == "job_result":
            evidence.add("job_result_available")
            status = str(data.get("status", "")).lower()
            if status in {"running", "pending"}:
                constraints.add("job_running")
                tags.add("job_running")
            if data.get("patch_applied"):
                evidence.add("patch_applied")
            if data.get("regression"):
                evidence.add("regression_after_patch")
                tags.add("regression_after_patch")
            if data.get("already_fixed"):
                constraints.add("already_fixed")
                tags.add("already_fixed")
            if data.get("wide_change"):
                tags.add("wide_change")
                evidence.add("full_validation_needed")
            if data.get("error_type") == "core" or data.get("core_logic_error"):
                tags.add("core_logic_error")
                evidence.add("core_logic_error")

        elif ev.kind == "artifact_compare":
            evidence.add("job_result_available")
            if data.get("final_report_has_diagnostics"):
                evidence.add("final_report_has_diagnostics")
            if data.get("metrics_csv_missing_diagnostics"):
                evidence.add("metrics_csv_missing_diagnostics")
                tags.add("diagnostics_missing")
                tags.add("artifact_mismatch")
            if data.get("metrics_csv_has_diagnostics"):
                evidence.add("metrics_csv_has_diagnostics")
                constraints.add("already_fixed")
                tags.add("already_fixed")
            if data.get("deep_compare_done"):
                evidence.add("deep_compare_done")

        elif ev.kind == "smart_context":
            evidence.add("context_available")
            tags |= set(data.get("tags", []))
            evidence |= set(data.get("evidence", []))

        elif ev.kind == "read_symbol":
            if data.get("target") == "reporting":
                evidence.add("localized_reporting")
            if data.get("target") == "import":
                evidence.add("localized_import")
                evidence.add("read_symbol_done")
            if data.get("target") == "secret_filter":
                evidence.add("localized_secret_filter")
            if data.get("target") == "core":
                evidence.add("localized_core")
            if data.get("target") == "context_pack":
                evidence.add("localized_context_pack")

        elif ev.kind == "deep_compare":
            evidence.add("deep_compare_done")
            tags |= set(data.get("tags", []))
            evidence |= set(data.get("evidence", []))
            # Adapter bridge: if the task/context says core and deep_compare is done
            # after localized_core, then task-level core symptom becomes causal evidence.
            if "core_logic_error" in tags and "localized_core" in evidence:
                evidence.add("core_logic_error")

        elif ev.kind == "patch_apply":
            evidence.add("patch_applied")
            target = data.get("target")
            if target == "core":
                tags.add("core_logic_error")
            if target == "reporting":
                tags.add("diagnostics_missing")

        elif ev.kind == "dirty_guard":
            if data.get("dirty", True):
                constraints.add("dirty_guard")
                constraints.add("user_changes_conflict")
                tags.add("user_changes_conflict")

        elif ev.kind == "protected_files":
            if data.get("blocked", True):
                constraints.add("protected_file")
                constraints.add("permission_needed")

        elif ev.kind == "user_scope":
            scope = data.get("scope")
            if scope == "no_changes":
                constraints.add("user_no_changes")
                tags.add("user_no_changes")
            if scope == "ambiguous":
                constraints.add("ambiguous_requirement")
                tags.add("ambiguous_requirement")

    return Scenario(
        scenario_id=task_id,
        summary=" | ".join(summary_parts)[:500],
        tags=tags,
        evidence=evidence,
        constraints=constraints,
        memories=memories if memories is not None else M,
        expected=set(),
        forbidden=set(),
    )


def demo_event_traces() -> Dict[str, List[MCPEvent]]:
    return {
        "mcp_diag_need_localize": [
            MCPEvent("task_start", {"summary": "diagnostics missing after warmup9999"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("artifact_compare", {"final_report_has_diagnostics": True, "metrics_csv_missing_diagnostics": True}),
        ],
        "mcp_diag_ready_patch": [
            MCPEvent("task_start", {"summary": "diagnostics missing after warmup9999"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("artifact_compare", {"final_report_has_diagnostics": True, "metrics_csv_missing_diagnostics": True}),
            MCPEvent("read_symbol", {"target": "reporting"}),
        ],
        "mcp_dirty_guard_blocks_patch": [
            MCPEvent("task_start", {"summary": "diagnostics missing but user changes conflict"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("artifact_compare", {"final_report_has_diagnostics": True, "metrics_csv_missing_diagnostics": True}),
            MCPEvent("read_symbol", {"target": "reporting"}),
            MCPEvent("dirty_guard", {"dirty": True}),
        ],
        "mcp_core_needs_compare": [
            MCPEvent("task_start", {"summary": "core algorithm unit test failure"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("read_symbol", {"target": "core"}),
        ],
        "mcp_core_ready_patch": [
            MCPEvent("task_start", {"summary": "core algorithm unit test failure"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("read_symbol", {"target": "core"}),
            MCPEvent("deep_compare", {"done": True}),
        ],
        "mcp_user_no_changes": [
            MCPEvent("task_start", {"summary": "diagnostics missing but explain only"}),
            MCPEvent("job_result", {"status": "failed"}),
            MCPEvent("artifact_compare", {"final_report_has_diagnostics": True, "metrics_csv_missing_diagnostics": True}),
            MCPEvent("read_symbol", {"target": "reporting"}),
            MCPEvent("user_scope", {"scope": "no_changes"}),
        ],
        "mcp_running_job": [
            MCPEvent("task_start", {"summary": "wide validation needed"}),
            MCPEvent("job_result", {"status": "running", "patch_applied": True, "wide_change": True}),
        ],
        "mcp_already_fixed": [
            MCPEvent("task_start", {"summary": "diagnostics missing maybe"}),
            MCPEvent("job_result", {"status": "passed", "already_fixed": True}),
            MCPEvent("artifact_compare", {"metrics_csv_has_diagnostics": True, "final_report_has_diagnostics": True}),
        ],
    }
