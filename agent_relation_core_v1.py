#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class MemoryCase:
    case_id: str
    summary: str
    action: str
    tags: Set[str] = field(default_factory=set)
    constraints: Set[str] = field(default_factory=set)
    observed_outcome: str = "unknown"
    verified: bool = False
    same_constraints: bool = False
    stale: bool = False
    poisoned: bool = False
    patch_target: Optional[str] = None

    def visible_quality(self) -> float:
        q = 0.0
        if self.observed_outcome == "success":
            q += 0.35
        elif self.observed_outcome == "partial":
            q += 0.10
        elif self.observed_outcome == "fail":
            q -= 0.35
        if self.verified:
            q += 0.35
        if self.same_constraints:
            q += 0.20
        if self.stale:
            q -= 0.30
        return max(-1.0, min(1.0, q))


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    summary: str
    tags: Set[str]
    evidence: Set[str]
    constraints: Set[str]
    memories: List[MemoryCase]
    expected: Set[str]
    forbidden: Set[str] = field(default_factory=set)
    notes: str = ""


@dataclass(frozen=True)
class ActionSpec:
    name: str
    action_class: str
    intent_tags: Set[str]
    required_evidence: Set[str] = field(default_factory=set)
    soft_evidence: Set[str] = field(default_factory=set)
    cost: float = 0.2
    blast_radius: float = 0.1
    reversible: float = 0.8
    phase: str = "evidence"
    patch_target: Optional[str] = None


@dataclass
class Proof:
    action: str
    action_class: str
    score: float
    decision: str
    support: float
    contradiction: float
    evidence_sufficiency: float
    constraint_compatibility: float
    uncertainty: float
    risk: float
    expected_progress: float
    reversibility: float
    memory_support: float
    poison_suspicion: float
    blocker_paths: List[List[str]]
    support_paths: List[List[str]]
    missing_evidence: List[str]
    denied_reasons: List[str]
    motifs: Dict[str, List[List[str]]]


@dataclass
class Decision:
    selected: str
    selected_class: str
    decision: str
    score: float
    proofs: List[Proof]
    explanation: List[str]


