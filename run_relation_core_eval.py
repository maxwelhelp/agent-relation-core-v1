#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from agent_relation_core_v1 import RelationCore, decision_to_dict
from relation_core_scenarios import scenarios


def run(out_dir: Path, show_failures: bool, show_all: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    core = RelationCore()
    rows = []
    details = []
    failures = []

    for s in scenarios():
        d = core.decide(s)
        selected = d.selected
        ok = selected in s.expected and selected not in s.forbidden
        forbidden = selected in s.forbidden
        top3 = [p.action for p in d.proofs[:3]]
        expected_top3 = bool(set(top3) & s.expected)
        p = d.proofs[0]
        row = {
            "scenario": s.scenario_id,
            "selected": selected,
            "class": d.selected_class,
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
        detail = {
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

    summary = {
        "n": len(rows),
        "success_rate": sum(r["ok"] for r in rows) / max(1, len(rows)),
        "forbidden_hit_rate": sum(r["forbidden_hit"] for r in rows) / max(1, len(rows)),
        "expected_in_top3_rate": sum(r["expected_in_top3"] for r in rows) / max(1, len(rows)),
        "failures": len(failures),
    }

    with (out_dir / "scenario_results.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (out_dir / "scenario_results.json").write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Agent Relation Core v1 scenario evaluation ===")
    print(f"scenarios={summary['n']} success={summary['success_rate']:.3f} forbidden_hit={summary['forbidden_hit_rate']:.3f} expected_in_top3={summary['expected_in_top3_rate']:.3f}")
    print()
    print(f"{'scenario':42s} | {'selected':24s} | {'expected':34s} | ok | top3")
    print("-" * 140)
    for r in rows:
        if show_all or not r["ok"]:
            print(f"{r['scenario'][:42]:42s} | {r['selected'][:24]:24s} | {r['expected'][:34]:34s} | {r['ok']}  | {r['top3']}")

    if failures and show_failures:
        print("\n=== Failure explanations ===")
        for f in failures:
            print(f"\n[{f['scenario']}] expected={f['expected']} selected={f['decision']['selected']}")
            for line in f["decision"]["explanation"]:
                print("  " + line)
            for p in f["decision"]["top"][:5]:
                print(f"  proof {p['action']}: score={p['score']:.3f} decision={p['decision']} support={p['support']:.2f} contr={p['contradiction']:.2f} evidence={p['evidence_sufficiency']:.2f} risk={p['risk']:.2f} uncertainty={p['uncertainty']:.2f} denied={p['denied_reasons']}")

    print("\nSaved:")
    print(f"  {out_dir / 'scenario_results.csv'}")
    print(f"  {out_dir / 'scenario_results.json'}")
    print(f"  {out_dir / 'failures.json'}")
    print(f"  {out_dir / 'summary.json'}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./relation_core_v1_results")
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--show-all", action="store_true")
    args = ap.parse_args()
    run(Path(args.out_dir), show_failures=args.show_failures, show_all=args.show_all)


if __name__ == "__main__":
    main()
