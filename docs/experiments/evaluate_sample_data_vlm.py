"""Run and evaluate VLM extraction on existing sample_data images.

This script turns the repository's existing wallet/key image collection into a
reproducible first-pass VLM evaluation.

It uses filename-derived weak labels:

- ``wallet_*.jpg`` -> expected object: wallet
- ``key_*.jpg`` -> expected object: key

This is stronger than evaluating two hand-picked JSON files, but still not a
replacement for manually labeled bounding/object annotations. Treat the results
as a repository-internal benchmark over the existing sample_data set.

Examples
--------

Run a small balanced subset:

    python docs/experiments/evaluate_sample_data_vlm.py --max-per-class 10

Run all wallet/key images:

    python docs/experiments/evaluate_sample_data_vlm.py

Summarize already generated outputs without calling the VLM:

    python docs/experiments/evaluate_sample_data_vlm.py --no-inference
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
INFERENCE_APP_DIR = REPO_ROOT / "apps" / "inference-server"
SAMPLE_DATA_DIR = INFERENCE_APP_DIR / "sample_data"
OUTPUT_DIR = Path(__file__).resolve().parent / "sample_data_vlm_outputs"
SUMMARY_JSON = Path(__file__).resolve().parent / "sample_data_vlm_summary.json"
SUMMARY_MD = Path(__file__).resolve().parent / "sample_data_vlm_summary.md"

LABEL_ALIASES = {
    "wallet": {
        "wallet",
        "purse",
        "card holder",
        "card wallet",
        "지갑",
        "카드지갑",
        "카드 지갑",
    },
    "key": {
        "key",
        "keys",
        "keyring",
        "key ring",
        "열쇠",
        "키",
        "키링",
    },
}


@dataclass
class SampleItem:
    image_path: str
    label: str


@dataclass
class SampleResult:
    image_path: str
    label: str
    status: str
    latency_sec: float | None
    detected_terms: list[str]
    matched: bool
    output_path: str
    error: str | None = None


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _configure_ollama_env() -> None:
    _load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("OLLAMA_API_URL") and os.getenv("API_LLM_OLLAMA_BASE_URL"):
        os.environ["OLLAMA_API_URL"] = os.getenv("API_LLM_OLLAMA_BASE_URL", "")
    if not os.getenv("OLLAMA_API_KEY") and os.getenv("API_LLM_OLLAMA_API_KEY"):
        os.environ["OLLAMA_API_KEY"] = os.getenv("API_LLM_OLLAMA_API_KEY", "")
    if not os.getenv("OLLAMA_VLM_MODEL"):
        os.environ["OLLAMA_VLM_MODEL"] = os.getenv("OLLAMA_VLM_MODEL", "gemma4:31b-cloud")
    if not os.getenv("OLLAMA_TIMEOUT_SEC"):
        os.environ["OLLAMA_TIMEOUT_SEC"] = "90"
    if not os.getenv("OLLAMA_RETRY_COUNT"):
        os.environ["OLLAMA_RETRY_COUNT"] = "2"


def _collect_samples(max_per_class: int | None) -> list[SampleItem]:
    grouped: dict[str, list[Path]] = {"wallet": [], "key": []}
    for path in sorted(SAMPLE_DATA_DIR.iterdir()):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if lower_name.startswith("wallet_"):
            grouped["wallet"].append(path)
        elif lower_name.startswith("key_"):
            grouped["key"].append(path)

    samples: list[SampleItem] = []
    for label, paths in grouped.items():
        selected = paths[:max_per_class] if max_per_class else paths
        samples.extend(
            SampleItem(
                image_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                label=label,
            )
            for path in selected
        )
    return samples


def _output_path_for(sample: SampleItem) -> Path:
    image_path = Path(sample.image_path)
    return OUTPUT_DIR / f"{image_path.stem}.json"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _extract_terms(payload: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    metadata = payload.get("metadata") or {}
    pipeline_output = payload.get("pipeline_output") or {}

    for key in ("caption", "sceneSummary", "positionHint"):
        value = metadata.get(key) or pipeline_output.get(key)
        if value:
            terms.append(str(value))

    for value in metadata.get("detectedObjects") or []:
        terms.append(str(value))

    for value in metadata.get("tags") or []:
        terms.append(str(value))

    for obj in payload.get("objects") or pipeline_output.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        terms.append(str(obj.get("name") or ""))
        position = obj.get("position") or {}
        if isinstance(position, dict):
            terms.append(str(position.get("hint") or ""))
            terms.append(str(position.get("surface") or ""))
        for nearby in obj.get("nearby_objects") or obj.get("nearbyObjects") or []:
            terms.append(str(nearby))

    return [term for term in terms if term.strip()]


def _matches_label(label: str, terms: list[str]) -> bool:
    haystack = "\n".join(_normalize_text(term) for term in terms)
    return any(alias.lower() in haystack for alias in LABEL_ALIASES[label])


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_inference(sample: SampleItem) -> tuple[dict[str, Any], float]:
    _configure_ollama_env()
    sys.path.insert(0, str(INFERENCE_APP_DIR))
    from src.adapters.ollama_adapter import generate_ollama_vlm_metadata

    image_path = REPO_ROOT / sample.image_path
    started = time.perf_counter()
    with Image.open(image_path) as image:
        result = generate_ollama_vlm_metadata(image=image.convert("RGB"))
    latency = time.perf_counter() - started
    return result, latency


def evaluate_samples(samples: list[SampleItem], run_inference: bool) -> list[SampleResult]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[SampleResult] = []

    for index, sample in enumerate(samples, start=1):
        out_path = _output_path_for(sample)
        try:
            if run_inference:
                print(f"[{index}/{len(samples)}] Running VLM: {sample.image_path}")
                payload, latency = _run_inference(sample)
                out_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            elif out_path.exists():
                print(f"[{index}/{len(samples)}] Reusing: {out_path.name}")
                payload = _read_json(out_path)
                latency = payload.get("elapsed_sec")
            else:
                print(f"[{index}/{len(samples)}] Missing cached output: {sample.image_path}")
                results.append(
                    SampleResult(
                        image_path=sample.image_path,
                        label=sample.label,
                        status="missing_output",
                        latency_sec=None,
                        detected_terms=[],
                        matched=False,
                        output_path=str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        error="Run without --no-inference to generate this output.",
                    )
                )
                continue

            terms = _extract_terms(payload)
            results.append(
                SampleResult(
                    image_path=sample.image_path,
                    label=sample.label,
                    status="success",
                    latency_sec=round(float(latency), 3) if latency is not None else None,
                    detected_terms=terms,
                    matched=_matches_label(sample.label, terms),
                    output_path=str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                )
            )
        except Exception as exc:
            results.append(
                SampleResult(
                    image_path=sample.image_path,
                    label=sample.label,
                    status="error",
                    latency_sec=None,
                    detected_terms=[],
                    matched=False,
                    output_path=str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100.0, 1)


def summarize(results: list[SampleResult]) -> dict[str, Any]:
    successful = [item for item in results if item.status == "success"]
    latencies = [item.latency_sec for item in successful if item.latency_sec is not None]
    by_label: dict[str, dict[str, Any]] = {}
    for label in sorted(LABEL_ALIASES):
        label_results = [item for item in successful if item.label == label]
        by_label[label] = {
            "samples": len(label_results),
            "matched": sum(1 for item in label_results if item.matched),
            "weak_label_recall_pct": _pct(
                sum(1 for item in label_results if item.matched),
                len(label_results),
            ),
        }

    return {
        "dataset": {
            "total_samples": len(results),
            "successful_outputs": len(successful),
            "errors": sum(1 for item in results if item.status == "error"),
        },
        "overall": {
            "weak_label_matches": sum(1 for item in successful if item.matched),
            "weak_label_recall_pct": _pct(
                sum(1 for item in successful if item.matched),
                len(successful),
            ),
            "avg_latency_sec": round(sum(latencies) / len(latencies), 3)
            if latencies
            else None,
        },
        "by_label": by_label,
        "results": [asdict(item) for item in results],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    overall = summary["overall"]
    by_label = summary["by_label"]

    rows = "\n".join(
        f"| {label} | {item['samples']} | {item['matched']} | {item['weak_label_recall_pct']}% |"
        for label, item in by_label.items()
    )

    return f"""# Sample-data VLM evaluation

