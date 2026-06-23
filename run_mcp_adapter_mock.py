#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from agent_relation_core_v1 import RelationCore, decision_to_dict
from mcp_adapter_mock import demo_event_traces, events_to_scenario

EXPECTED = {
    "mcp_diag_need_localize": {"read_metrics_aggregation", "deep_compare"},
    "mcp_diag_ready_patch": {"patch_reporting"},
    "mcp_dirty_guard_blocks_patch": {"rollback"},
    "mcp_core_needs_compare": {"deep_compare", "read_symbol"},
    "mcp_core_ready_patch": {"patch_core_logic"},
    "mcp_user_no_changes": {"inspect_constraints", "stop_noop", "ask_user"},
    "mcp_running_job": {"wait_job"},
    "mcp_already_fixed": {"stop_noop", "inspect_constraints"},
}

FORBIDDEN = {
    "mcp_diag_need_localize": {"patch_reporting", "patch_core_logic"},
    "mcp_dirty_guard_blocks_patch": {"patch_reporting", "short_rerun", "full_rerun"},
    "mcp_core_needs_compare": {"patch_core_logic"},
    "mcp_user_no_changes": {"patch_reporting", "short_rerun", "full_rerun"},
    "mcp_running_job": {"short_rerun", "full_rerun", "patch_core_logic", "patch_reporting"},
    "mcp_already_fixed": {"patch_reporting", "short_rerun", "full_rerun"},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./mcp_adapter_mock_results")
    ap.add_argument("--show-all", action="store_true")
    ap.add_argument("--show-failures", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    core = RelationCore()

    rows = []
    details = []
    failures = []

    for task_id, events in demo_event_traces().items():
        scenario = events_to_scenario(task_id, events)
        decision = core.decide(scenario)
        expected = EXPECTED.get(task_id, set())
        forbidden = FORBIDDEN.get(task_id, set())
        top3 = [p.action for p in decision.proofs[:3]]
        ok = decision.selected in expected and decision.selected not in forbidden
        forbidden_hit = decision.selected in forbidden
        p = decision.proofs[0]
        row = {
            "task_id": task_id,
            "selected": decision.selected,
            "expected": "|".join(sorted(expected)),
            "forbidden": "|".join(sorted(forbidden)),
            "ok": int(ok),
            "forbidden_hit": int(forbidden_hit),
            "expected_in_top3": int(bool(set(top3) & expected)),
            "score": round(decision.score, 4),
            "support": round(p.support, 3),
            "contradiction": round(p.contradiction, 3),
            "evidence": round(p.evidence_sufficiency, 3),
            "risk": round(p.risk, 3),
            "uncertainty": round(p.uncertainty, 3),
            "tags": "|".join(sorted(scenario.tags)),
            "evidence_set": "|".join(sorted(scenario.evidence)),
            "constraints": "|".join(sorted(scenario.constraints)),
            "top3": " > ".join(top3),
        }
        rows.append(row)
        detail = {
            "task_id": task_id,
            "events": [{"kind": e.kind, "data": e.data} for e in events],
            "scenario": {
                "summary": scenario.summary,
                "tags": sorted(scenario.tags),
                "evidence": sorted(scenario.evidence),
                "constraints": sorted(scenario.constraints),
            },
            "expected": sorted(expected),
            "forbidden": sorted(forbidden),
            "decision": decision_to_dict(decision, top_k=8),
        }
        details.append(detail)
        if not ok:
            failures.append(detail)

    summary = {
        "tasks": len(rows),
        "success_rate": sum(r["ok"] for r in rows) / max(1, len(rows)),
        "forbidden_hit_rate": sum(r["forbidden_hit"] for r in rows) / max(1, len(rows)),
        "expected_in_top3_rate": sum(r["expected_in_top3"] for r in rows) / max(1, len(rows)),
        "failures": len(failures),
    }

    with (out_dir / "mcp_adapter_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (out_dir / "mcp_adapter_details.json").write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "mcp_adapter_failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "mcp_adapter_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== MCP adapter mock → RelationCore ===")
    print(f"tasks={summary['tasks']} success={summary['success_rate']:.3f} forbidden_hit={summary['forbidden_hit_rate']:.3f} expected_top3={summary['expected_in_top3_rate']:.3f} failures={summary['failures']}")
    print()
    print(f"{'task':34s} | {'selected':22s} | {'expected':35s} | ok | top3")
    print("-" * 130)
    for r in rows:
        if args.show_all or not r["ok"]:
            print(f"{r['task_id'][:34]:34s} | {r['selected'][:22]:22s} | {r['expected'][:35]:35s} | {r['ok']}  | {r['top3']}")

    if failures and args.show_failures:
        print("\n=== Adapter failures ===")
        for f in failures:
            print(f"\n[{f['task_id']}] selected={f['decision']['selected']} expected={f['expected']} forbidden={f['forbidden']}")
            print("scenario:", f["scenario"])
            for line in f["decision"]["explanation"]:
                print("  " + line)

    print("\nSaved:")
    print(" ", out_dir / "mcp_adapter_results.csv")
    print(" ", out_dir / "mcp_adapter_details.json")
    print(" ", out_dir / "mcp_adapter_failures.json")
    print(" ", out_dir / "mcp_adapter_summary.json")


if __name__ == "__main__":
    main()
