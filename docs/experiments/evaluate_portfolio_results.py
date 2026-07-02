"""Smoke-check smart-glass VLM/LLM sample outputs.

The goal of this script is not to benchmark model quality. Instead, it checks
whether existing sample artifacts in ``ai_test2/`` are parseable and contain the
fields required by the downstream memory-search pipeline:

 - structured JSON validity
 - object and relationship fields
 - recorded runtime metadata
 - 3-stage LLM search output fields

Do not report the generated percentages as model accuracy. A proper benchmark
requires a labeled dataset and object/retrieval ground truth.

Run from the repository root:

    python docs/experiments/evaluate_portfolio_results.py
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent

VLM_RESULT_FILES = [
    REPO_ROOT / "ai_test2" / "vlm_generation_result.json",
    REPO_ROOT / "ai_test2" / "vlm_generation_result_cup.json",
]

LLM_RESULT_FILES = [
    REPO_ROOT / "ai_test2" / "llm_search_result.json",
    REPO_ROOT / "ai_test2" / "llm_search_result_cup.json",
]


@dataclass
class VlmSampleMetric:
    file: str
    model: str | None
    object_count: int
    detected_object_count: int
    inference_time_sec: float | None
    valid_json: bool
    objects_with_surface: int
    objects_with_nearby_objects: int
    objects_with_position_hint: int
    nearby_relation_count: int


@dataclass
class LlmSampleMetric:
    file: str
    query: str
    answer_mode: str | None
    total_hits: int
    confidence: float | None
    expanded_term_count: int
    cited_memory_count: int
    has_grounded_answer: bool


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # pragma: no cover - diagnostic path
        return None, f"{type(exc).__name__}: {exc}"


def _pipeline_output(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("pipeline_output") or payload.get("pipelineOutput") or {}


def _objects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    direct_objects = payload.get("objects")
    if isinstance(direct_objects, list):
        return [item for item in direct_objects if isinstance(item, dict)]
    pipeline_objects = _pipeline_output(payload).get("objects", [])
    return [item for item in pipeline_objects if isinstance(item, dict)]


def _detected_objects(payload: dict[str, Any]) -> list[str]:
    detected = (payload.get("metadata") or {}).get("detectedObjects", [])
    return [item for item in detected if isinstance(item, str) and item.strip()]


def _surface_of(obj: dict[str, Any]) -> str:
    position = obj.get("position") or {}
    if isinstance(position, dict):
        surface = position.get("surface")
        if isinstance(surface, str):
            return surface.strip()
    return ""


def _position_hint_of(obj: dict[str, Any]) -> str:
    position = obj.get("position") or {}
    if isinstance(position, dict):
        hint = position.get("hint") or position.get("positionHint")
        if isinstance(hint, str):
            return hint.strip()
    hint = obj.get("positionHint")
    return hint.strip() if isinstance(hint, str) else ""


def _nearby_objects_of(obj: dict[str, Any]) -> list[str]:
    nearby = obj.get("nearby_objects") or obj.get("nearbyObjects") or []
    if not isinstance(nearby, list):
        return []
    return [item for item in nearby if isinstance(item, str) and item.strip()]


def evaluate_vlm(path: Path) -> VlmSampleMetric:
    payload, error = _read_json(path)
    if payload is None:
        return VlmSampleMetric(
            file=str(path.relative_to(REPO_ROOT)),
            model=None,
            object_count=0,
            detected_object_count=0,
            inference_time_sec=None,
            valid_json=False,
            objects_with_surface=0,
            objects_with_nearby_objects=0,
            objects_with_position_hint=0,
            nearby_relation_count=0,
        )

    objects = _objects(payload)
    nearby_lists = [_nearby_objects_of(item) for item in objects]
    pipeline_output = _pipeline_output(payload)
    runtime = payload.get("runtime") or {}

    return VlmSampleMetric(
        file=str(path.relative_to(REPO_ROOT)),
        model=payload.get("model_id")
        or (payload.get("providerMetadata") or {}).get("modelId")
        or payload.get("provider"),
        object_count=len(objects),
        detected_object_count=len(_detected_objects(payload)),
        inference_time_sec=payload.get("elapsed_sec")
        or pipeline_output.get("inference_time")
        or runtime.get("latencySec"),
        valid_json=error is None,
        objects_with_surface=sum(1 for item in objects if _surface_of(item)),
        objects_with_nearby_objects=sum(1 for nearby in nearby_lists if nearby),
        objects_with_position_hint=sum(1 for item in objects if _position_hint_of(item)),
        nearby_relation_count=sum(len(nearby) for nearby in nearby_lists),
    )


def evaluate_llm(path: Path) -> LlmSampleMetric:
    payload, _ = _read_json(path)
    if payload is None:
        return LlmSampleMetric(
            file=str(path.relative_to(REPO_ROOT)),
            query="",
            answer_mode=None,
            total_hits=0,
            confidence=None,
            expanded_term_count=0,
            cited_memory_count=0,
            has_grounded_answer=False,
        )

    pipeline = payload.get("_pipeline") or {}
    expansion = pipeline.get("stage2_expansion") or {}
    expanded_terms = expansion.get("expanded_terms") or []
    cited_memory_ids = payload.get("citedMemoryIds") or []
    answer = payload.get("answer") or ""

    return LlmSampleMetric(
        file=str(path.relative_to(REPO_ROOT)),
        query=payload.get("query") or "",
        answer_mode=payload.get("answerMode"),
        total_hits=int(payload.get("totalHits") or 0),
        confidence=payload.get("confidence"),
        expanded_term_count=len(expanded_terms)
        if isinstance(expanded_terms, list)
        else 0,
        cited_memory_count=len(cited_memory_ids)
        if isinstance(cited_memory_ids, list)
        else 0,
        has_grounded_answer=bool(answer.strip()) and bool(cited_memory_ids),
    )


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(statistics.mean(clean), 3)


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def build_summary(
    vlm_metrics: list[VlmSampleMetric],
    llm_metrics: list[LlmSampleMetric],
) -> dict[str, Any]:
    total_objects = sum(item.object_count for item in vlm_metrics)
    valid_json_count = sum(1 for item in vlm_metrics if item.valid_json)
    object_surface_count = sum(item.objects_with_surface for item in vlm_metrics)
    object_nearby_count = sum(item.objects_with_nearby_objects for item in vlm_metrics)
    object_position_count = sum(item.objects_with_position_hint for item in vlm_metrics)

    grounded_answers = sum(1 for item in llm_metrics if item.has_grounded_answer)
    hit_queries = sum(1 for item in llm_metrics if item.total_hits > 0)

    return {
        "dataset": {
            "vlm_samples": len(vlm_metrics),
            "llm_search_samples": len(llm_metrics),
            "note": "Pilot evaluation based on existing sample artifacts under ai_test2/.",
        },
        "vlm": {
            "json_parse_success_rate_pct": _pct(valid_json_count, len(vlm_metrics)),
            "avg_objects_per_image": _safe_mean(
                [float(item.object_count) for item in vlm_metrics]
            ),
            "total_objects": total_objects,
            "surface_coverage_pct": _pct(object_surface_count, total_objects),
            "position_hint_coverage_pct": _pct(object_position_count, total_objects),
            "nearby_object_coverage_pct": _pct(object_nearby_count, total_objects),
            "nearby_relation_count": sum(
                item.nearby_relation_count for item in vlm_metrics
            ),
            "avg_inference_time_sec": _safe_mean(
                [
                    float(item.inference_time_sec)
                    for item in vlm_metrics
                    if item.inference_time_sec is not None
                ]
            ),
        },
        "llm": {
            "queries_with_hits_pct": _pct(hit_queries, len(llm_metrics)),
            "grounded_answer_rate_pct": _pct(grounded_answers, len(llm_metrics)),
            "avg_expanded_terms": _safe_mean(
                [float(item.expanded_term_count) for item in llm_metrics]
            ),
            "avg_hits_per_query": _safe_mean(
                [float(item.total_hits) for item in llm_metrics]
            ),
            "avg_confidence": _safe_mean(
                [
                    float(item.confidence)
                    for item in llm_metrics
                    if item.confidence is not None
                ]
            ),
        },
        "samples": {
            "vlm": [asdict(item) for item in vlm_metrics],
            "llm": [asdict(item) for item in llm_metrics],
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    vlm = summary["vlm"]
    llm = summary["llm"]

    return f"""# Artifact smoke-check summary

