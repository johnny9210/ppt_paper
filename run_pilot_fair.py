#!/usr/bin/env python3
"""
Fair Pilot: 모든 method에 content 제공 + 5개 메트릭 + VLM-as-Judge.
slide_003 (three_column) 단일 슬라이드.
"""

import base64
import json
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

client = OpenAI()
DATA_DIR = Path(__file__).parent / "data" / "design_images"
RESULTS_DIR = Path(__file__).parent / "results" / "pilot_fair"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


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


def wrap_slide(html_content, title):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden;position:relative;">{html_content}</div>
</body></html>"""


def main():
    with open(DATA_DIR / "session_meta.json") as f:
        meta = json.load(f)

    style = meta["research_brief"]["style"]
    sc = meta["slide_contents"][2]  # slide_003
    sid, stype = sc["slide_id"], sc["type"]
    content = sc.get("content", {})
    img_path = DATA_DIR / f"{sid}_design.png"
    b64 = base64.b64encode(img_path.read_bytes()).decode()

    print("=" * 70)
    print(f"Fair Pilot: {sid} ({stype}) — 모든 method에 content 제공")
    print("=" * 70)

    results = {}

    # ── A: Baseline + Content ──
    print(f"\n[A] Baseline + Content...", end=" ", flush=True)
    from src.methods.baseline import generate_with_content as a_gen
    t0 = time.time()
    html_a = extract_html(a_gen(client, b64, content))
    results["A"] = {"html": html_a, "time": round(time.time() - t0, 1)}
    print(f"{len(html_a)} chars ({results['A']['time']:.0f}s)")

    # ── B: Visual CoT + Content ──
    print(f"[B] Visual CoT + Content...", end=" ", flush=True)
    from src.methods.visual_cot import generate_with_content as b_gen
    t0 = time.time()
    _, html_b = b_gen(client, b64, content)
    html_b = extract_html(html_b)
    results["B"] = {"html": html_b, "time": round(time.time() - t0, 1)}
    print(f"{len(html_b)} chars ({results['B']['time']:.0f}s)")

    # ── C: CoT + H-RAG + Content ──
    print(f"[C] CoT + H-RAG + Content...", end=" ", flush=True)
    from src.methods.cot_hrag import generate_with_content as c_gen
    t0 = time.time()
    _, _, html_c = c_gen(client, b64, content)
    html_c = extract_html(html_c)
    results["C"] = {"html": html_c, "time": round(time.time() - t0, 1)}
    print(f"{len(html_c)} chars ({results['C']['time']:.0f}s)")

    # ── E: Layer Agents v2 ──
    print(f"[E] Layer Agents v2...", end=" ", flush=True)
    from src.methods.layer_agents_v2 import generate_from_saved_image as e_gen
    t0 = time.time()
    result_e = e_gen(client, str(img_path), sid, stype, content, style)
    html_e = result_e["assembled"]
    results["E"] = {"html": html_e, "time": round(time.time() - t0, 1)}
    print(f"{len(html_e)} chars ({results['E']['time']:.0f}s)")

    # ── F: LayerAgent (ours) ──
    print(f"[F] LayerAgent...", end=" ", flush=True)
    import src.methods.layer_agents_langgraph as lg
    lg._pipeline = None
    from src.methods.layer_agents_langgraph import generate_from_saved_image as f_gen
    t0 = time.time()
    result_f = f_gen(str(img_path), sid, stype, content, style)
    html_f = result_f["assembled"]
    html_fplus = result_f["edited"]
    results["F"] = {"html": html_f, "time": round(time.time() - t0, 1), "bboxes": len(result_f.get("card_bboxes", []))}
    results["F+"] = {"html": html_fplus, "time": 0}
    print(f"{len(html_f)} → edit:{len(html_fplus)} chars ({results['F']['time']:.0f}s)")

    # ── HTML 저장 + 스크린샷 ──
    for method, data in results.items():
        fname = f"method_{method.replace('+', 'plus')}.html"
        (RESULTS_DIR / fname).write_text(wrap_slide(data["html"], f"Method {method}"))

    print(f"\n스크린샷 촬영...", flush=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for method in results:
            fname = f"method_{method.replace('+', 'plus')}.html"
            page.goto(f"file://{RESULTS_DIR / fname}")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(RESULTS_DIR / f"method_{method.replace('+', 'plus')}.png"))
        browser.close()

    # ══════════════════════════════════════
    # 평가: 5개 메트릭
    # ══════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("평가")
    print(f"{'=' * 70}")

    from src.metrics.content_completeness import content_completeness_rate
    from src.metrics.layer_ordering import layer_ordering_accuracy
    from src.metrics.css_effect_preservation import css_richness
    from src.metrics.icon_integrity import icon_integrity_rate

    eval_results = {}
    for method, data in results.items():
        html = data["html"]
        ccr = content_completeness_rate(content, html)
        loa = layer_ordering_accuracy(html)
        cr = css_richness(html)
        iir = icon_integrity_rate(html)

        eval_results[method] = {
            "CCR": ccr["rate"],
            "CCR_high": ccr["high_importance_rate"],
            "CCR_found": f"{ccr['found_items']}/{ccr['total_items']}",
            "LOA": loa["z_index_usage_rate"],
            "LOA_levels": loa["unique_z_levels"],
            "CSS_effects": cr["total_effects"],
            "CSS_colors": cr["unique_colors"],
            "IIR": iir["rate"],
            "time": data["time"],
        }

    # ── VLM-as-Judge ──
    print(f"\nVLM-as-Judge (pairwise)...", flush=True)
    judge_prompt = """두 개의 슬라이드 HTML 렌더링 결과를 비교합니다.

