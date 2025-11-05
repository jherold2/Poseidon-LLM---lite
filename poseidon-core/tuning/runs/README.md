# Tuning Run Records

`run_recipe.py` and CI jobs should emit structured outputs under this directory.
Each evaluation run is stored in a timestamped folder containing the metrics
JSON and a copy of the eval spec used. When preparing a run card, copy the
metrics paths into the template under `templates/`.
