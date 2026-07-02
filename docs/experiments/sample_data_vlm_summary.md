# Sample-data VLM evaluation

This benchmark uses filename-derived weak labels from existing repository images.
It is more meaningful than a two-sample smoke check, but still weaker than a
manually labeled dataset.

## Dataset

| Metric | Value |
|---|---:|
| Total samples | 10 |
| Successful VLM outputs | 10 |
| Errors | 0 |

## Overall

| Metric | Value |
|---|---:|
| Weak-label matches | 5 |
| Weak-label recall | 50.0% |
| Average latency | 27.216 sec |

## By label

| Label | Samples | Matched | Weak-label recall |
|---|---:|---:|---:|
| key | 5 | 1 | 20.0% |
| wallet | 5 | 4 | 80.0% |

## Caveat

The labels are inferred from filenames such as `wallet_*.jpg` and `key_*.jpg`.
Use this as a first-pass benchmark only. A final portfolio result should use
manual object and spatial-relation labels.
