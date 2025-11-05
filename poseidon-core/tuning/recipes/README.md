# Training Recipes

Recipes capture the hyperparameters, dataset versions, and logging defaults for
SFT and RLHF runs. Use `run_recipe.py` to launch experiments so configuration is
tracked alongside MLflow runs.

```
/tuning/recipes/
  run_recipe.py
  sft/
    standard_sft_v1.yaml
  dpo/
    standard_dpo_v1.yaml
```
