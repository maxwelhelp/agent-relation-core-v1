#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin integration API for MCP Local Operator.

The MCP side should not call RelationCore internals directly.
It should call relation_plan_check(events, candidate_actions=...).
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional

from agent_relation_core_v1 import MemoryCase, RelationCore, decision_to_dict
from mcp_adapter_mock import MCPEvent, demo_event_traces, events_to_scenario


def relation_plan_check(
    task_id: str,
    events: List[MCPEvent | Dict[str, Any]],
    candidate_actions: Optional[List[str]] = None,
    memories: Optional[List[MemoryCase]] = None,
    top_k: int = 8,
) -> Dict[str, Any]:
    """Convert MCP events to a Scenario and evaluate action proof.

    Parameters
    ----------
    task_id:
        Stable task/job id from MCP.
    events:
        List of MCPEvent or dicts shaped like {"kind": ..., "data": {...}}.
    candidate_actions:
        Optional allowed action set for this MCP call-site.
        Example before patch_apply: ["patch_reporting", "patch_core_logic", "ask_user", ...]
    memories:
        Optional relation memory cases. If omitted, demo memory bank is used.
    top_k:
        Number of proof entries to include.

    Returns
    -------
    JSON-serializable dict with selected action, proof summary, denied actions, and normalized scenario.
    """
    normalized_events: List[MCPEvent] = []
    for ev in events:
        if isinstance(ev, MCPEvent):
            normalized_events.append(ev)
        elif isinstance(ev, dict):
            normalized_events.append(MCPEvent(kind=str(ev.get("kind", "unknown")), data=dict(ev.get("data", {}))))
        else:
            raise TypeError(f"Unsupported event type: {type(ev)!r}")

    scenario = events_to_scenario(task_id, normalized_events, memories=memories)
    core = RelationCore()
    decision = core.decide(scenario, candidates=candidate_actions)

    top = decision.proofs[:top_k]
    denied = [p.action for p in top if p.decision == "deny"]
    allowed = [p.action for p in top if p.decision == "allow"]

    return {
        "task_id": task_id,
        "selected_action": decision.selected,
        "selected_class": decision.selected_class,
        "selected_decision": decision.decision,
        "score": decision.score,
        "allowed_top_actions": allowed,
        "denied_top_actions": denied,
        "scenario": {
            "summary": scenario.summary,
            "tags": sorted(scenario.tags),
            "evidence": sorted(scenario.evidence),
            "constraints": sorted(scenario.constraints),
        },
        "proof": decision_to_dict(decision, top_k=top_k),
    }


def _demo() -> int:
    failures = 0
    for task_id, events in demo_event_traces().items():
        result = relation_plan_check(task_id, events)
        print(f"{task_id:32s} -> {result['selected_action']}")
        if result["selected_decision"] != "allow":
            failures += 1
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="Run demo MCP event traces through relation_plan_check")
    ap.add_argument("--json", action="store_true", help="Print full JSON for demo traces")
    args = ap.parse_args()

    if args.demo or not args.json:
        rc = _demo()
        if not args.json:
            return rc

    if args.json:
        payload = {task_id: relation_plan_check(task_id, events) for task_id, events in demo_event_traces().items()}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
