# Agent Relation Core v1

Это не rerank benchmark и не random simulation.

Это проверка ядра:

```text
candidate action
→ motif proof
→ hard blockers / constraints
→ evidence obligations
→ allow/deny/inspect/ask/wait/rollback
```

## Файлы

- `agent_relation_core_v1.py` — ядро proof engine.
- `relation_core_scenarios.py` — ручные field-like сценарии.
- `relation_core_redteam_scenarios.py` — red-team сценарии.
- `run_relation_core_eval.py` — прогон базовых сценариев.
- `run_relation_core_redteam.py` — прогон red-team.

## Запуск

```bash
python run_relation_core_eval.py --show-failures --show-all
python run_relation_core_redteam.py --show-failures --show-all
```

## Что проверяется

- `triangle`: task/evidence/action, memory/outcome/action.
- `star`: constraint вокруг action.
- `chain`: порядок evidence → localize → patch → verify.
- `diamond`: независимое подтверждение, например final_report + metrics.csv.
- `cycle`: action → expected result → goal.
- `cut/blocker`: dirty_guard/protected/ambiguous/job_running отрезают patch.

## Главный принцип

Memory не управляет агентом. Memory — только evidence.

Действие разрешается не потому, что оно похоже на прошлое, а потому что его relation-proof замкнулся и нет hard blocker.

## v1.1 change

После первого прогона ядро слишком часто выбирало `read/deep_compare/smart_context`, даже когда evidence уже достаточно для commit.
Добавлены:

- `commit_readiness_bonus`;
- `redundant_evidence_penalty`;
- verify-after-patch priority;
- stronger full-rerun only when wide/full validation is justified.

## v1.2 change

Исправлено разделение `reindex_context` vs `patch_context_pack`:

- `reindex_context` — когда context/index stale/corrupt и источник не локализован;
- `patch_context_pack` — когда баг генератора context pack уже локализован.

## v1.3 change — universal dominance/cut/proof layers

Добавлены не частные if-подгонки, а общие слои:

1. `effective_tags()` / current-state dominance:
   - current evidence can suppress stale task text;
   - `already_fixed/no_op/metrics_csv_has_diagnostics` suppress old diagnostic-missing support.

2. `constraint_cut()`:
   - constraints cut incompatible actions before scoring;
   - `user_no_changes`, `already_fixed`, `job_running`, `dirty_guard`, `permission_needed`, `ambiguous_requirement`.

3. `proof_obligation_cuts()`:
   - high-blast actions need stronger proof;
   - `patch_core_logic` requires `deep_compare_done`, error evidence, and localization.

## v1.4 change — high-blast core causal check

When `core_logic_error + localized_core` is present but `deep_compare_done` is missing:

- `patch_core_logic` is cut by proof obligations;
- `deep_compare` / `read_symbol` are preferred over generic `smart_context`;
- generic context gets a redundancy penalty after localization.

## Current result

Base scenarios:

```text
scenarios=27
success=1.000
forbidden_hit=0.000
expected_in_top3=1.000
```

Red-team scenarios:

```text
scenarios=40
success=1.000
forbidden_hit=0.000
expected_in_top3=1.000
```