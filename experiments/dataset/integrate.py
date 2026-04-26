"""Integrate Gemini-generated 40-seed dataset into the existing pipeline.

Steps:
  1. Copy each new PNG from data/eval_dataset/slides/ → data/experiment_designs/
  2. For each new slide, extract structured content from its SEED prompt via
     GPT-4o (LLM-as-extractor) and produce a meta.json-style entry
  3. Merge new entries into data/experiment_designs/meta.json
  4. Append entries to data/slide_specs.jsonl (id, type, complexity, primary_rq)

After this, every baseline (single_pass / visual_cot / cot_h_rag) and
LayerAgent.run(slide_id) work on the new slides unchanged.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from openai import OpenAI

from experiments.dataset.seeds import SEEDS

_DATA_DIR = _ROOT / "data" / "experiment_designs"
_META_PATH = _DATA_DIR / "meta.json"
_SPECS_PATH = _ROOT / "data" / "slide_specs.jsonl"
_SLIDES_DIR = _ROOT / "data" / "eval_dataset" / "slides"

# Layout → meta.json `type` value mapping for downstream agents.
_LAYOUT_TO_TYPE = {
    "mekko":         "dashboard",      # has chart_title-like content
    "matrix_2x2":    "feature_grid",   # closest existing semantic
    "waterfall":     "dashboard",
    "harvey_table":  "table",
    "bar_chart":     "dashboard",
    "line_chart":    "dashboard",
    "process_flow":  "timeline",
    "pyramid":       "pyramid",
}

# Complexity heuristic from layout (cheap, post-hoc SCM as continuous covariate
# can refine later)
_LAYOUT_TO_COMPLEXITY = {
    "mekko": "high", "matrix_2x2": "high", "waterfall": "high",
    "harvey_table": "high", "bar_chart": "medium", "line_chart": "medium",
    "process_flow": "medium", "pyramid": "medium",
}


_EXTRACT_PROMPT = """Below is a slide-image-generation prompt that was given to
an image model. Extract the slide's structured content as JSON.

PROMPT:
\"\"\"{prompt}\"\"\"

Return JSON with these top-level keys (use null for any not in the prompt):
{{
  "title": "the action title",
  "subtitle": "subtitle if present, else null",
  "body": <data shape depends on layout — see below>,
  "source": "source attribution",
  "page": <page number as int or null>
}}

For "body" shape per layout:
- mekko:        {{"x_axis": [{{"label", "share_pct"}}, ...],
                  "y_categories": ["cat1", ...],
                  "cells": [[{{"x_label", "y_cat", "value"}}, ...]] }}
- matrix_2x2:   {{"x_axis_label", "y_axis_label", "quadrants": [...],
                  "items": [{{"label", "x_quadrant_idx", "y_quadrant_idx", "size_metric"}}]}}
- waterfall:    {{"start_label", "start_value", "steps": [{{"label", "delta", "is_positive"}}], "end_label"}}
- harvey_table: {{"headers": [...], "rows": [[{{"value_pct", "justification"}}, ...]]}}
- bar_chart:    {{"x_categories": [...], "values": [...], "y_label"}}
- line_chart:   {{"x_axis": [...], "series": [{{"name", "values": [...]}}]}}
- process_flow: {{"steps": [{{"name", "description", "duration"}}, ...]}}
- pyramid:      {{"top": "main message", "middle": [...], "bottom": [...]}}

