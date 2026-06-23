#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from agent_relation_core_v1 import RelationCore, decision_to_dict
from relation_core_trace_scenarios import traces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./relation_core_trace_results")
    ap.add_argument("--show-all", action="store_true")
    ap.add_argument("--show-failures", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    core = RelationCore()
    rows = []
    details = []
    failures = []
    trace_summary = []

    for tr in traces():
        trace_ok = True
        trace_forbidden = False
        trace_rows = []
        for idx, s in enumerate(tr.steps, start=1):
            d = core.decide(s)
            selected = d.selected
            ok = selected in s.expected and selected not in s.forbidden
            forbidden = selected in s.forbidden
            top3 = [p.action for p in d.proofs[:3]]
            expected_top3 = bool(set(top3) & s.expected)
            p = d.proofs[0]
            row = {
                "trace": tr.trace_id,
                "step": idx,
                "scenario": s.scenario_id,
                "selected": selected,
                "expected": "|".join(sorted(s.expected)),
                "forbidden": "|".join(sorted(s.forbidden)),
                "ok": int(ok),
                "forbidden_hit": int(forbidden),
                "expected_in_top3": int(expected_top3),
                "score": round(d.score, 4),
                "support": round(p.support, 3),
                "contradiction": round(p.contradiction, 3),
                "evidence": round(p.evidence_sufficiency, 3),
                "risk": round(p.risk, 3),
                "uncertainty": round(p.uncertainty, 3),
                "top3": " > ".join(top3),
            }
            rows.append(row)
            trace_rows.append(row)
            detail = {
                "trace": tr.trace_id,
                "trace_summary": tr.summary,
                "step": idx,
                "scenario": s.scenario_id,
                "summary": s.summary,
                "tags": sorted(s.tags),
                "evidence": sorted(s.evidence),
                "constraints": sorted(s.constraints),
                "expected": sorted(s.expected),
                "forbidden": sorted(s.forbidden),
                "decision": decision_to_dict(d, top_k=8),
            }
            details.append(detail)
            if not ok:
                failures.append(detail)
                trace_ok = False
            if forbidden:
                trace_forbidden = True

        trace_summary.append({
            "trace": tr.trace_id,
            "steps": len(tr.steps),
            "ok": int(trace_ok),
            "forbidden_hit": int(trace_forbidden),
            "selected_chain": " -> ".join(r["selected"] for r in trace_rows),
        })

    summary = {
        "traces": len(trace_summary),
        "steps": len(rows),
        "trace_success_rate": sum(t["ok"] for t in trace_summary) / max(1, len(trace_summary)),
        "step_success_rate": sum(r["ok"] for r in rows) / max(1, len(rows)),
        "forbidden_hit_rate": sum(r["forbidden_hit"] for r in rows) / max(1, len(rows)),
        "expected_in_top3_rate": sum(r["expected_in_top3"] for r in rows) / max(1, len(rows)),
        "failures": len(failures),
    }

    with (out_dir / "trace_steps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with (out_dir / "trace_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(trace_summary[0].keys()))
        w.writeheader()
        w.writerows(trace_summary)

    (out_dir / "trace_details.json").write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "trace_failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "trace_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Relation Core v1 MULTI-STEP traces ===")
    print(f"traces={summary['traces']} steps={summary['steps']} trace_success={summary['trace_success_rate']:.3f} step_success={summary['step_success_rate']:.3f} forbidden_hit={summary['forbidden_hit_rate']:.3f} expected_top3={summary['expected_in_top3_rate']:.3f} failures={summary['failures']}")
    print()
    print(f"{'trace':42s} | ok | selected chain")
    print("-" * 130)
    for t in trace_summary:
        if args.show_all or not t["ok"]:
            print(f"{t['trace'][:42]:42s} | {t['ok']}  | {t['selected_chain']}")

    if failures and args.show_failures:
        print("\n=== Trace failures ===")
        for f in failures:
            print(f"\n[{f['trace']} step={f['step']} {f['scenario']}] selected={f['decision']['selected']} expected={f['expected']} forbidden={f['forbidden']}")
            print("summary:", f["summary"])
            print("tags:", f["tags"], "evidence:", f["evidence"], "constraints:", f["constraints"])
            for line in f["decision"]["explanation"]:
                print(" ", line)
            for p in f["decision"]["top"][:5]:
                print(f"  proof {p['action']}: score={p['score']:.3f} dec={p['decision']} support={p['support']:.2f} contr={p['contradiction']:.2f} evidence={p['evidence_sufficiency']:.2f} risk={p['risk']:.2f} uncertain={p['uncertainty']:.2f} denied={p['denied_reasons']} missing={p['missing_evidence']}")

    print("\nSaved:")
    print(" ", out_dir / "trace_steps.csv")
    print(" ", out_dir / "trace_summary.csv")
    print(" ", out_dir / "trace_failures.json")
    print(" ", out_dir / "trace_summary.json")


if __name__ == "__main__":
    main()
