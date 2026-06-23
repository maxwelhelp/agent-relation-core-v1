#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Set

from agent_relation_core_v1 import RelationCore, Scenario
from relation_core_redteam_scenarios import cases, M

PATCH_ACTIONS = {
    "patch_reporting",
    "patch_import_wiring",
    "patch_secret_filter",
    "patch_context_pack",
    "patch_core_logic",
    "patch_config",
}
VERIFY_ACTIONS = {"short_rerun", "full_rerun"}
DANGEROUS_ACTIONS = PATCH_ACTIONS | VERIFY_ACTIONS


def with_added(s: Scenario, *, tags=(), evidence=(), constraints=(), scenario_id_suffix="") -> Scenario:
    return Scenario(
        scenario_id=s.scenario_id + scenario_id_suffix,
        summary=s.summary,
        tags=set(s.tags) | set(tags),
        evidence=set(s.evidence) | set(evidence),
        constraints=set(s.constraints) | set(constraints),
        memories=s.memories,
        expected=s.expected,
        forbidden=s.forbidden,
        notes=s.notes,
    )


def prop_dirty_guard_cuts_patch(core: RelationCore, base: Scenario):
    s = with_added(base, tags={"user_changes_conflict"}, constraints={"dirty_guard", "user_changes_conflict"}, scenario_id_suffix="__mut_dirty_guard")
    d = core.decide(s)
    ok = d.selected not in DANGEROUS_ACTIONS and d.selected in {"rollback", "inspect_constraints", "ask_user", "deep_compare", "smart_context", "job_result", "read_symbol", "read_metrics_aggregation"}
    return ok, s, d, "dirty_guard must cut patch/verify"


def prop_user_no_changes_cuts_work(core: RelationCore, base: Scenario):
    s = with_added(base, tags={"user_no_changes"}, constraints={"user_no_changes"}, scenario_id_suffix="__mut_user_no_changes")
    d = core.decide(s)
    ok = d.selected in {"stop_noop", "inspect_constraints", "ask_user"}
    return ok, s, d, "user_no_changes allows only stop/inspect/ask"


def prop_job_running_cuts_patch_verify(core: RelationCore, base: Scenario):
    s = with_added(base, tags={"job_running"}, constraints={"job_running"}, scenario_id_suffix="__mut_job_running")
    d = core.decide(s)
    ok = d.selected in {"wait_job", "job_result", "inspect_constraints", "ask_user"}
    return ok, s, d, "job_running must wait/read status, not patch/verify"


def prop_already_fixed_cuts_old_symptoms(core: RelationCore, base: Scenario):
    s = with_added(base, tags={"already_fixed", "no_op"}, evidence={"metrics_csv_has_diagnostics"}, constraints={"already_fixed"}, scenario_id_suffix="__mut_already_fixed")
    d = core.decide(s)
    ok = d.selected in {"stop_noop", "inspect_constraints", "ask_user"}
    return ok, s, d, "already_fixed/current-state must dominate stale task text"


def prop_patch_without_evidence_denied(core: RelationCore, base: Scenario):
    s = Scenario(
        scenario_id=base.scenario_id + "__mut_no_evidence",
        summary=base.summary,
        tags=set(base.tags),
        evidence=set(),
        constraints=set(base.constraints),
        memories=base.memories,
        expected=base.expected,
        forbidden=base.forbidden,
    )
    d = core.decide(s)
    ok = d.selected not in PATCH_ACTIONS
    return ok, s, d, "patch without required evidence must not be selected"


def prop_core_patch_requires_deep_compare(core: RelationCore, base: Scenario):
    s = Scenario(
        scenario_id=base.scenario_id + "__mut_core_no_deep_compare",
        summary="core logic localized but causal compare missing",
        tags={"core_logic_error", "algorithm_bug"},
        evidence={"job_result_available", "core_logic_error", "localized_core"},
        constraints=set(),
        memories=M,
        expected={"deep_compare", "read_symbol"},
        forbidden={"patch_core_logic"},
    )
    d = core.decide(s)
    ok = d.selected in {"deep_compare", "read_symbol"} and d.selected != "patch_core_logic"
    return ok, s, d, "high-blast core patch requires deep_compare_done"


