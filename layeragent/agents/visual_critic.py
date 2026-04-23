"""Visual Critic — render-compare-fix (선택적, 1 iteration)."""
from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from pathlib import Path

from ..prompts.visual_critic import CRITIC_PROMPT, FIXER_PROMPT
from ..utils.common import extract_html, wrap_slide
from ..utils.llm import _openai_client, text_call


def render_html_to_b64(html_content: str, width: int = 1280, height: int = 720) -> str:
    from playwright.sync_api import sync_playwright

    wrapped = wrap_slide(html_content)
    tmp = Path("/tmp/visual_critic_render.html")
    tmp.write_text(wrapped)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=2)
        page = ctx.new_page()
        try:
            page.goto(f"file://{tmp.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{tmp.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(400)
        png_bytes = page.screenshot(clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()
    return base64.b64encode(png_bytes).decode()


def run_critic(reference_b64: str, rendered_b64: str, model: str = "gpt-4o") -> dict:
    client = _openai_client()
    resp = client.chat.completions.create(
        model=model, max_tokens=3000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": CRITIC_PROMPT},
                {"type": "text", "text": "REFERENCE 이미지:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{reference_b64}"}},
                {"type": "text", "text": "RENDERED 이미지 (현재 HTML 출력):"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{rendered_b64}"}},
            ],
        }],
    )
    raw = resp.choices[0].message.content
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"diffs": [], "overall_fidelity": 0.0}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"diffs": [], "overall_fidelity": 0.0}


def run_fixer(html: str, diffs: dict, model: str = "gpt-4o") -> str:
    diff_summary = json.dumps(diffs.get("diffs", [])[:8], ensure_ascii=False, indent=2)
    prompt = FIXER_PROMPT.format(html=html[:30000], diffs=diff_summary)
    raw = text_call(prompt, model, max_tokens=16000)
    result = extract_html(raw)
    if not result or len(result) < 500:
        return html
    return result


def visual_critic(state) -> dict:
    if state.get("ablation") == "no_visual_critic":
        return {"assembled": state.get("assembled", ""), "critic_diffs": None}

    html = state.get("assembled", "")
    if not html or len(html) < 200:
        return {"assembled": html, "critic_diffs": None}

    try:
        rendered_b64 = render_html_to_b64(html)
    except Exception as e:
        print(f"[critic] render failed: {e}")
        return {"assembled": html, "critic_diffs": None}

    reference_b64 = state["image_b64"]
    try:
        diffs = run_critic(reference_b64, rendered_b64, state.get("model", "gpt-4o"))
    except Exception as e:
        print(f"[critic] critic failed: {e}")
        return {"assembled": html, "critic_diffs": None}

    n = len(diffs.get("diffs", []))
    print(f"[critic] {n} diffs, fidelity≈{diffs.get('overall_fidelity', 0):.2f}")
    if n == 0:
        return {"assembled": html, "critic_diffs": diffs}

    try:
        fixed = run_fixer(html, diffs, state.get("model", "gpt-4o"))
    except Exception as e:
        print(f"[critic] fixer failed: {e}")
        return {"assembled": html, "critic_diffs": diffs}

    return {"assembled": fixed, "critic_diffs": diffs}