> Pilot evaluation based on existing sample artifacts in `ai_test2/`.
> The current VLM sample artifacts were generated through the Ollama/Gemma path
> (`gemma4:31b-cloud`). The repository also includes a separate Qwen2.5-VL
> multi-stage inference path for local/server-side deployment.
> This is not a formal benchmark and should not be reported as model accuracy.

## Dataset

| Item | Count |
|---|---:|
| VLM image samples | {dataset["vlm_samples"]} |
| LLM search samples | {dataset["llm_search_samples"]} |

## VLM artifact checks

| Metric | Result |
|---|---:|
| JSON parse success rate | {vlm["json_parse_success_rate_pct"]}% |
| Average objects per image | {vlm["avg_objects_per_image"]} |
| Total structured objects | {vlm["total_objects"]} |
| Surface field coverage | {vlm["surface_coverage_pct"]}% |
| Position hint coverage | {vlm["position_hint_coverage_pct"]}% |
| Nearby-object coverage | {vlm["nearby_object_coverage_pct"]}% |
| Extracted nearby relations | {vlm["nearby_relation_count"]} |
| Average recorded inference time | {vlm["avg_inference_time_sec"]} sec |

## LLM search artifact checks

| Metric | Result |
|---|---:|
| Queries with at least one hit | {llm["queries_with_hits_pct"]}% |
| Grounded answer rate | {llm["grounded_answer_rate_pct"]}% |
| Average expanded terms | {llm["avg_expanded_terms"]} |
| Average hits per query | {llm["avg_hits_per_query"]} |
| Average confidence | {llm["avg_confidence"]} |

## Interpretation

- Existing sample artifacts are parseable and contain the expected downstream fields.
- The checks confirm schema/readiness, not extraction accuracy.
- Do not use the 100% field-presence values as portfolio performance claims.
- For real evaluation, collect manually labeled images and natural-language search queries.
"""


def main() -> None:
    vlm_metrics = [evaluate_vlm(path) for path in VLM_RESULT_FILES]
    llm_metrics = [evaluate_llm(path) for path in LLM_RESULT_FILES]
    summary = build_summary(vlm_metrics, llm_metrics)

    json_path = OUTPUT_DIR / "portfolio_results_summary.json"
    md_path = OUTPUT_DIR / "portfolio_results_summary.md"

    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(summary), encoding="utf-8")

    print(f"Wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"Wrote {md_path.relative_to(REPO_ROOT)}")
    print(render_markdown(summary))


if __name__ == "__main__":
    main()
