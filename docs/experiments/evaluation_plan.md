# AI pipeline evaluation plan

This document defines the evaluation that should be run before reporting
portfolio-grade performance numbers.

## Dataset

Collect at least 30–50 smart-glass images across varied everyday scenes:

- desk / monitor setup
- backpack or pouch
- shelf / cabinet
- café table
- bedroom / living room
- partially occluded small objects
- multiple similar objects in the same image

For each image, manually label:

- visible target objects
- object aliases, if any
- surface or support object
- approximate position hint
- nearby objects useful for recall
- whether the object is portable / search-worthy

## VLM metrics

| Metric | Definition |
|---|---|
| Object recall | labeled target objects detected / labeled target objects |
| Object precision | valid detected objects / detected objects |
| Surface accuracy | objects with correct surface hint / matched objects |
| Nearby-object accuracy | correct nearby-object relations / predicted relations |
| JSON validity | parseable structured outputs / total runs |

## Ablation

Compare at least two modes:

1. single-pass VLM prompt
2. multi-pass VLM pipeline

Report object recall, duplicate rate, missing-object recovery, and latency for
both modes.

## Retrieval / LLM metrics

Create 2–3 natural-language questions per target item.

| Metric | Definition |
|---|---|
| Top-1 hit rate | correct memory appears at rank 1 |
| Top-3 hit rate | correct memory appears in top 3 |
| Grounded answer correctness | answer location matches labeled memory |
| Citation validity | cited memory ID corresponds to the correct image |
| End-to-end latency | query request to answer response |

## Reporting rule

Do not report headline percentages from unlabeled samples. Existing `ai_test2`
artifacts are useful for smoke checks only.
