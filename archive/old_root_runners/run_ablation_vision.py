#!/usr/bin/env python3
"""
Ablation Study: Asymmetric Vision

F (현재 설계): Content/Icons Agent는 text-only (bbox 좌표만 사용)
F-vision:      Content/Icons Agent에 이미지를 포함 (vision call)

가설: VLM이 이미지를 보면 bbox 좌표를 무시하고 이미지 기반으로 배치하려 해서
      위치가 틀어지고 CCR이 하락한다.

대상: design_01_timeline, design_03_comparison_split,
      design_05_hub_spoke, design_07_feature_grid
"""

import base64
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

# ── F-vision 변형: content_agent와 icons_agent를 vision call로 변경 ──

import src.methods.layer_agents_langgraph as lg
from src.methods.layer_agents_langgraph import (
    LayerAgentState,
    _get_openai_client,
    _vision_call,
    _extract_html,
    _filter_content,
    CONTENT_PROMPT_WITH_BBOX,
    ICONS_PROMPT_WITH_BBOX,
    COMMON_RULES,
)


def content_agent_vision(state: LayerAgentState) -> dict:
    """F-vision: Content Agent WITH image (vision call).

    원래 F는 text-only인데, 여기서는 이미지를 함께 전달하여
    VLM이 이미지 vs bbox 중 어떤 걸 우선하는지 실험.
    """
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})
    content = _filter_content(state.get("content", {}))
    slide_type = state.get("slide_type", "")

    card_bboxes_json = json.dumps(state.get("card_bboxes", []), ensure_ascii=False, indent=2)
    content_json = json.dumps(content, ensure_ascii=False, indent=2)

    prompt = CONTENT_PROMPT_WITH_BBOX.format(
        analysis=state["analysis"],
        slide_type=slide_type,
        card_bboxes_json=card_bboxes_json,
        content_json=content_json,
        text_color=style.get("text_color", "#F1F5F9"),
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    # KEY DIFFERENCE: _vision_call with image instead of text-only
    raw = _vision_call(client, state["image_b64"], prompt, model, max_tokens=6000)
    return {"content_html": _extract_html(raw)}


def icons_agent_vision(state: LayerAgentState) -> dict:
    """F-vision: Icons Agent WITH image (vision call).

    원래 F는 text-only인데, 여기서는 이미지를 함께 전달.
    """
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})

    card_bboxes_json = json.dumps(state.get("card_bboxes", []), ensure_ascii=False, indent=2)

    prompt = ICONS_PROMPT_WITH_BBOX.format(
        analysis=state["analysis"],
        card_bboxes_json=card_bboxes_json,
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    # KEY DIFFERENCE: _vision_call with image instead of text-only
    raw = _vision_call(client, state["image_b64"], prompt, model, max_tokens=6000)
    return {"icons_html": _extract_html(raw)}


def build_vision_pipeline():
    """F-vision pipeline: content_agent와 icons_agent만 vision call로 교체."""
    from langgraph.graph import StateGraph, START, END
    from src.methods.layer_agents_langgraph import (
        visual_cot_analyzer,
        background_agent,
        cards_agent,
        assembler,
        screenshot_agent,
        edit_agent,
    )

    graph = StateGraph(LayerAgentState)

    graph.add_node("visual_cot_analyzer", visual_cot_analyzer)
    graph.add_node("background_agent", background_agent)
    graph.add_node("cards_agent", cards_agent)
    # F-vision: vision call 사용
    graph.add_node("content_agent", content_agent_vision)
    graph.add_node("icons_agent", icons_agent_vision)
    graph.add_node("assembler", assembler)
    graph.add_node("screenshot_agent", screenshot_agent)
    graph.add_node("edit_agent", edit_agent)

    graph.add_edge(START, "visual_cot_analyzer")
    graph.add_edge("visual_cot_analyzer", "background_agent")
    graph.add_edge("visual_cot_analyzer", "cards_agent")

    graph.add_edge("background_agent", "assembler")
    graph.add_edge("cards_agent", "content_agent")
    graph.add_edge("cards_agent", "icons_agent")

    graph.add_edge("content_agent", "assembler")
    graph.add_edge("icons_agent", "assembler")

    graph.add_edge("assembler", "screenshot_agent")
    graph.add_edge("screenshot_agent", "edit_agent")
    graph.add_edge("edit_agent", END)

    return graph.compile()


def generate_f_vision(image_path, slide_id, slide_type, content, style, model="gpt-4o"):
    """F-vision 실행."""
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    pipeline = build_vision_pipeline()

    result = pipeline.invoke({
        "image_b64": b64,
        "slide_id": slide_id,
        "slide_type": slide_type,
        "content": content,
        "style": style,
        "model": model,
    })

    return {
        "analysis": result.get("analysis", ""),
        "card_bboxes": result.get("card_bboxes", []),
        "layers": {
            "bg": result.get("bg_html", ""),
            "cards": result.get("cards_html", ""),
            "content": result.get("content_html", ""),
            "icons": result.get("icons_html", ""),
        },
        "assembled": result.get("assembled", ""),
        "edited": result.get("edited", ""),
    }


def wrap_slide(html_content):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;overflow:hidden;position:relative;">{html_content}</div>
</body></html>"""


def main():
    DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
    RESULTS_DIR = Path(__file__).parent / "results" / "ablation_vision"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "meta.json") as f:
        meta = json.load(f)

    style = meta["style"]
    slides_map = {s["id"]: s for s in meta["slides"]}

    # 실험 대상 디자인
    target_ids = [
        "design_01_timeline",
        "design_03_comparison_split",
        "design_05_hub_spoke",
        "design_07_feature_grid",
    ]

    # 기존 F 결과 로드
    FULL_DIR = Path(__file__).parent / "results" / "full_experiment"

    print("=" * 70)
    print("Ablation Study: Asymmetric Vision (F vs F-vision)")
    print("=" * 70)
    print("F:        Content/Icons Agent = text-only (bbox only)")
    print("F-vision: Content/Icons Agent = vision (image + bbox)")
    print(f"Targets:  {', '.join(target_ids)}")
    print("=" * 70)

    all_results = {}

    for si, sid in enumerate(target_ids):
        slide = slides_map[sid]
        stype = slide["type"]
        content = slide["content"]
        img_path = DATA_DIR / f"{sid}.png"

        slide_dir = RESULTS_DIR / sid
        slide_dir.mkdir(exist_ok=True)

        print(f"\n{'━' * 70}")
        print(f"  [{si+1}/{len(target_ids)}] {sid} ({stype})")
        print(f"{'━' * 70}")

        # Check if F-vision already done
        results_file = slide_dir / "results.json"
        if results_file.exists():
            print(f"  Already done, loading cached results")
            with open(results_file) as f:
                all_results[sid] = json.load(f)
            continue

        # ── Load existing F results ──
        f_results_file = FULL_DIR / sid / "results.json"
        if f_results_file.exists():
            with open(f_results_file) as f:
                f_metrics = json.load(f)["F"]
            print(f"  [F] Loaded from full_experiment: CCR={f_metrics['CCR']:.2f} LOA={f_metrics['LOA']:.2f} CSS={f_metrics['CSS']}")
        else:
            print(f"  [F] No cached result, skipping")
            continue

        # ── Also copy F HTML for comparison screenshots ──
        f_html_path = FULL_DIR / sid / "F.html"
        if f_html_path.exists():
            import shutil
            shutil.copy2(f_html_path, slide_dir / "F.html")
            f_png = FULL_DIR / sid / "F.png"
            if f_png.exists():
                shutil.copy2(f_png, slide_dir / "F.png")

        # ── Run F-vision ──
        print(f"  [F-vision] Running...", end=" ", flush=True)
        t0 = time.time()
        result_fv = generate_f_vision(str(img_path), sid, stype, content, style)
        fv_time = round(time.time() - t0, 1)
        fv_html = result_fv["assembled"]
        fv_edited = result_fv.get("edited", "")
        fv_bboxes = len(result_fv.get("card_bboxes", []))
        print(f"{len(fv_html)} chars ({fv_time:.0f}s) bbox={fv_bboxes}")

        # Save F-vision HTML
        (slide_dir / "F-vision.html").write_text(wrap_slide(fv_html))
        if fv_edited:
            (slide_dir / "F-vision-edited.html").write_text(wrap_slide(fv_edited))

        # ── Screenshot ──
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(f"file://{slide_dir / 'F-vision.html'}")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(slide_dir / "F-vision.png"))
            if fv_edited:
                page.goto(f"file://{slide_dir / 'F-vision-edited.html'}")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(slide_dir / "F-vision-edited.png"))
            browser.close()

        # ── Evaluate ──
        from src.metrics.content_completeness import content_completeness_rate
        from src.metrics.layer_ordering import layer_ordering_accuracy
        from src.metrics.css_effect_preservation import css_richness
        from src.metrics.icon_integrity import icon_integrity_rate

        ccr = content_completeness_rate(content, fv_html)
        loa = layer_ordering_accuracy(fv_html)
        cr = css_richness(fv_html)
        iir = icon_integrity_rate(fv_html)

        fv_metrics = {
            "CCR": ccr["rate"],
            "CCR_high": ccr["high_importance_rate"],
            "CCR_found": ccr["found_items"],
            "CCR_total": ccr["total_items"],
            "LOA": loa["z_index_usage_rate"],
            "LOA_levels": loa["unique_z_levels"],
            "CSS": cr["total_effects"],
            "Colors": cr["unique_colors"],
            "IIR": iir["rate"],
            "time": fv_time,
            "chars": len(fv_html),
            "bboxes": fv_bboxes,
        }

        # Also evaluate edited version if available
        fv_edited_metrics = None
        if fv_edited:
            ccr_e = content_completeness_rate(content, fv_edited)
            loa_e = layer_ordering_accuracy(fv_edited)
            cr_e = css_richness(fv_edited)
            iir_e = icon_integrity_rate(fv_edited)
            fv_edited_metrics = {
                "CCR": ccr_e["rate"],
                "CCR_high": ccr_e["high_importance_rate"],
                "LOA": loa_e["z_index_usage_rate"],
                "LOA_levels": loa_e["unique_z_levels"],
                "CSS": cr_e["total_effects"],
                "Colors": cr_e["unique_colors"],
                "IIR": iir_e["rate"],
            }

        slide_result = {
            "F": f_metrics,
            "F-vision": fv_metrics,
        }
        if fv_edited_metrics:
            slide_result["F-vision-edited"] = fv_edited_metrics

        all_results[sid] = slide_result

        # Save per-slide
        (slide_dir / "results.json").write_text(
            json.dumps(slide_result, indent=2, ensure_ascii=False)
        )

        # Save CCR detail for analysis
        (slide_dir / "ccr_detail.json").write_text(
            json.dumps(ccr, indent=2, ensure_ascii=False)
        )

        # Print comparison
        print(f"\n  {'Metric':<12} {'F':>8} {'F-vision':>10} {'Delta':>8}")
        print(f"  {'-'*42}")
        for k in ["CCR", "LOA", "CSS", "Colors", "IIR"]:
            fv = f_metrics.get(k, 0)
            fvv = fv_metrics.get(k, 0)
            delta = fvv - fv
            sign = "+" if delta > 0 else ""
            if isinstance(fv, float):
                print(f"  {k:<12} {fv:>8.2f} {fvv:>10.2f} {sign}{delta:>7.2f}")
            else:
                print(f"  {k:<12} {fv:>8} {fvv:>10} {sign}{delta:>7}")

    # ══════════════════════════════════════
    # Summary Table
    # ══════════════════════════════════════
    print(f"\n{'═' * 70}")
    print("ABLATION SUMMARY: F (text-only) vs F-vision (with image)")
    print(f"{'═' * 70}")

    # Per-design table
    print(f"\n{'Design':<30} {'Variant':<12} {'CCR':>6} {'LOA':>6} {'CSS':>5} {'Colors':>7} {'IIR':>5}")
    print("-" * 75)
    for sid in target_ids:
        if sid not in all_results:
            continue
        r = all_results[sid]
        short = sid.replace("design_", "").replace("_", " ")
        for variant in ["F", "F-vision"]:
            if variant in r:
                m = r[variant]
                print(f"  {short:<28} {variant:<12} {m['CCR']:>6.2f} {m['LOA']:>6.2f} {m['CSS']:>5} {m.get('Colors', 0):>7} {m['IIR']:>5.2f}")

    # Averages
    metrics_keys = ["CCR", "LOA", "CSS", "Colors", "IIR"]
    avg_f = {k: 0 for k in metrics_keys}
    avg_fv = {k: 0 for k in metrics_keys}
    n = 0
    for sid in target_ids:
        if sid not in all_results:
            continue
        r = all_results[sid]
        n += 1
        for k in metrics_keys:
            avg_f[k] += r["F"].get(k, 0)
            avg_fv[k] += r["F-vision"].get(k, 0)

    if n > 0:
        print(f"\n{'AVERAGE':<30} {'F':>6} {'F-vis':>8} {'Delta':>8}")
        print("-" * 55)
        for k in metrics_keys:
            f_val = avg_f[k] / n
            fv_val = avg_fv[k] / n
            delta = fv_val - f_val
            sign = "+" if delta > 0 else ""
            if isinstance(avg_f[k] / n, float) and avg_f[k] / n <= 1.0:
                print(f"  {k:<28} {f_val:>6.3f} {fv_val:>8.3f} {sign}{delta:>7.3f}")
            else:
                print(f"  {k:<28} {f_val:>6.1f} {fv_val:>8.1f} {sign}{delta:>7.1f}")

    # Conclusion
    if n > 0:
        ccr_delta = (avg_fv["CCR"] - avg_f["CCR"]) / n if avg_f["CCR"] > 0 else 0
        print(f"\n{'─' * 70}")
        if avg_fv["CCR"] / n < avg_f["CCR"] / n:
            print("CONCLUSION: F-vision shows LOWER CCR than F (text-only).")
            print("This supports the hypothesis: VLM with image ignores bbox")
            print("coordinates and attempts image-based placement, causing")
            print("content misalignment.")
        elif avg_fv["CCR"] / n == avg_f["CCR"] / n:
            print("CONCLUSION: F and F-vision show SIMILAR CCR.")
            print("Vision input does not significantly affect content placement.")
        else:
            print("CONCLUSION: F-vision shows HIGHER CCR than F (text-only).")
            print("The hypothesis is NOT supported; vision helps content placement.")
        print(f"{'─' * 70}")

    # Save all results
    (RESULTS_DIR / "all_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False)
    )
    print(f"\nResults saved: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