This benchmark uses filename-derived weak labels from existing repository images.
It is more meaningful than a two-sample smoke check, but still weaker than a
manually labeled dataset.

## Dataset

| Metric | Value |
|---|---:|
| Total samples | {dataset['total_samples']} |
| Successful VLM outputs | {dataset['successful_outputs']} |
| Errors | {dataset['errors']} |

## Overall

| Metric | Value |
|---|---:|
| Weak-label matches | {overall['weak_label_matches']} |
| Weak-label recall | {overall['weak_label_recall_pct']}% |
| Average latency | {overall['avg_latency_sec']} sec |

## By label

| Label | Samples | Matched | Weak-label recall |
|---|---:|---:|---:|
{rows}

## Caveat

The labels are inferred from filenames such as `wallet_*.jpg` and `key_*.jpg`.
Use this as a first-pass benchmark only. A final portfolio result should use
manual object and spatial-relation labels.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-class", type=int, default=0)
    parser.add_argument("--no-inference", action="store_true")
    args = parser.parse_args()

    samples = _collect_samples(args.max_per_class or None)
    if not samples:
        raise SystemExit("No wallet/key samples found.")

    results = evaluate_samples(samples, run_inference=not args.no_inference)
    summary = summarize(results)
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_MD.write_text(render_markdown(summary), encoding="utf-8")
    print(render_markdown(summary))
    print(f"Wrote {SUMMARY_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {SUMMARY_MD.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
