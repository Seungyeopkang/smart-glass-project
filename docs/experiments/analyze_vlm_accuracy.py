"""VLM extraction accuracy on cached sample_data outputs (corrected aliases)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent
CACHED_DIR = OUTPUT_DIR / "sample_data_vlm_outputs"

# "키" intentionally removed: it partial-matched "키보드" and inflated key recall.
LABEL_ALIASES = {
    "wallet": {"wallet", "purse", "card holder", "card wallet", "지갑", "카드지갑", "카드 지갑"},
    "key": {"key", "keys", "keyring", "key ring", "열쇠", "키링"},
}


@dataclass
class Row:
    image: str
    label: str
    detected_names: list[str]
    matched_alias: str | None
    correct: bool
    latency_sec: float | None


def _label(path: Path) -> str | None:
    s = path.stem.lower()
    if s.startswith("wallet_"):
        return "wallet"
    if s.startswith("key_"):
        return "key"
    return None


def _names(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    md = payload.get("metadata") or {}
    for v in md.get("detectedObjects") or []:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    objs = payload.get("objects") or payload.get("pipeline_output", {}).get("objects") or []
    for o in objs:
        if isinstance(o, dict) and isinstance(o.get("name"), str) and o["name"].strip():
            out.append(o["name"].strip())
    return out


def _match(label: str, names: list[str]) -> str | None:
    for n in names:
        low = n.lower()
        for a in LABEL_ALIASES[label]:
            if a in low:
                return a
    return None


def analyze() -> list[Row]:
    rows: list[Row] = []
    for p in sorted(CACHED_DIR.glob("*.json")):
        lab = _label(p)
        if not lab:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        ns = _names(data)
        alias = _match(lab, ns)
        rows.append(Row(p.stem, lab, ns, alias, alias is not None, data.get("elapsed_sec")))
    return rows


def summarize(rows: list[Row]) -> dict[str, Any]:
    by_label: dict[str, Any] = {}
    for lab in sorted(LABEL_ALIASES):
        lr = [r for r in rows if r.label == lab]
        c = sum(1 for r in lr if r.correct)
        by_label[lab] = {
            "samples": len(lr),
            "correct": c,
            "recall_pct": round(c / len(lr) * 100, 1) if lr else 0.0,
        }
    tc = sum(1 for r in rows if r.correct)
    lats = [r.latency_sec for r in rows if r.latency_sec is not None]
    return {
        "overall": {
            "samples": len(rows),
            "correct": tc,
            "recall_pct": round(tc / len(rows) * 100, 1) if rows else 0.0,
            "avg_latency_sec": round(sum(lats) / len(lats), 3) if lats else None,
        },
        "by_label": by_label,
        "rows": [asdict(r) for r in rows],
    }


def render_md(s: dict[str, Any]) -> str:
    o = s["overall"]
    bl = s["by_label"]
    rows = s["rows"]
    ll = "\n".join(
        f"| {k} | {v['samples']} | {v['correct']} | {v['recall_pct']}% |"
        for k, v in bl.items()
    )
    rl = "\n".join(
        f"| {r['image']} | {r['label']} | {', '.join(r['detected_names'][:4])} | "
        f"{r['matched_alias'] or '—'} | {'✓' if r['correct'] else '✗'} | "
        f"{r['latency_sec'] or '—'} |"
        for r in rows
    )
    return f"""# VLM extraction accuracy (corrected aliases)

> Portfolio lightweight experiment over cached gemma4:31b-cloud outputs.
> Recall = filename-derived label object present in VLM detectedObjects/objects.
> Alias "키" removed (it partial-matched "키보드" and inflated key recall).

## Overall

| Metric | Value |
|---|---:|
| Samples | {o['samples']} |
| Correct (recall) | {o['correct']} |
| Recall | {o['recall_pct']}% |
| Avg latency | {o['avg_latency_sec']} sec |

## By label

| Label | Samples | Correct | Recall |
|---|---:|---:|---:|
{ll}

## Per-image

| Image | Label | Detected (first 4) | Matched | OK | Latency(s) |
|---|---|---|---|---|---:|
{rl}
"""


def main() -> None:
    rows = analyze()
    if not rows:
        raise SystemExit("No cached VLM outputs found.")
    s = summarize(rows)
    (OUTPUT_DIR / "vlm_accuracy_summary.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "vlm_accuracy_summary.md").write_text(render_md(s), encoding="utf-8")
    print(render_md(s))


if __name__ == "__main__":
    main()