def default_actions() -> Dict[str, ActionSpec]:
    specs = [
        ActionSpec("inspect_constraints", "INSPECT", {"dirty_guard", "protected_file", "ambiguous_requirement", "permission_needed", "user_no_changes"}, cost=0.12, blast_radius=0.0, reversible=1.0, phase="constraints"),
        ActionSpec("job_result", "EVIDENCE", {"need_logs", "job_failed", "diagnostics_missing", "unknown_failure", "flaky_timeout"}, cost=0.18, blast_radius=0.0, reversible=1.0),
        ActionSpec("smart_context", "EVIDENCE", {"need_context", "unknown_failure", "diagnostics_missing", "import_error", "secret_leak", "core_logic_error"}, cost=0.22, blast_radius=0.0, reversible=1.0),
        ActionSpec("read_metrics_aggregation", "LOCALIZE", {"diagnostics_missing", "metrics_csv_missing_diagnostics", "artifact_mismatch"}, required_evidence={"job_result_available"}, soft_evidence={"final_report_has_diagnostics", "metrics_csv_missing_diagnostics"}, cost=0.22, blast_radius=0.0, reversible=1.0, phase="localize"),
        ActionSpec("read_symbol", "LOCALIZE", {"import_error", "core_logic_error", "unknown_failure", "symbol_missing"}, required_evidence={"job_result_available"}, cost=0.24, blast_radius=0.0, reversible=1.0, phase="localize"),
        ActionSpec("deep_compare", "LOCALIZE", {"artifact_mismatch", "regression_after_patch", "diagnostics_missing", "unknown_failure", "core_logic_error"}, required_evidence={"job_result_available"}, cost=0.30, blast_radius=0.0, reversible=1.0, phase="localize"),
        ActionSpec("patch_reporting", "PATCH", {"diagnostics_missing", "artifact_mismatch", "metrics_csv_missing_diagnostics"}, required_evidence={"job_result_available", "final_report_has_diagnostics", "metrics_csv_missing_diagnostics", "localized_reporting"}, soft_evidence={"deep_compare_done"}, cost=0.50, blast_radius=0.25, reversible=0.65, phase="patch", patch_target="reporting"),
        ActionSpec("patch_import_wiring", "PATCH", {"import_error", "module_move", "path_wiring"}, required_evidence={"job_result_available", "import_error", "localized_import"}, soft_evidence={"read_symbol_done"}, cost=0.48, blast_radius=0.28, reversible=0.65, phase="patch", patch_target="import"),
        ActionSpec("patch_secret_filter", "PATCH", {"secret_leak", "filter_leak", "redaction_missing"}, required_evidence={"job_result_available", "secret_leak", "localized_secret_filter"}, cost=0.52, blast_radius=0.22, reversible=0.70, phase="patch", patch_target="secret_filter"),
        ActionSpec("patch_context_pack", "PATCH", {"context_pack_stale", "index_bug"}, required_evidence={"context_pack_stale", "localized_context_pack"}, cost=0.45, blast_radius=0.30, reversible=0.60, phase="patch", patch_target="context_pack"),
        ActionSpec("patch_core_logic", "PATCH", {"core_logic_error", "algorithm_bug", "unit_test_failure"}, required_evidence={"job_result_available", "core_logic_error", "localized_core", "deep_compare_done"}, soft_evidence={"deep_compare_done"}, cost=0.80, blast_radius=0.80, reversible=0.35, phase="patch", patch_target="core"),
        ActionSpec("patch_config", "PATCH", {"config_error", "env_mismatch"}, required_evidence={"job_result_available", "config_error", "localized_config"}, cost=0.45, blast_radius=0.50, reversible=0.45, phase="patch", patch_target="config"),
        ActionSpec("short_rerun", "VERIFY", {"patch_applied", "flaky_timeout", "verify_needed"}, required_evidence={"patch_applied"}, cost=0.35, blast_radius=0.0, reversible=1.0, phase="verify"),
        ActionSpec("full_rerun", "VERIFY", {"full_validation_needed", "wide_change"}, required_evidence={"patch_applied"}, cost=0.95, blast_radius=0.0, reversible=1.0, phase="verify"),
        ActionSpec("rollback", "NO_PATCH", {"dirty_guard", "regression_after_patch", "user_changes_conflict"}, cost=0.35, blast_radius=0.05, reversible=0.85, phase="no_patch"),
        ActionSpec("ask_user", "NO_PATCH", {"ambiguous_requirement", "permission_needed", "user_confirmation_needed", "protected_file"}, cost=0.20, blast_radius=0.0, reversible=1.0, phase="no_patch"),
        ActionSpec("wait_job", "NO_PATCH", {"job_running", "flaky_timeout", "rate_limit"}, cost=0.12, blast_radius=0.0, reversible=1.0, phase="no_patch"),
        ActionSpec("reindex_context", "NO_PATCH", {"stale_context", "context_pack_stale", "index_corrupt", "symbol_missing"}, cost=0.28, blast_radius=0.05, reversible=0.9, phase="no_patch"),
        ActionSpec("stop_noop", "NO_PATCH", {"already_fixed", "user_no_changes", "no_op"}, cost=0.05, blast_radius=0.0, reversible=1.0, phase="no_patch"),
    ]
    return {s.name: s for s in specs}


