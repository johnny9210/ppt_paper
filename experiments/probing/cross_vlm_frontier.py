"""Cross-VLM frontier probing — GPT-5.4 + Claude 4.6 Opus single-pass.

Question: Does the perception-generation gap close when we use a STRONGER
frontier model than GPT-4o (the one our LayerAgent was built on)?

For each dark-glass design × {GPT-5.4, Claude 4.6 Opus}:
  - Run single-pass: image + content_json -> HTML
  - Track token usage (prompt_tokens, completion_tokens)
  - Parse HTML -> layer tree
  - Compute Layer Recall and LTED vs cached perception tree (GPT-4o anchor)

Cost-efficiency narrative: compare LayerAgent (GPT-4o, ~8 specialists) vs
single-pass on more expensive frontier models. If LayerAgent on cheap GPT-4o
beats single-pass on expensive GPT-5.4/Opus, that's the strongest possible
defense of decomposition.

Output:
  results/cross_vlm/frontier_probing.jsonl
  results/cross_vlm/frontier_summary.json
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from experiments.probing.layer_tree import (
    layer_recall,
    lted as _lted,
    parse_html_tree,
    parse_perception_response,
)
from layeragent.utils.common import (
    b64_image, extract_html, filter_content, get_design_by_id, load_meta,
)


PERCEPTION_DIR = _ROOT / "data" / "eval_dataset" / "perception"
OUT_DIR = _ROOT / "results" / "cross_vlm"
RAW_DIR = _ROOT / "results" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Single-pass prompt (image + structured content -> HTML), identical to
# baselines/multi_model.py PROMPT_WITH_CONTENT for fair comparison.
PROMPT = """이 디자인 이미지를 HTML+CSS로 변환하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

규칙:
- 슬라이드 크기: 1280x720px
- 이미지의 시각적 구조를 최대한 정확히 재현
- 위 텍스트 콘텐츠를 디자인에 맞게 배치
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""


# 10 dark-glass sweet-spot designs (same as probing_minimal)
DESIGNS = [
    "design_01_timeline", "design_02_dashboard", "design_03_comparison_split",
    "design_04_pyramid", "design_05_hub_spoke", "design_06_before_after",
    "design_07_feature_grid", "design_08_roadmap", "design_09_layered_stack",
    "design_10_stats_hero",
]


def _detect_image_format(img_bytes: bytes) -> str:
    if img_bytes[:4] == b"\x89PNG":
        return "png"
    if img_bytes[:3] == b"\xff\xd8\xff":
        return "jpeg"
    return "png"


def call_gpt54(image_b64: str, prompt: str) -> tuple[str, dict]:
    """Returns (text, {prompt_tokens, completion_tokens, total_tokens})."""
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=os.getenv("APIM_AOAI_ENDPOINT"),
        api_key=os.getenv("APIM_AOAI_API_KEY"),
        api_version=os.getenv("GPT_API_VERSION", "2025-04-01-preview"),
    )
    model = os.getenv("GPT_MODEL", "gpt-5.4")
    resp = client.chat.completions.create(
        model=model, max_completion_tokens=8000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "total_tokens": resp.usage.total_tokens,
    }
    return text, usage


def call_claude_opus(image_b64: str, prompt: str) -> tuple[str, dict]:
    """Returns (text, {input_tokens, output_tokens, total_tokens}) via Bedrock."""
    import boto3
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    model_id = os.getenv("BEDROCK_CLAUDE_OPUS_MODEL_ID")
    img_bytes = base64.b64decode(image_b64)
    img_format = _detect_image_format(img_bytes)
    resp = bedrock.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": img_format, "source": {"bytes": img_bytes}}},
                {"text": prompt},
            ],
        }],
        inferenceConfig={"maxTokens": 8000},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    usage = {
        "prompt_tokens": resp["usage"]["inputTokens"],
        "completion_tokens": resp["usage"]["outputTokens"],
        "total_tokens": resp["usage"]["totalTokens"],
    }
    return text, usage


