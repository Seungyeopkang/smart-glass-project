# Smart-glass AI pipeline experiments

This folder contains experiment utilities for the smart-glass AI pipeline.

The current script is intentionally lightweight: it checks existing sample
outputs under `ai_test2/` instead of re-running heavy VLM inference. Treat it as
an artifact smoke check, not as a formal benchmark or portfolio-grade
performance result.

For a dataset-backed first pass, use:

```bash
python docs/experiments/evaluate_sample_data_vlm.py --max-per-class 5
```

The current 10-image weak-label run produced:

- successful VLM outputs: 10 / 10
- overall weak-label recall: 50.0%
- wallet weak-label recall: 80.0%
- key weak-label recall: 20.0%
- average VLM latency: 27.216 sec

Note: the current VLM sample artifacts were generated through the Ollama/Gemma
path (`gemma4:31b-cloud`). The repository also includes a separate Qwen2.5-VL
multi-stage inference path under `apps/inference-server/src/models/qwen_vlm.py`.

For a proper evaluation, collect a labeled dataset first:

- 30–50 smart-glass images across desks, bags, shelves, cafés, and rooms
- manual labels for visible target objects
- surface / position hint / nearby-object labels
- natural-language search questions for each target object
- single-pass and multi-pass outputs for ablation

## Run

```bash
python docs/experiments/evaluate_portfolio_results.py
```

Smoke-check outputs:

- `docs/experiments/portfolio_results_summary.json`
- `docs/experiments/portfolio_results_summary.md`