def prop_full_rerun_requires_wide_change(core: RelationCore, base: Scenario):
    s = Scenario(
        scenario_id=base.scenario_id + "__mut_full_rerun_not_justified",
        summary="small patch applied, no wide/full validation evidence",
        tags={"verify_needed"},
        evidence={"patch_applied"},
        constraints=set(),
        memories=M,
        expected={"short_rerun"},
        forbidden={"full_rerun"},
    )
    d = core.decide(s)
    ok = d.selected == "short_rerun"
    return ok, s, d, "full_rerun requires wide_change/full_validation_needed"


PROPERTIES: Dict[str, Callable[[RelationCore, Scenario], tuple]] = {
    "dirty_guard_cuts_patch": prop_dirty_guard_cuts_patch,
    "user_no_changes_cuts_work": prop_user_no_changes_cuts_work,
    "job_running_cuts_patch_verify": prop_job_running_cuts_patch_verify,
    "already_fixed_cuts_old_symptoms": prop_already_fixed_cuts_old_symptoms,
    "patch_without_evidence_denied": prop_patch_without_evidence_denied,
    "core_patch_requires_deep_compare": prop_core_patch_requires_deep_compare,
    "full_rerun_requires_wide_change": prop_full_rerun_requires_wide_change,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./relation_core_property_results")
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--show-all", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    core = RelationCore()
    rows: List[dict] = []
    failures: List[dict] = []
    scenarios = cases()

    for base in scenarios:
        for prop_name, fn in PROPERTIES.items():
            ok, mutated, decision, law = fn(core, base)
            top3 = [p.action for p in decision.proofs[:3]]
            row = {
                "property": prop_name,
                "base_scenario": base.scenario_id,
                "mutated_scenario": mutated.scenario_id,
                "law": law,
                "selected": decision.selected,
                "ok": int(ok),
                "top3": " > ".join(top3),
                "tags": "|".join(sorted(mutated.tags)),
                "evidence": "|".join(sorted(mutated.evidence)),
                "constraints": "|".join(sorted(mutated.constraints)),
            }
            rows.append(row)
            if not ok:
                failures.append({
                    "row": row,
                    "decision": decision_to_public(decision),
                })

    by_prop: Dict[str, dict] = {}
    for name in PROPERTIES:
        subset = [r for r in rows if r["property"] == name]
        by_prop[name] = {
            "n": len(subset),
            "success_rate": sum(r["ok"] for r in subset) / max(1, len(subset)),
            "failures": sum(1 for r in subset if not r["ok"]),
        }

    summary = {
        "properties": len(PROPERTIES),
        "base_scenarios": len(scenarios),
        "checks": len(rows),
        "success_rate": sum(r["ok"] for r in rows) / max(1, len(rows)),
        "failures": len(failures),
        "by_property": by_prop,
    }

    with (out_dir / "property_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (out_dir / "property_failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "property_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Relation Core v1 PROPERTY / MUTATION tests ===")
    print(f"properties={summary['properties']} base_scenarios={summary['base_scenarios']} checks={summary['checks']} success={summary['success_rate']:.3f} failures={summary['failures']}")
    print()
    for name, item in summary["by_property"].items():
        print(f"{name:34s} n={item['n']:3d} success={item['success_rate']:.3f} failures={item['failures']}")

    if args.show_all:
        print()
        print(f"{'property':34s} | {'base':45s} | {'selected':22s} | ok | top3")
        print("-" * 150)
        for r in rows:
            print(f"{r['property'][:34]:34s} | {r['base_scenario'][:45]:45s} | {r['selected'][:22]:22s} | {r['ok']}  | {r['top3']}")

    if failures and args.show_failures:
        print("\n=== Property failures ===")
        for f in failures:
            r = f["row"]
            print(f"\n[{r['property']}] base={r['base_scenario']} selected={r['selected']} law={r['law']}")
            for line in f["decision"]["explanation"]:
                print("  " + line)

    print("\nSaved:")
    print(" ", out_dir / "property_results.csv")
    print(" ", out_dir / "property_failures.json")
    print(" ", out_dir / "property_summary.json")


def decision_to_public(d):
    return {
        "selected": d.selected,
        "score": d.score,
        "explanation": d.explanation,
        "top": [
            {
                "action": p.action,
                "score": p.score,
                "decision": p.decision,
                "denied_reasons": p.denied_reasons,
                "missing_evidence": p.missing_evidence,
            }
            for p in d.proofs[:8]
        ],
    }


if __name__ == "__main__":
    main()
