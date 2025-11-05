---
run_id: <generated-by-mlflow-or-ci>
created: <YYYY-MM-DDTHH:MM:SSZ>
initiated_by: <owner>
recipe: <relative-path-to-recipe>
base_model: <model-name>
seed: <int>
mlflow_run: <link-or-id>
datasets:
  sft_train: <dataset-version>
  sft_validation: <dataset-version>
  dpo_preferences: <dataset-version>
artifacts:
  model_output: <path-or-registry-uri>
  eval_results:
    - spec: core_functional_v1
      path: <runs/.../metrics.json>
    - spec: safety_redteam_v1
      path: <runs/.../metrics.json>
 gate_verdict: <pass/fail>
 gate_spec: tuning/gates/standard_v1.yaml
notes: |
  <Key findings, regressions, or follow-up items.>
---

## Metrics Snapshot

| Metric | Value | Source |
| ------ | ----- | ------ |
| chain_accuracy | <value> | core_functional_v1 |
| preference_match_rate | <value> | safety_redteam_v1 |

## Changelog

- <Describe notable training or data changes>

## Follow Ups

- [ ] <Issue or action item>