class RelationCore:
    def __init__(self, actions: Optional[Dict[str, ActionSpec]] = None):
        self.actions = actions or default_actions()

    def decide(self, scenario: Scenario, candidates: Optional[List[str]] = None) -> Decision:
        names = candidates or list(self.actions.keys())
        proofs = [self.evaluate_action(scenario, self.actions[n]) for n in names if n in self.actions]
        proofs.sort(key=lambda p: p.score, reverse=True)
        selected = proofs[0]
        return Decision(selected.action, selected.action_class, selected.decision, selected.score, proofs, self._explain(selected, proofs[:5]))

    def _effective_tags(self, s: Scenario) -> Set[str]:
        tags = set(s.tags) | set(s.evidence) | set(s.constraints)
        if "already_fixed" in tags or "no_op" in tags or "metrics_csv_has_diagnostics" in tags:
            tags.discard("diagnostics_missing")
            tags.discard("metrics_csv_missing_diagnostics")
            tags.discard("artifact_mismatch")
            tags.discard("secret_leak")
        if "user_no_changes" in tags:
            for x in ["diagnostics_missing", "artifact_mismatch", "core_logic_error", "config_error", "secret_leak"]:
                tags.discard(x)
        return tags

    def _constraint_cut(self, s: Scenario, a: ActionSpec) -> List[str]:
        tags = self._effective_tags(s)
        cuts: List[str] = []
        if "user_no_changes" in tags and a.name not in {"stop_noop", "inspect_constraints", "ask_user"}:
            cuts.append("user_no_changes")
        if ("already_fixed" in tags or "no_op" in tags) and a.name not in {"stop_noop", "inspect_constraints", "ask_user"}:
            cuts.append("already_fixed")
        if "job_running" in tags and a.name not in {"wait_job", "inspect_constraints", "ask_user", "job_result"}:
            cuts.append("job_running")
        if ("dirty_guard" in tags or "user_changes_conflict" in tags) and (a.action_class == "PATCH" or a.name in {"short_rerun", "full_rerun"}):
            cuts.append("dirty_guard")
        if "ambiguous_requirement" in tags and a.action_class == "PATCH":
            cuts.append("ambiguous_requirement")
        if "permission_needed" in tags and a.action_class == "PATCH":
            cuts.append("permission_needed")
        if "protected_file" in tags and "permission_needed" in tags and a.action_class == "PATCH":
            cuts.append("protected_file")
        return cuts

    def _proof_obligation_cuts(self, s: Scenario, a: ActionSpec) -> List[str]:
        e = set(s.evidence)
        cuts: List[str] = []
        if a.name == "patch_core_logic":
            for req in ["job_result_available", "core_logic_error", "localized_core", "deep_compare_done"]:
                if req not in e:
                    cuts.append(f"core_patch_requires_{req}")
        return cuts

    def evaluate_action(self, s: Scenario, a: ActionSpec) -> Proof:
        tags = self._effective_tags(s)
        motifs = {k: [] for k in ["triangle", "star", "chain", "diamond", "cycle", "cut"]}
        support_paths: List[List[str]] = []
        blockers = sorted(set(self._constraint_cut(s, a) + self._proof_obligation_cuts(s, a)))
        for b in blockers:
            motifs["cut"].append([b, "BLOCKS", a.name])
        required = set(a.required_evidence)
        have = required & set(s.evidence)
        missing = sorted(required - set(s.evidence))
        evidence_suff = len(have) / max(1, len(required)) if required else 1.0
        denied_reasons: List[str] = []
        if blockers:
            denied_reasons.append("hard_blocker")
        if a.action_class == "PATCH" and missing:
            denied_reasons.append("patch_requires_more_evidence")
            motifs["chain"].append(["task", "missing_evidence", a.name])

        support = 0.30 * evidence_suff
        direct = set(a.intent_tags) & tags
        if direct:
            support += min(0.45, 0.10 * len(direct) + 0.18)
            for h in sorted(direct)[:4]:
                p = ["task", h, a.name]
                support_paths.append(p)
                motifs["triangle"].append(p)
        soft = set(a.soft_evidence) & set(s.evidence)
        if soft:
            support += min(0.15, 0.05 * len(soft))
        mem_support, poison_suspicion, mem_paths, mem_contra = self._memory_signal(s, a)
        support += 0.22 * mem_support
        support_paths.extend(mem_paths[:3])
        contradiction = 1.0 if blockers else mem_contra
        risk = min(1.0, a.blast_radius + (0.35 if a.action_class == "PATCH" and evidence_suff < 1.0 else 0.0) + (0.20 if poison_suspicion > 0.55 and a.action_class == "PATCH" else 0.0))
        uncertainty = self._uncertainty(s, a, evidence_suff, poison_suspicion)
        progress = self._expected_progress(s, a)
        if progress > 0.45:
            motifs["cycle"].append([a.name, "expected_result", "goal_state"])
        if a.action_class == "PATCH" and risk > 0.80:
            denied_reasons.append("patch_risk_too_high")
        if a.name == "full_rerun" and "wide_change" not in tags and "full_validation_needed" not in tags:
            denied_reasons.append("full_rerun_not_justified")

        score = 1.10 * support + 0.75 * progress + 0.55 * (0.0 if blockers else 1.0) + 0.25 * a.reversible - 1.50 * contradiction - 0.85 * risk - 0.55 * uncertainty - 0.25 * a.cost
        score += self._commit_readiness_bonus(s, a, evidence_suff)
        score -= self._redundant_evidence_penalty(s, a)
        if denied_reasons:
            score -= 2.5
        if a.action_class in {"EVIDENCE", "LOCALIZE", "NO_PATCH", "INSPECT"}:
            score += self._information_value_bonus(s, a)
        if a.name == "stop_noop" and not ({"already_fixed", "user_no_changes", "no_op"} & tags):
            score -= 0.8
        return Proof(a.name, a.action_class, score, "deny" if denied_reasons else "allow", max(0.0, min(1.0, support)), max(0.0, min(1.0, contradiction)), evidence_suff, 0.0 if blockers else 1.0, max(0.0, min(1.0, uncertainty)), max(0.0, min(1.0, risk)), max(0.0, min(1.0, progress)), a.reversible, max(0.0, min(1.0, mem_support)), max(0.0, min(1.0, poison_suspicion)), motifs["cut"], support_paths, missing, denied_reasons, motifs)

    def _memory_signal(self, s: Scenario, a: ActionSpec):
        tags = self._effective_tags(s)
        support = 0.0; poison = 0.0; contra = 0.0; paths: List[List[str]] = []
        for m in s.memories:
            overlap = len(tags & set(m.tags)) / max(1, len(tags | set(m.tags)))
            same = m.action == a.name
            q = m.visible_quality()
            if same and q > 0 and overlap > 0.08:
                inc = overlap * (0.35 + 0.45 * q) + (0.10 if m.same_constraints else 0.0)
                support += inc
                if inc > 0.10:
                    paths.append([m.case_id, "verified_trace" if m.verified else "observed_trace", a.name])
            if same and m.observed_outcome == "fail" and overlap > 0.25:
                contra = max(contra, 0.55 + 0.25 * overlap)
            if same and (m.observed_outcome == "success"):
                if not m.verified: poison += 0.20 * max(0.2, overlap)
                if m.stale: poison += 0.25 * max(0.2, overlap)
                if m.constraints and not m.same_constraints: poison += 0.20 * max(0.2, overlap)
        return min(1.0, support), min(1.0, poison), paths, min(1.0, contra)

    def _expected_progress(self, s: Scenario, a: ActionSpec) -> float:
        tags = self._effective_tags(s)
        e = set(s.evidence)
        if a.name == "rollback" and {"dirty_guard", "regression_after_patch", "user_changes_conflict"} & tags: return 0.95
        if a.name == "ask_user" and {"ambiguous_requirement", "permission_needed", "protected_file"} & tags: return 0.90
        if a.name == "wait_job" and {"job_running", "flaky_timeout", "rate_limit"} & tags: return 0.85
        if a.name == "reindex_context" and {"stale_context", "context_pack_stale", "index_corrupt", "symbol_missing"} & tags: return 0.85
        if a.name == "stop_noop" and {"already_fixed", "user_no_changes", "no_op"} & tags: return 1.00
        if a.name == "read_metrics_aggregation" and "diagnostics_missing" in tags and "localized_reporting" not in e: return 0.78
        if a.name == "read_symbol" and {"import_error", "core_logic_error", "unknown_failure"} & tags: return 0.72
        if a.name == "deep_compare" and {"artifact_mismatch", "regression_after_patch", "unknown_failure", "core_logic_error"} & tags: return 0.74
        if a.name.startswith("patch_") and not self._constraint_cut(s, a) and not self._proof_obligation_cuts(s, a): return 0.70 * (len(a.required_evidence & e) / max(1, len(a.required_evidence)))
        if a.name == "short_rerun" and "patch_applied" in e: return 0.78
        if a.name == "full_rerun" and "patch_applied" in e and {"wide_change", "full_validation_needed"} & tags: return 0.90
        if a.name == "job_result" and "job_result_available" not in e: return 0.70
        if a.name == "smart_context" and "context_available" not in e: return 0.55
        return 0.20

    def _uncertainty(self, s: Scenario, a: ActionSpec, evidence_suff: float, poison: float) -> float:
        u = 0.15
        if a.action_class == "PATCH": u += 0.60 * (1.0 - evidence_suff)
        if "ambiguous_requirement" in s.constraints: u += 0.35
        u += 0.30 * poison
        return min(1.0, u)

    def _ready_patch_exists(self, s: Scenario) -> bool:
        for a in self.actions.values():
            if a.action_class == "PATCH" and not self._constraint_cut(s, a) and not self._proof_obligation_cuts(s, a) and a.required_evidence <= set(s.evidence):
                return True
        return False

    def _redundant_evidence_penalty(self, s: Scenario, a: ActionSpec) -> float:
        e = set(s.evidence); tags = self._effective_tags(s); p = 0.0
        if a.name == "job_result" and "job_result_available" in e: p += 0.95
        if a.name == "read_metrics_aggregation" and "localized_reporting" in e: p += 0.95
        if a.name == "deep_compare" and "deep_compare_done" in e: p += 0.95
        if a.name == "read_symbol" and ({"localized_import", "localized_core", "localized_symbol"} & e): p += 0.95
        if a.name == "smart_context" and self._ready_patch_exists(s): p += 0.55
        if a.name == "smart_context" and "localized_core" in e and "core_logic_error" in e and "deep_compare_done" not in e: p += 0.75
        if a.name == "reindex_context" and "localized_context_pack" in e and "index_corrupt" not in tags: p += 0.75
        if ({"already_fixed", "no_op", "user_no_changes"} & tags) and a.action_class in {"EVIDENCE", "LOCALIZE", "VERIFY"}: p += 1.25
        if a.action_class in {"EVIDENCE", "LOCALIZE"} and self._ready_patch_exists(s): p += 0.45
        if "patch_applied" in e and a.action_class in {"EVIDENCE", "LOCALIZE"} and "regression_after_patch" not in e: p += 0.65
        return p

    def _commit_readiness_bonus(self, s: Scenario, a: ActionSpec, evidence_suff: float) -> float:
        tags = self._effective_tags(s)
        if a.action_class == "PATCH" and evidence_suff >= 1.0 and not self._constraint_cut(s, a) and not self._proof_obligation_cuts(s, a):
            if a.patch_target in {"reporting", "import", "secret_filter", "context_pack", "config"}: return 0.75
            if a.patch_target == "core": return 0.45
        if a.name == "short_rerun" and "patch_applied" in s.evidence and not ({"full_validation_needed", "wide_change"} & tags): return 0.80
        if a.name == "full_rerun" and "patch_applied" in s.evidence and ({"wide_change", "full_validation_needed"} & tags): return 1.35
        return 0.0

    def _information_value_bonus(self, s: Scenario, a: ActionSpec) -> float:
        tags = self._effective_tags(s); e = set(s.evidence)
        if a.name == "inspect_constraints" and ({"dirty_guard", "protected_file", "ambiguous_requirement", "permission_needed", "user_no_changes", "already_fixed"} & tags): return 0.85
        if a.name == "rollback" and ({"dirty_guard", "user_changes_conflict", "regression_after_patch"} & tags): return 0.90
        if a.name == "ask_user" and ({"ambiguous_requirement", "permission_needed", "protected_file"} & tags): return 0.85
        if a.name == "wait_job" and "job_running" in tags: return 0.85
        if a.name == "reindex_context" and ({"stale_context", "index_corrupt", "context_pack_stale"} & tags): return 0.75
        if a.name == "read_metrics_aggregation" and "diagnostics_missing" in tags and "localized_reporting" not in e: return 0.60
        if a.name == "read_symbol" and ({"import_error", "core_logic_error", "unknown_failure"} & tags):
            if "core_logic_error" in tags and "localized_core" in e and "deep_compare_done" not in e: return 0.80
            return 0.55
        if a.name == "deep_compare" and ({"artifact_mismatch", "regression_after_patch"} & tags): return 0.50
        if a.name == "deep_compare" and "core_logic_error" in tags and "localized_core" in e and "deep_compare_done" not in e: return 0.95
        if a.name == "job_result" and "job_result_available" not in e: return 0.45
        if a.name == "smart_context" and "context_available" not in e: return 0.35
        return 0.0

    def _explain(self, selected: Proof, top: List[Proof]) -> List[str]:
        out = [f"selected={selected.action} class={selected.action_class} decision={selected.decision} score={selected.score:.3f}", f"support={selected.support:.2f} contradiction={selected.contradiction:.2f} evidence={selected.evidence_sufficiency:.2f} risk={selected.risk:.2f} uncertainty={selected.uncertainty:.2f}"]
        if selected.blocker_paths: out.append("blockers=" + "; ".join("->".join(p) for p in selected.blocker_paths))
        if selected.missing_evidence: out.append("missing_evidence=" + ",".join(selected.missing_evidence))
        if selected.support_paths: out.append("support_paths=" + "; ".join("->".join(p) for p in selected.support_paths[:3]))
        out.append("top=" + ", ".join(f"{p.action}:{p.score:.2f}" for p in top))
        return out


def proof_to_dict(p: Proof) -> Dict[str, Any]:
    return asdict(p)


def decision_to_dict(d: Decision, top_k: int = 5) -> Dict[str, Any]:
    return {"selected": d.selected, "selected_class": d.selected_class, "decision": d.decision, "score": d.score, "explanation": d.explanation, "top": [proof_to_dict(p) for p in d.proofs[:top_k]]}
