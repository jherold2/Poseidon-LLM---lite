# RLHF Pipeline

This directory collects artifacts for the RLHF stage, including preference pair
curation, reward model checkpoints, and orchestration scripts for DPO/PPO
training. The initial focus is on Direct Preference Optimisation (DPO) with a
lightweight reward model (RM v1) to rank candidate responses.

## Layout

```
/tuning/rlhf/
  bootstrap_dpo.py        # CLI to seed preference data and launch DPO jobs
  preference_pairs/
    initial_pairs.jsonl   # Seed preference set used for RM v1
  reward_models/
    rm_v1_config.yaml     # Hyperparameters + checkpoints for reward model
```

All training runs should be tracked in MLflow with the tag `stage=rlhf`. Reward
model checkpoints can be registered under the `poseidon-rm` registry namespace.
