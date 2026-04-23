#!/usr/bin/env python3
"""
멀티 모델 실험: GPT-5.4, Claude 4.6 Opus, Claude 4.5 Sonnet로 A vs F 비교.
디자인 3개 × 모델 3개 × method 2개 = 18 runs.
"""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import boto3
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import AzureOpenAI, OpenAI

DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
RESULTS_BASE = Path(__file__).parent / "results"


# ══════════════════════════════════════
# Model Clients
# ══════════════════════════════════════

def get_gpt4o_client():
    """기존 GPT-4o (OpenAI direct)."""
    return OpenAI(), "gpt-4o"


def get_gpt54_client():
    """GPT-5.4 via Azure OpenAI."""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("APIM_AOAI_ENDPOINT"),
        api_key=os.getenv("APIM_AOAI_API_KEY"),
        api_version=os.getenv("GPT_API_VERSION", "2025-04-01-preview"),
    )
    return client, os.getenv("GPT_MODEL", "gpt-5.4")


def call_bedrock_claude(model_id: str, messages: list, max_tokens: int = 8000) -> str:
    """AWS Bedrock Claude 호출 (Converse API)."""
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    # Convert OpenAI message format to Bedrock Converse format
    converse_messages = []
    for msg in messages:
        parts = []
        if isinstance(msg["content"], str):
            parts.append({"text": msg["content"]})
        elif isinstance(msg["content"], list):
            for part in msg["content"]:
                if part["type"] == "text":
                    parts.append({"text": part["text"]})
                elif part["type"] == "image_url":
                    url = part["image_url"]["url"]
                    if "base64," in url:
                        b64 = url.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64)
                        # 실제 포맷 감지
                        fmt = "jpeg" if img_bytes[:2] == b'\xff\xd8' else "png"
                        parts.append({"image": {"format": fmt, "source": {"bytes": img_bytes}}})
        converse_messages.append({"role": msg["role"], "content": parts})

    resp = bedrock.converse(
        modelId=model_id,
        messages=converse_messages,
        inferenceConfig={"maxTokens": max_tokens},
    )
    return resp["output"]["message"]["content"][0]["text"]


# ══════════════════════════════════════
# Method implementations (model-agnostic)
# ══════════════════════════════════════

def extract_html(text):
    text = text.strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0:
        text = text[start.start():]
    return text.strip()


def run_visual_cot(model_name: str, b64: str, content: dict, call_fn) -> str:
    """Method B: Visual CoT with content."""
    from src.methods.visual_cot import ANALYSIS_PROMPT, GENERATE_PROMPT_WITH_CONTENT
    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)

    # Step 1: Analysis
    analysis = call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": ANALYSIS_PROMPT},
    ]}], max_tokens=2000)

    # Step 2: Generate with content
    raw = call_fn([
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": ANALYSIS_PROMPT},
        ]},
        {"role": "assistant", "content": analysis},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": GENERATE_PROMPT_WITH_CONTENT.format(content_json=content_json)},
        ]},
    ], max_tokens=8000)
    return extract_html(raw)


def run_cot_hrag(model_name: str, b64: str, content: dict, call_fn) -> str:
    """Method C: CoT + H-RAG with content."""
    from src.methods.cot_hrag import ANALYSIS_PROMPT, GENERATE_PROMPT_WITH_CONTENT, _build_pattern_context
    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)

    analysis = call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": ANALYSIS_PROMPT},
    ]}], max_tokens=2000)

    patterns = _build_pattern_context(analysis)

    raw = call_fn([
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": ANALYSIS_PROMPT},
        ]},
        {"role": "assistant", "content": analysis},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": GENERATE_PROMPT_WITH_CONTENT.format(patterns=patterns, content_json=content_json)},
        ]},
    ], max_tokens=8000)
    return extract_html(raw)