Output JSON ONLY, no preamble, no markdown fences.
"""


def extract_content(prompt: str, client: OpenAI) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        max_tokens=2500,
        messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(prompt=prompt)}],
    )
    raw = resp.choices[0].message.content or ""
    # strip markdown fences if any
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    try:
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  ✗ JSON parse failed: {e}\n     raw start: {raw[:200]}")
        return {}


def normalize_to_meta_content(layout: str, extracted: dict) -> dict:
    """Map the LLM-extracted body to the meta.json content schema used by
    the downstream baselines. Several layouts collapse onto existing schemas
    so the existing pipeline can render them without modification."""
    title = extracted.get("title", "")
    subtitle = extracted.get("subtitle")
    body = extracted.get("body") or {}
    out = {"title": title}
    if subtitle:
        out["description"] = subtitle

    if layout == "mekko" or layout == "bar_chart" or layout == "line_chart" or layout == "waterfall":
        # Collapse to dashboard-style metrics + chart
        metrics = []
        if layout == "bar_chart":
            cats = body.get("x_categories", [])
            vals = body.get("values", [])
            for c, v in zip(cats[:6], vals[:6]):
                metrics.append({"emoji": "📊", "title": str(c), "value": str(v),
                                "change": ""})
        elif layout == "mekko":
            for col in (body.get("x_axis") or [])[:5]:
                metrics.append({"emoji": "📐", "title": col.get("label", ""),
                                "value": f"{col.get('share_pct', '')}%", "change": ""})
        elif layout == "line_chart":
            series = body.get("series", [])
            if series:
                for s in series[:3]:
                    vals = s.get("values", [])
                    if vals:
                        metrics.append({"emoji": "📈", "title": s.get("name", ""),
                                        "value": f"{vals[-1]}", "change": ""})
        elif layout == "waterfall":
            steps = body.get("steps", [])
            for st in steps[:5]:
                metrics.append({"emoji": "🔁", "title": st.get("label", ""),
                                "value": str(st.get("delta", "")), "change": ""})
        out["metrics"] = metrics
        out["chart_title"] = subtitle or title

    elif layout == "matrix_2x2":
        items = body.get("items", []) or body.get("quadrants", [])
        out["features"] = [
            {"emoji": "🟢", "title": (it.get("label") or it.get("name") or "Item"),
             "description": str(it.get("size_metric", ""))}
            for it in items[:6]
        ]

    elif layout == "harvey_table":
        out["headers"] = body.get("headers", [])
        rows = body.get("rows", [])
        out["rows"] = [
            [(c.get("value_pct") or "") + " " + (c.get("justification") or "")
                if isinstance(c, dict) else str(c)
             for c in row]
            for row in rows[:8]
        ]

    elif layout == "process_flow":
        steps = body.get("steps", [])
        out["items"] = [
            {"step": i + 1, "emoji": "🔵", "title": s.get("name", ""),
             "description": s.get("description") or s.get("duration", "")}
            for i, s in enumerate(steps[:6])
        ]

    elif layout == "pyramid":
        levels = ([body.get("top", "")] + (body.get("middle") or []))[:3]
        out["levels"] = [{"title": str(l) if isinstance(l, str) else l.get("title", ""),
                          "description": ""} for l in levels]

    return out


def main() -> None:
    # 1. Copy PNGs to data/experiment_designs/
    print("[integrate] copying PNGs into data/experiment_designs/")
    copied = 0
    for seed in SEEDS:
        src = _SLIDES_DIR / f"{seed['id']}.png"
        dst = _DATA_DIR / f"{seed['id']}.png"
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            copied += 1
    print(f"  copied {copied} new PNGs")

    # 2. Extract content for each new seed via GPT-4o
    client = OpenAI()
    print(f"\n[integrate] extracting content for {len(SEEDS)} seeds")
    new_meta_entries: list[dict] = []
    new_specs_entries: list[dict] = []
    for i, seed in enumerate(SEEDS, 1):
        sid = seed["id"]
        # skip if already in meta
        print(f"[{i:>2}/{len(SEEDS)}] {sid} ...", flush=True)
        try:
            extracted = extract_content(seed["prompt"], client)
            content = normalize_to_meta_content(seed["layout"], extracted)
            slide_type = _LAYOUT_TO_TYPE.get(seed["layout"], "dashboard")
            complexity = _LAYOUT_TO_COMPLEXITY.get(seed["layout"], "medium")
            new_meta_entries.append({
                "id": sid,
                "type": slide_type,
                "content": content,
                "_layout": seed["layout"],
                "_theme": seed["theme"],
                "_domain": seed["domain"],
            })
            new_specs_entries.append({
                "id": sid, "type": slide_type, "complexity": complexity,
                "primary_rq": "RQ1", "_layout": seed["layout"],
                "_theme": seed["theme"], "_domain": seed["domain"],
            })
            print(f"     ✓ {slide_type}: {list(content.keys())}")
        except Exception as e:
            print(f"     ✗ {e}")

    # 3. Merge into meta.json
    if _META_PATH.exists():
        meta = json.loads(_META_PATH.read_text())
    else:
        meta = {"style": {}, "slides": []}
    existing_ids = {s["id"] for s in meta.get("slides", [])}
    added = 0
    for entry in new_meta_entries:
        if entry["id"] not in existing_ids:
            meta["slides"].append(entry)
            added += 1
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\n[integrate] meta.json: added {added} entries (total {len(meta['slides'])})")

    # 4. Append to slide_specs.jsonl
    existing_spec_ids = set()
    if _SPECS_PATH.exists():
        for line in _SPECS_PATH.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    existing_spec_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    appended = 0
    with _SPECS_PATH.open("a") as f:
        for entry in new_specs_entries:
            if entry["id"] not in existing_spec_ids:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                appended += 1
    print(f"[integrate] slide_specs.jsonl: appended {appended} entries")


if __name__ == "__main__":
    main()
