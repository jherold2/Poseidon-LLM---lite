# Tuning Data Assets

This directory hosts versioned datasets used during supervised fine-tuning (SFT),
preference tuning (DPO), and downstream regression suites. Datasets should be
tracked with DVC or LakeFS (optional), and accompanied by an updated dataset
card under `templates/` to preserve provenance and quality checks.

Recommended layout:

```
/tuning/data/
  sft/
    train.jsonl
    validation.jsonl
  dpo/
    preference_pairs.jsonl
  eval/
    core_functional_v1.jsonl
    safety_redteam_v1.jsonl
```

Maintain data version identifiers (e.g., git tags, MLflow dataset URIs, or DVC
hashes) so run cards can reference the exact snapshot used for each experiment.