def run_layer_agents(model_name: str, b64: str, sid: str, stype: str, content: dict, style: dict, call_fn) -> str:
    """Method E: Layer Agents (independent, no coord sharing)."""
    from src.methods.layer_agents_v2 import (
        PRECISE_ANALYSIS_PROMPT, BG_PROMPT, CARDS_PROMPT,
        CONTENT_PROMPT, ICONS_PROMPT, COMMON_RULES, _extract_html,
    )

    primary = style.get("primary_color", "#3B82F6")
    accent = style.get("accent_color", "#60A5FA")
    bg_color = style.get("background", "#0F172A")
    text_color = style.get("text_color", "#F1F5F9")

    analysis = call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": PRECISE_ANALYSIS_PROMPT},
    ]}], max_tokens=3000)

    fmt = {"analysis": analysis, "primary": primary, "accent": accent,
           "bg_color": bg_color, "text_color": text_color, "slide_id": sid, "common_rules": COMMON_RULES}

    bg_html = _extract_html(call_fn([{"role": "user", "content": BG_PROMPT.format(**fmt)}], max_tokens=4000))
    cards_html = _extract_html(call_fn([{"role": "user", "content": CARDS_PROMPT.format(**fmt)}], max_tokens=4000))

    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)
    content_html = _extract_html(call_fn([{"role": "user", "content": CONTENT_PROMPT.format(**fmt, content_json=content_json)}], max_tokens=4000))
    icons_html = _extract_html(call_fn([{"role": "user", "content": ICONS_PROMPT.format(**fmt)}], max_tokens=4000))

    return f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_html}</div>
    <div style="position:absolute;inset:0;z-index:10;">{cards_html}</div>
    <div style="position:absolute;inset:0;z-index:20;">{content_html}</div>
    <div style="position:absolute;inset:0;z-index:30;">{icons_html}</div>
</div>"""


def run_baseline(model_name: str, b64: str, content: dict, call_fn) -> str:
    """Method A: Baseline with content."""
    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)

    prompt = f"""이 디자인 이미지를 HTML+CSS로 변환하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

규칙:
- 슬라이드 크기: 1280x720px
- 이미지의 시각적 구조를 최대한 정확히 재현
- 위 텍스트 콘텐츠를 디자인에 맞게 배치
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]}]

    raw = call_fn(messages, max_tokens=8000)
    return extract_html(raw)


def run_layeragent(model_name: str, b64: str, sid: str, stype: str, content: dict, style: dict, call_fn) -> dict:
    """Method F: LayerAgent — model-agnostic version."""
    from src.methods.layer_agents_langgraph import (
        PRECISE_ANALYSIS_PROMPT, BG_PROMPT, CARDS_PROMPT,
        CONTENT_PROMPT_WITH_BBOX, ICONS_PROMPT_WITH_BBOX, COMMON_RULES,
        _extract_html, _extract_bbox_json, _filter_content, _get_content_structure,
    )

    filtered_content = _filter_content(content)
    content_structure, expected_cards = _get_content_structure(filtered_content, stype)

    primary = style.get("primary_color", "#3B82F6")
    accent = style.get("accent_color", "#60A5FA")
    bg_color = style.get("background", "#0F172A")
    text_color = style.get("text_color", "#F1F5F9")

    # Step 1: Visual CoT Analysis
    analysis = call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": PRECISE_ANALYSIS_PROMPT},
    ]}], max_tokens=4000)

    fmt = {"analysis": analysis, "primary": primary, "accent": accent,
           "bg_color": bg_color, "slide_id": sid, "common_rules": COMMON_RULES}

    # Step 2: BG Agent (vision)
    bg_prompt = BG_PROMPT.format(**fmt)
    bg_html = _extract_html(call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": bg_prompt},
    ]}], max_tokens=6000))

    # Step 3: Cards Agent (vision)
    cards_prompt = CARDS_PROMPT.format(**fmt, slide_type=stype,
        content_structure=content_structure, expected_cards=expected_cards)
    cards_raw = call_fn([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": cards_prompt},
    ]}], max_tokens=6000)
    cards_html = _extract_html(cards_raw)
    card_bboxes = _extract_bbox_json(cards_raw)

    # Step 4: Content Agent (text-only)
    card_bboxes_json = json.dumps(card_bboxes, ensure_ascii=False, indent=2)
    content_json = json.dumps(filtered_content, ensure_ascii=False, indent=2)
    content_prompt = CONTENT_PROMPT_WITH_BBOX.format(
        **fmt, slide_type=stype, card_bboxes_json=card_bboxes_json,
        content_json=content_json, text_color=text_color)
    content_html = _extract_html(call_fn([{"role": "user", "content": content_prompt}], max_tokens=6000))

    # Step 5: Icons Agent (text-only)
    icons_prompt = ICONS_PROMPT_WITH_BBOX.format(**fmt, card_bboxes_json=card_bboxes_json)
    icons_html = _extract_html(call_fn([{"role": "user", "content": icons_prompt}], max_tokens=6000))

    # Assemble
    assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_html}</div>
    <div style="position:absolute;inset:0;z-index:10;">{cards_html}</div>
    <div style="position:absolute;inset:0;z-index:20;">{content_html}</div>
    <div style="position:absolute;inset:0;z-index:30;">{icons_html}</div>
