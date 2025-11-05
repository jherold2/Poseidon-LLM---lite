# Poseidon Tuning Pipeline

This folder defines the end-to-end tuning workflow: dataset prep, supervised
fine-tuning, RLHF, evaluation harnesses, and CI guardrails. All tooling is wired
for MLflow logging so experiments, eval results, and gate verdicts remain
traceable.

## Quick Start Checklist (copy/paste to issue)

- [ ] Confirm dataset cards updated for SFT + DPO sources under `tuning/data/templates/`.
- [ ] Run `python tuning/recipes/run_recipe.py tuning/recipes/sft/standard_sft_v1.yaml` and log the MLflow run ID.
- [ ] Execute DPO bootstrap: `python tuning/rlhf/bootstrap_dpo.py tuning/recipes/dpo/standard_dpo_v1.yaml`.
- [ ] Generate model predictions for `core_functional_v1` + `safety_redteam_v1` suites.
- [ ] Run harness: `python -m tuning.eval.runner tuning/eval/specs/core_functional_v1.yaml <predictions.jsonl>`.
- [ ] Update run card in `tuning/runs/templates/` with datasets, metrics, and gate verdict.
- [ ] Enforce gates via `python tuning/ops/ci/check_gates.py --gate tuning/gates/standard_v1.yaml`.
- [ ] File follow-up issues for suite gaps or failed thresholds.

Refer to the subdirectory READMEs for details on data governance, recipe
configuration, evaluation specs, and RLHF orchestration.
