# MCP Integration Plan

## Goal

Use Agent Relation Core as a proof-check layer for MCP Local Operator.

Flow:

```text
MCP events -> Scenario -> RelationCore -> selected_action + proof
```

The core is not a full router. It checks whether a proposed next action is consistent with current state, evidence, constraints, and memory.

## Current checks

```text
base scenarios: 27/27
red-team scenarios: 40/40
multi-step traces: 10 traces / 28 steps
property tests: 280/280
mock MCP adapter: 8/8
```

## Files

```text
agent_relation_core_v1.py
mcp_adapter_mock.py
relation_plan_check_api.py
run_all_checks.py
```

## API

MCP should call:

```python
from relation_plan_check_api import relation_plan_check

result = relation_plan_check(
    task_id="task_123",
    events=[
        {"kind": "task_start", "data": {"summary": "diagnostics missing"}},
        {"kind": "job_result", "data": {"status": "failed"}},
        {"kind": "artifact_compare", "data": {
            "final_report_has_diagnostics": True,
            "metrics_csv_missing_diagnostics": True,
        }},
        {"kind": "read_symbol", "data": {"target": "reporting"}},
    ],
    candidate_actions=[
        "patch_reporting",
        "patch_core_logic",
        "deep_compare",
        "ask_user",
    ],
)
```

Return fields:

```text
selected_action
selected_class
selected_decision
score
allowed_top_actions
denied_top_actions
scenario
proof
```

## Event mapping

Supported event kinds:

```text
task_start
job_result
artifact_compare
smart_context
read_symbol
deep_compare
patch_apply
dirty_guard
protected_files
user_scope
```

Important mappings:

```text
job_result status=running -> job_running
artifact_compare metrics missing + final report has key -> reporting mismatch evidence
read_symbol target=reporting -> localized_reporting
read_symbol target=core -> localized_core
deep_compare after localized_core -> core causal evidence
user_scope no_changes -> user_no_changes
```

## First MCP usage

Start in shadow mode:

```text
1. Collect MCP events.
2. Call relation_plan_check.
3. Log selected_action and proof.
4. Compare with the action MCP was about to take.
5. Do not change behavior yet.
```

Then warning mode:

```text
If MCP intended action differs from selected_action, show proof summary.
```

Then enforcement mode for selected call sites:

```text
Use result.selected_action and result.proof before patch, rerun, rollback, or replay.
```

## First integration points

```text
before patch_apply
before full rerun
before recovery replay
before final suggest_next
```

## Acceptance cases

```text
diagnostics mismatch -> read_metrics_aggregation -> patch_reporting -> short_rerun
same diagnostics with dirty state -> rollback/inspect, not patch
core localized without deep_compare -> deep_compare/read_symbol
core localized with deep_compare -> patch_core_logic
job running -> wait_job
already fixed -> stop_noop
user no changes -> inspect/stop
protected scope -> ask_user
```

## Next task

Implement a small MCP-side wrapper:

```python
def relation_plan_check_action(task_id, recent_events, candidate_actions=None):
    return relation_plan_check(task_id, recent_events, candidate_actions)
```