</div>"""

    return {"assembled": assembled, "card_bboxes": card_bboxes}


def wrap_slide(html):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body><div style="width:1280px;height:720px;overflow:hidden;position:relative;">{html}</div></body></html>"""


def main():
    with open(DATA_DIR / "meta.json") as f:
        meta = json.load(f)

    style = meta["style"]
    target_ids = ["design_01_timeline", "design_02_dashboard", "design_03_comparison_split", "design_04_pyramid", "design_05_hub_spoke"]
    target_slides = [s for s in meta["slides"] if s["id"] in target_ids]

    # Model configs
    models = {
        "claude-4.5-sonnet": {"type": "bedrock", "model_id": os.getenv("BEDROCK_CLAUDE_SONNET_MODEL_ID")},
        "claude-4.6-opus": {"type": "bedrock", "model_id": os.getenv("BEDROCK_CLAUDE_OPUS_MODEL_ID")},
    }

    # Build call functions
    def make_call_fn(model_key, model_cfg):
        if model_cfg["type"] == "openai":
            client = OpenAI()
            model = "gpt-4o"
            def call_fn(messages, max_tokens=8000):
                resp = client.chat.completions.create(model=model, max_tokens=max_tokens, messages=messages)
                return resp.choices[0].message.content
            return call_fn
        elif model_cfg["type"] == "azure":
            client, model = get_gpt54_client()
            def call_fn(messages, max_tokens=8000):
                resp = client.chat.completions.create(model=model, max_completion_tokens=max_tokens, messages=messages)
                return resp.choices[0].message.content
            return call_fn
        elif model_cfg["type"] == "bedrock":
            model_id = model_cfg["model_id"]
            def call_fn(messages, max_tokens=8000):
                return call_bedrock_claude(model_id, messages, max_tokens)
            return call_fn

    METHODS = ["A", "B", "C", "E", "F"]

    print("=" * 70)
    print(f"Multi-Model Experiment: {len(target_slides)} designs × {len(models)} models × {len(METHODS)} methods")
    print("=" * 70)

    all_results = {}

    for slide in target_slides:
        sid = slide["id"]
        stype = slide["type"]
        content = slide["content"]
        img_path = DATA_DIR / f"{sid}.png"
        b64 = base64.b64encode(img_path.read_bytes()).decode()

        print(f"\n{'━'*70}")
        print(f"  {sid} ({stype})")
        print(f"{'━'*70}")

        for model_key, model_cfg in models.items():
            call_fn = make_call_fn(model_key, model_cfg)
            model_dir = RESULTS_BASE / model_key / sid
            model_dir.mkdir(parents=True, exist_ok=True)

            result_key = f"{sid}__{model_key}"
            method_results = {}

            print(f"  [{model_key}]", end=" ", flush=True)

            for method in METHODS:
                print(f"{method}...", end=" ", flush=True)
                t0 = time.time()
                html = ""
                try:
                    if method == "A":
                        html = run_baseline(model_key, b64, content, call_fn)
                    elif method == "B":
                        html = run_visual_cot(model_key, b64, content, call_fn)
                    elif method == "C":
                        html = run_cot_hrag(model_key, b64, content, call_fn)
                    elif method == "E":
                        html = run_layer_agents(model_key, b64, sid, stype, content, style, call_fn)
                    elif method == "F":
                        result_f = run_layeragent(model_key, b64, sid, stype, content, style, call_fn)
                        html = result_f["assembled"]
                    dt = time.time() - t0
                    print(f"{len(html)}c", end=" ", flush=True)
                except Exception as e:
                    dt = 0
                    print(f"ERR", end=" ", flush=True)

                (model_dir / f"{method}.html").write_text(wrap_slide(html))

                from src.metrics.content_completeness import content_completeness_rate
                from src.metrics.layer_ordering import layer_ordering_accuracy
                from src.metrics.css_effect_preservation import css_richness

                if html:
                    ccr = content_completeness_rate(content, html)
                    loa = layer_ordering_accuracy(html)
                    cr = css_richness(html)
                    method_results[method] = {
                        "CCR": ccr["rate"], "LOA": loa["z_index_usage_rate"],
                        "CSS": cr["total_effects"], "Colors": cr["unique_colors"], "time": round(dt, 1),
                    }
                else:
                    method_results[method] = {"CCR": 0, "LOA": 0, "CSS": 0, "Colors": 0, "time": 0}

            print()
            all_results[result_key] = method_results

            # Screenshots
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page(viewport={"width": 1280, "height": 720})
                    for method in METHODS:
                        f = model_dir / f"{method}.html"
                        if f.exists():
                            page.goto(f"file://{f}")
                            page.wait_for_timeout(1000)
                            page.screenshot(path=str(model_dir / f"{method}.png"))
                    browser.close()
            except:
                pass

    # Summary
    print(f"\n{'═'*70}")
    print("전체 요약 (3개 디자인 평균)")
    print(f"{'═'*70}")
    print(f"{'Model':<20} {'Method':<6} {'CCR':>5} {'LOA':>5} {'CSS':>5} {'Colors':>7}")
    print("-" * 55)

    for model_key in models:
        for method in METHODS:
            ccr_sum = loa_sum = css_sum = colors_sum = 0
            n = 0
            for slide in target_slides:
                rk = f"{slide['id']}__{model_key}"
                if rk in all_results and method in all_results[rk]:
                    r = all_results[rk][method]
                    ccr_sum += r["CCR"]
                    loa_sum += r["LOA"]
                    css_sum += r["CSS"]
                    colors_sum += r["Colors"]
                    n += 1
            if n > 0:
                print(f"{model_key:<20} {method:<6} {ccr_sum/n:>5.2f} {loa_sum/n:>5.2f} {css_sum/n:>5.1f} {colors_sum/n:>7.1f}")
        print()

    # 모델별 averages.json 저장
    for model_key in models:
        model_avg = {}
        for method in METHODS:
            ccr_sum = loa_sum = css_sum = colors_sum = 0
            n = 0
            for slide in target_slides:
                rk = f"{slide['id']}__{model_key}"
                if rk in all_results and method in all_results[rk]:
                    r = all_results[rk][method]
                    ccr_sum += r["CCR"]; loa_sum += r["LOA"]
                    css_sum += r["CSS"]; colors_sum += r["Colors"]
                    n += 1
            if n > 0:
                model_avg[method] = {"CCR": round(ccr_sum/n, 3), "LOA": round(loa_sum/n, 3),
                                     "CSS": round(css_sum/n, 1), "Colors": round(colors_sum/n, 1)}
        model_path = RESULTS_BASE / model_key
        model_path.mkdir(parents=True, exist_ok=True)
        (model_path / "averages.json").write_text(json.dumps(model_avg, indent=2, ensure_ascii=False))

    (RESULTS_BASE / "multi_model_all.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"Saved: {RESULTS_BASE}")


if __name__ == "__main__":
    main()