# Approximate USD pricing per million tokens (2026 Q1 estimates).
# These are *list prices*; actual costs vary by deployment/contract.
PRICING = {
    "gpt-4o":         {"input_per_m": 2.50,  "output_per_m": 10.00},
    "gpt-5.4":        {"input_per_m": 5.00,  "output_per_m": 15.00},
    "claude-4.6-opus":{"input_per_m": 15.00, "output_per_m": 75.00},
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICING[model]
    return (prompt_tokens * p["input_per_m"] + completion_tokens * p["output_per_m"]) / 1_000_000


def run_one(model_name: str, did: str, image_b64: str, content_json: str) -> dict:
    prompt = PROMPT.format(content_json=content_json)
    t0 = time.time()
    if model_name == "gpt-5.4":
        text, usage = call_gpt54(image_b64, prompt)
    elif model_name == "claude-4.6-opus":
        text, usage = call_claude_opus(image_b64, prompt)
    else:
        raise ValueError(f"unknown model: {model_name}")
    elapsed = time.time() - t0
    html = extract_html(text)

    # Save HTML for traceability
    out_html_dir = RAW_DIR / f"single_pass_{model_name.replace('.', '_').replace('-','_')}"
    out_html_dir.mkdir(parents=True, exist_ok=True)
    (out_html_dir / f"{did}_seed0.html").write_text(html)

    # Compute metrics
    perc_path = PERCEPTION_DIR / f"{did}.txt"
    perc_tree = parse_perception_response(perc_path.read_text())
    gen_tree = parse_html_tree(html)
    L = _lted(perc_tree, gen_tree)
    R = layer_recall(perc_tree, gen_tree)
    cost = cost_usd(model_name, usage["prompt_tokens"], usage["completion_tokens"])

    return {
        "model": model_name,
        "design_id": did,
        "elapsed_s": elapsed,
        "html_len": len(html),
        "n_layers_gen": len(gen_tree),
        "lted": L,
        "layer_recall": R,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": cost,
    }


def main() -> None:
    meta = load_meta()
    out_path = OUT_DIR / "frontier_probing.jsonl"

    # Resume support
    done: set[tuple[str, str]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                done.add((r["model"], r["design_id"]))
            except Exception:
                pass

    rows: list[dict] = []
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

    models = ["gpt-5.4", "claude-4.6-opus"]
    total = len(models) * len(DESIGNS)
    n_done = 0

    with out_path.open("a") as f:
        for model_name in models:
            for did in DESIGNS:
                key = (model_name, did)
                if key in done:
                    n_done += 1
                    print(f"  [{n_done}/{total}] cached  {model_name} / {did}")
                    continue
                try:
                    image_b64 = b64_image(did)
                except FileNotFoundError as e:
                    print(f"  ERR {model_name}/{did}: {e}")
                    continue
                design = get_design_by_id(meta, did)
                content_json = json.dumps(filter_content(design["content"]),
                                          ensure_ascii=False, indent=2)
                try:
                    print(f"  [{n_done+1}/{total}] {model_name} / {did} ...", flush=True)
                    r = run_one(model_name, did, image_b64, content_json)
                    rows.append(r)
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    f.flush()
                    n_done += 1
                    print(f"      LTED={r['lted']:.3f}  Recall={r['layer_recall']:.3f}  "
                          f"tok={r['total_tokens']}  ${r['cost_usd']:.4f}  "
                          f"layers={r['n_layers_gen']}  {r['elapsed_s']:.1f}s")
                except Exception as e:
                    print(f"      ERR {type(e).__name__}: {e}")

    # Aggregate
    from statistics import mean, stdev
    print("\n=== Aggregate (N={}) ===".format(len(DESIGNS)))
    print(f"{'model':<22} {'LTED':>13} {'Recall':>13} {'tokens':>10} {'cost$':>9} {'time(s)':>9}")
    summary = {}
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        if not sub:
            continue
        ltd = [r["lted"] for r in sub]
        rcl = [r["layer_recall"] for r in sub]
        tok = [r["total_tokens"] for r in sub]
        cost = [r["cost_usd"] for r in sub]
        elapsed = [r["elapsed_s"] for r in sub]
        summary[m] = {
            "n": len(sub),
            "lted_mean": mean(ltd), "lted_std": stdev(ltd) if len(ltd) > 1 else 0,
            "recall_mean": mean(rcl), "recall_std": stdev(rcl) if len(rcl) > 1 else 0,
            "tokens_mean": mean(tok), "tokens_total": sum(tok),
            "cost_mean": mean(cost), "cost_total": sum(cost),
            "elapsed_mean": mean(elapsed),
        }
        print(f"{m:<22} {mean(ltd):.3f}±{stdev(ltd) if len(ltd)>1 else 0:.3f}  "
              f"{mean(rcl):.3f}±{stdev(rcl) if len(rcl)>1 else 0:.3f}  "
              f"{int(mean(tok)):>10} {mean(cost):>9.4f} {mean(elapsed):>9.1f}")

    # Compare to existing baselines (from main_eval N=10 dark-glass subset)
    print("\n=== Reference (main_eval N=10 dark-glass subset, no token tracking) ===")
    print("single_pass(gpt-4o):  LTED 0.823, Recall 0.224, ~unknown tokens")
    print("layeragent(gpt-4o):   LTED 0.551, Recall 0.759, 8-stage decomposition")

    summary_path = OUT_DIR / "frontier_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {summary_path}")


if __name__ == "__main__":
    main()
