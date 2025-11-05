---
title: <dataset_name>
id: <dataset_version>
created: <YYYY-MM-DD>
owners:
  - <name or team>
source:
  warehouse: <warehouse/schema>
  extraction_query: <sql file or link>
  lineage:
    - <upstream dataset>
license: <license or usage agreement>
security:
  pii_reviewed: <yes/no>
  retention_policy: <description>
quality_checks:
  - check: schema_validation
    status: <pass/fail>
    notes: <context>
  - check: null_rate
    status: <pass/fail>
    notes: <context>
intended_use:
  model_tasks:
    - sft
    - dpo
    - regression_suite
  notes: |
    <Explain how the dataset should be used, sampling strategy, and caveats.>
supporting_artifacts:
  - name: profiling_report
    path: <path-to-report>
  - name: issue_tracker
    link: <url>
---

## Summary

Provide a short overview of what the dataset captures and why it exists.

## Data Preparation

Document extraction jobs, transformation scripts, and validation steps.

## Known Gaps

Highlight missing labels, sparse segments, or planned improvements.
