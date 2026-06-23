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
from typing import Any, Dict, List, Optional

from agent_relation_core_v1 import MemoryCase, RelationCore, decision_to_dict
from mcp_adapter_mock import MCPEvent, demo_event_traces, events_to_scenario


def relation_plan_check(
    task_id: str,
    events: List[MCPEvent | Dict[str, Any]],
    candidate_actions: Optional[List[str]] = None,
    memories: Optional[List[MemoryCase]] = None,
    top_k: int = 8,
    compact: bool = False,
) -> Dict[str, Any]:
    """Convert MCP events to a Scenario and evaluate action proof."""
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

    base = {
        "task_id": task_id,
        "selected_action": decision.selected,
        "selected_class": decision.selected_class,
        "selected_decision": decision.decision,
        "score": round(decision.score, 6),
        "allowed_top_actions": allowed,
        "denied_top_actions": denied,
        "scenario": {
            "summary": scenario.summary,
            "tags": sorted(scenario.tags),
            "evidence": sorted(scenario.evidence),
            "constraints": sorted(scenario.constraints),
        },
    }

    if compact:
        base["top"] = [
            {
                "action": p.action,
                "class": p.action_class,
                "decision": p.decision,
                "score": round(p.score, 4),
                "risk": round(p.risk, 3),
                "evidence": round(p.evidence_sufficiency, 3),
                "denied": p.denied_reasons,
                "missing": p.missing_evidence,
            }
            for p in top
        ]
        return base

    base["proof"] = decision_to_dict(decision, top_k=top_k)
    return base


def relation_plan_check_compact(
    task_id: str,
    events: List[MCPEvent | Dict[str, Any]],
    candidate_actions: Optional[List[str]] = None,
    memories: Optional[List[MemoryCase]] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    return relation_plan_check(task_id, events, candidate_actions, memories, top_k=top_k, compact=True)


def _demo() -> int:
    failures = 0
    for task_id, events in demo_event_traces().items():
        result = relation_plan_check_compact(task_id, events, top_k=3)
        print(f"{task_id:32s} -> {result['selected_action']}")
        if result["selected_decision"] != "allow":
            failures += 1
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="Run demo MCP event traces as one-line decisions")
    ap.add_argument("--json", action="store_true", help="Print JSON for demo traces")
    ap.add_argument("--compact", action="store_true", help="Print compact JSON instead of full proof JSON")
    ap.add_argument("--task", default=None, help="Print only one demo task id")
    ap.add_argument("--top-k", type=int, default=5, help="Number of top proof/action entries")
    args = ap.parse_args()

    traces = demo_event_traces()
    if args.task:
        if args.task not in traces:
            print("available tasks:")
            for key in traces:
                print("  " + key)
            return 2
        traces = {args.task: traces[args.task]}

    if args.demo or (not args.json and not args.compact):
        return _demo()

    if args.json or args.compact:
        payload = {
            task_id: relation_plan_check(task_id, events, top_k=args.top_k, compact=args.compact)
            for task_id, events in traces.items()
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
