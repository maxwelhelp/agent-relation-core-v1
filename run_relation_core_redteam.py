#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict

from agent_relation_core_v1 import RelationCore, decision_to_dict
from relation_core_redteam_scenarios import cases


def group_of(name: str) -> str:
    return name.split("_", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./relation_core_redteam_results")
    ap.add_argument("--show-all", action="store_true")
    ap.add_argument("--show-failures", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    core = RelationCore()
    rows = []
    details = []
    failures = []
    by_group = defaultdict(lambda: {"n": 0, "ok": 0, "forbidden": 0, "top3": 0})

    for s in cases():
        d = core.decide(s)
        selected = d.selected
        ok = selected in s.expected and selected not in s.forbidden
        forbidden = selected in s.forbidden
        top3 = [p.action for p in d.proofs[:3]]
        expected_top3 = bool(set(top3) & s.expected)
        proof = d.proofs[0]
        row = {
            "scenario": s.scenario_id,
            "group": group_of(s.scenario_id),
            "selected": selected,
            "selected_class": d.selected_class,
            "expected": "|".join(sorted(s.expected)),
            "forbidden": "|".join(sorted(s.forbidden)),
            "ok": int(ok),
            "forbidden_hit": int(forbidden),
            "expected_in_top3": int(expected_top3),
            "score": round(d.score, 4),
            "support": round(proof.support, 3),
            "contradiction": round(proof.contradiction, 3),
            "evidence": round(proof.evidence_sufficiency, 3),
            "risk": round(proof.risk, 3),
            "uncertainty": round(proof.uncertainty, 3),
            "missing": ",".join(proof.missing_evidence),
            "denied": ",".join(proof.denied_reasons),
            "top3": " > ".join(top3),
        }
        rows.append(row)
        g = by_group[row["group"]]
        g["n"] += 1
        g["ok"] += int(ok)
        g["forbidden"] += int(forbidden)
        g["top3"] += int(expected_top3)

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
        "success_rate": sum(r["ok"] for r in rows) / len(rows),
        "forbidden_hit_rate": sum(r["forbidden_hit"] for r in rows) / len(rows),
        "expected_in_top3_rate": sum(r["expected_in_top3"] for r in rows) / len(rows),
        "failures": len(failures),
        "groups": {
            k: {
                "n": v["n"],
                "success_rate": v["ok"] / v["n"],
                "forbidden_hit_rate": v["forbidden"] / v["n"],
                "expected_in_top3_rate": v["top3"] / v["n"],
            }
            for k, v in sorted(by_group.items())
        },
    }

    with (out_dir / "redteam_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (out_dir / "redteam_results.json").write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "redteam_failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "redteam_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== Relation Core v1 RED-TEAM field scenarios ===")
    print(f"scenarios={summary['n']} success={summary['success_rate']:.3f} forbidden_hit={summary['forbidden_hit_rate']:.3f} expected_in_top3={summary['expected_in_top3_rate']:.3f} failures={summary['failures']}")
    print("\nGroups:")
    for k, v in summary["groups"].items():
        print(f"  {k}: n={v['n']:2d} success={v['success_rate']:.3f} forbidden={v['forbidden_hit_rate']:.3f} top3={v['expected_in_top3_rate']:.3f}")

    print()
    print(f"{'scenario':46s} | {'selected':22s} | {'expected':35s} | ok | top3")
    print("-" * 150)
    for r in rows:
        if args.show_all or not r["ok"]:
            print(f"{r['scenario'][:46]:46s} | {r['selected'][:22]:22s} | {r['expected'][:35]:35s} | {r['ok']}  | {r['top3']}")

    if args.show_failures and failures:
        print("\n=== Failures ===")
        for f in failures:
            print(f"\n[{f['scenario']}] selected={f['decision']['selected']} expected={f['expected']} forbidden={f['forbidden']}")
            print("summary:", f["summary"])
            print("tags:", f["tags"], "evidence:", f["evidence"], "constraints:", f["constraints"])
            for line in f["decision"]["explanation"]:
                print(" ", line)
            for p in f["decision"]["top"][:5]:
                print(f"  proof {p['action']}: score={p['score']:.3f} dec={p['decision']} support={p['support']:.2f} contr={p['contradiction']:.2f} evidence={p['evidence_sufficiency']:.2f} risk={p['risk']:.2f} uncertain={p['uncertainty']:.2f} denied={p['denied_reasons']} missing={p['missing_evidence']}")

    print("\nSaved:")
    print(" ", out_dir / "redteam_results.csv")
    print(" ", out_dir / "redteam_failures.json")
    print(" ", out_dir / "redteam_summary.json")


if __name__ == "__main__":
    main()
