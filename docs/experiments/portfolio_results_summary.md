# Artifact smoke-check summary

> Pilot evaluation based on existing sample artifacts in `ai_test2/`.
> The current VLM sample artifacts were generated through the Ollama/Gemma path
> (`gemma4:31b-cloud`). The repository also includes a separate Qwen2.5-VL
> multi-stage inference path for local/server-side deployment.
> This is not a formal benchmark and should not be reported as model accuracy.

## Dataset

| Item | Count |
|---|---:|
| VLM image samples | 2 |
| LLM search samples | 2 |

## VLM artifact checks

| Metric | Result |
|---|---:|
| JSON parse success rate | 100.0% |
| Average objects per image | 7.0 |
| Total structured objects | 14 |
| Surface field coverage | 100.0% |
| Position hint coverage | 100.0% |
| Nearby-object coverage | 100.0% |
| Extracted nearby relations | 25 |
| Average recorded inference time | 35.567 sec |

## LLM search artifact checks

| Metric | Result |
|---|---:|
| Queries with at least one hit | 100.0% |
| Grounded answer rate | 100.0% |
| Average expanded terms | 12.5 |
| Average hits per query | 1.0 |
| Average confidence | 0.26 |

## Interpretation

- Existing sample artifacts are parseable and contain the expected downstream fields.
- The checks confirm schema/readiness, not extraction accuracy.
- Do not use the 100% field-presence values as portfolio performance claims.
- For real evaluation, collect manually labeled images and natural-language search queries.