[원본 디자인 이미지] (첫 번째 이미지)
[Method X 결과] (두 번째 이미지)
[Method Y 결과] (세 번째 이미지)

다음 기준으로 평가하세요:
1. 레이아웃 정확도: 원본 디자인의 카드/컬럼 구조를 얼마나 잘 재현했는가? (1-10)
2. 시각 품질: 배경, 카드 스타일, 색상이 원본과 얼마나 비슷한가? (1-10)
3. 콘텐츠 완성도: 텍스트가 적절히 배치되어 있는가? (1-10)
4. 전체 점수: 종합적으로 어느 쪽이 더 나은 슬라이드인가? (1-10)

JSON으로 응답:
{"X": {"layout": N, "visual": N, "content": N, "overall": N}, "Y": {"layout": N, "visual": N, "content": N, "overall": N}}"""

    from PIL import Image
    design_img_b64 = b64

    # 핵심 비교: A vs F, C vs F, E vs F
    comparisons = [("A", "F"), ("C", "F"), ("E", "F")]
    judge_results = {}

    for mx, my in comparisons:
        mx_img = RESULTS_DIR / f"method_{mx}.png"
        my_img = RESULTS_DIR / f"method_{my}.png"
        if not mx_img.exists() or not my_img.exists():
            continue

        mx_b64 = base64.b64encode(mx_img.read_bytes()).decode()
        my_b64 = base64.b64encode(my_img.read_bytes()).decode()

        resp = client.chat.completions.create(
            model="gpt-4o", max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{design_img_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{mx_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{my_b64}"}},
                    {"type": "text", "text": judge_prompt.replace("Method X", f"Method {mx}").replace("Method Y", f"Method {my}")},
                ],
            }],
        )
        raw = resp.choices[0].message.content
        try:
            # JSON 추출
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                scores = json.loads(json_match.group(0))
                judge_results[f"{mx}_vs_{my}"] = scores
                print(f"  {mx} vs {my}: {mx}={scores.get(mx, scores.get('X', {}))}, {my}={scores.get(my, scores.get('Y', {}))}")
        except:
            print(f"  {mx} vs {my}: parse error")
            judge_results[f"{mx}_vs_{my}"] = raw

    # ── 요약 테이블 ──
    print(f"\n{'=' * 70}")
    print(f"{'Method':<6} {'CCR':>5} {'LOA':>5} {'CSS':>5} {'Colors':>7} {'IIR':>5} {'Time':>6}")
    print("-" * 50)
    for method in ["A", "B", "C", "E", "F", "F+"]:
        if method not in eval_results:
            continue
        r = eval_results[method]
        print(f"{method:<6} {r['CCR']:>5.2f} {r['LOA']:>5.2f} {r['CSS_effects']:>5} {r['CSS_colors']:>7} {r['IIR']:>5.2f} {r['time']:>5.0f}s")

    # JSON 저장
    (RESULTS_DIR / "evaluation.json").write_text(
        json.dumps({"metrics": eval_results, "judge": judge_results}, ensure_ascii=False, indent=2, default=str)
    )
    print(f"\nSaved: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
