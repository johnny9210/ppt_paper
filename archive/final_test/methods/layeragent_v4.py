"""LayerAgent v4 — Extraction-augmented agents.

v3 대비 유일한 변경: Hero/Card Detail Agent가 프롬프트 안에 **결정론적 CV 추출값**을 FACT로 받는다.
VLM 측정 의존 → CV 도구 측정 의존.

리뷰어 3명 합의:
- VLM은 "이 텍스트가 영역의 30%" 같은 비율 측정이 약함 (58% 정확도, ±15% 오차).
- k-means/HSV/OCR은 100% 결정론적.
- 프롬프트에 값 하드코딩 아님 — 값은 이미지에서 매번 새로 뽑힘.

재사용: v3의 analyzer, bg_agent, assembler, style_normalizer, text_inserter
교체: card_detail_agents_v4, hero_detail_agents_v4 (CV facts 주입)
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from . import _common
from .bbox_utils import draw_bbox_on_image
from .cv_extractors import visual_facts, format_facts_as_prompt
from .layeragent_v3 import (
    CropAgentStateV3,
    analyzer_v3,
    assembler_v3,
    text_inserter_v3,
)
from src.methods import crop_layer_agent as _la


# ════════════════════════════════════════════════════════════
# Card Detail v4 — CV facts 주입
# ════════════════════════════════════════════════════════════

CARD_DETAIL_PROMPT_V4 = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 카드 {card_idx}**를 HTML+CSS로 재현하세요.

{facts_block}

★ 위 결정론적 측정값을 그대로 반영 (VLM이 추측하지 말 것):
- CSS 색상은 palette에서 가져오기 (role에 맞게 — bg는 bg_primary, 강조는 accent)
- 글자 크기는 OCR 높이에서 유도 (1rem ≈ 16px 환산)
- 채도가 높다고 나오면 rgba alpha를 낮추지 말고 채도 유지

★ Global context (빨간 네모 바깥도 관찰):
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}
- 다른 카드들과 일관된 스타일 유지

★★★ **정규화된 class 이름 필수**:
- 컨테이너: `.card-{card_idx}`
- 아이콘: **`.card-icon`**, 값: **`.card-value`**, 라벨: **`.card-label`** (다른 이름 금지)
- 구조:
  ```
  <div class="card-{card_idx}">
    <div class="card-icon">아이콘자리</div>
    <div class="card-value">값자리</div>
    <div class="card-label">라벨자리</div>
  </div>
  ```

★ 빨간 사각형 안만 묘사 — 바깥 요소 만들지 마세요
★ 크기: width:100%; height:100%; position:relative;
★ 카드 형태가 가로형이면 flex-row, 세로형이면 flex-column (실제 이미지에서 판단)
★ 텍스트 내용은 넣지 마세요 (나중에 Text Inserter가 채움)
★ <style>과 <div>로만 출력"""


def card_detail_agents_v4(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    palette_global = analysis.get("global_palette", {})
    aesthetic = analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette_global.items() if v) or "(분석 못함)"

    card_htmls: list[str] = []
    card_positions: list[dict] = []

    for i, card in enumerate(cards_meta):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))

        # CV 추출 — 이 카드 영역의 결정론적 측정값
        try:
            facts = visual_facts(full, bbox_ratio=bbox)
            facts_block = format_facts_as_prompt(facts)
        except Exception as e:
            facts_block = f"(CV 추출 실패: {e})"

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=6, label=f"CARD_{i+1}")
        prompt = CARD_DETAIL_PROMPT_V4.format(
            card_idx=i + 1,
            facts_block=facts_block,
            palette_hint=palette_hint,
            aesthetic_hint=aesthetic,
        )
        raw = _la._vision_call(highlighted, prompt, model, max_tokens=6000)
        card_htmls.append(_la._extract_html(raw))

        card_positions.append({
            "card_id": f"card_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
            "content_area": {
                "left": round(bbox[0] * 100 + 1.5, 1),
                "top": round(bbox[1] * 100 + 1.5, 1),
                "width": round((bbox[2] - bbox[0]) * 100 - 3, 1),
                "height": round((bbox[3] - bbox[1]) * 100 - 3, 1),
            },
        })

    return {"card_htmls": card_htmls, "card_positions": card_positions}


# ════════════════════════════════════════════════════════════
# Hero Detail v4 — CV facts 주입
# ════════════════════════════════════════════════════════════

HERO_DETAIL_PROMPT_V4 = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 HERO 영역 {hero_idx}**를 HTML+CSS로 재현하세요.

{facts_block}

★ 위 결정론적 측정값을 그대로 반영:
- **OCR가 hero 텍스트의 실제 픽셀 높이를 알려줬다면** 그 값을 font-size로 써라 (예: 127px → font-size: 8rem).
  **추측해서 "font-size: 2.5rem" 같은 작은 값 쓰지 말 것.**
- Palette의 accent 색을 큰 값(hero-value)에 사용 — 채도를 죽이지 말 것
- 고채도 영역 비율이 50% 이상이면 accent를 과감히 써라 (배경과 강한 대비)

★ Hero 영역 특징 (이미지에서 관찰):
- 큰 placeholder 숫자/제목이 있는 standalone 박스
- 프레임/테두리 색상 (실제 이미지 관찰하여 재현)
- 내부 여백, 정렬

★ Global context:
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}

★★★ **정규화된 class 이름 필수**:
- 컨테이너: `.hero-{hero_idx}`
- 메인 큰 값: **`.hero-value`** (예: "XXXX", "300%")
- 서브타이틀: **`.hero-subtitle`**
- 구조:
  ```
  <div class="hero-{hero_idx}">
    <div class="hero-value">값자리</div>
    <div class="hero-subtitle">서브자리</div>
  </div>
  ```

★ 크기: width:100%; height:100%; position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center;
★ 텍스트 placeholder는 넣어도 OK (Text Inserter가 교체)
★ <style>과 <div>로만"""


def hero_detail_agents_v4(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    heros = analysis.get("hero_blocks", [])
    palette_global = analysis.get("global_palette", {})
    aesthetic = analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette_global.items() if v) or "(분석 못함)"

    hero_htmls: list[str] = []
    hero_positions: list[dict] = []

    for i, h in enumerate(heros):
        bbox = (h.get("x1", 0), h.get("y1", 0), h.get("x2", 1), h.get("y2", 1))
        try:
            facts = visual_facts(full, bbox_ratio=bbox)
            facts_block = format_facts_as_prompt(facts)
        except Exception as e:
            facts_block = f"(CV 추출 실패: {e})"

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=8, label=f"HERO_{i+1}")
        prompt = HERO_DETAIL_PROMPT_V4.format(
            hero_idx=i + 1,
            facts_block=facts_block,
            palette_hint=palette_hint,
            aesthetic_hint=aesthetic,
        )
        raw = _la._vision_call(highlighted, prompt, model, max_tokens=6000)
        hero_htmls.append(_la._extract_html(raw))
        hero_positions.append({
            "hero_id": f"hero_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
        })

    return {"hero_htmls": hero_htmls, "hero_positions": hero_positions}


# ════════════════════════════════════════════════════════════
# Pipeline v4
# ════════════════════════════════════════════════════════════

def _maybe_hero(state: CropAgentStateV3) -> dict:
    heros = state.get("analysis", {}).get("hero_blocks", [])
    if not heros:
        return {"hero_htmls": [], "hero_positions": []}
    return hero_detail_agents_v4(state)


def build_pipeline_v4():
    g = StateGraph(CropAgentStateV3)
    g.add_node("analyzer", analyzer_v3)  # v3 그대로
    g.add_node("background_agent", _la.background_agent)
    g.add_node("card_detail_agents", card_detail_agents_v4)  # ← CV facts 주입
    g.add_node("hero_detail_agents", _maybe_hero)             # ← CV facts 주입
    g.add_node("assembler", assembler_v3)                    # v3 (title 상시 표시)
    g.add_node("style_normalizer", _la.style_normalizer)
    g.add_node("text_inserter", text_inserter_v3)
    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "background_agent")
    g.add_edge("analyzer", "card_detail_agents")
    g.add_edge("analyzer", "hero_detail_agents")
    g.add_edge("background_agent", "assembler")
    g.add_edge("card_detail_agents", "assembler")
    g.add_edge("hero_detail_agents", "assembler")
    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", "text_inserter")
    g.add_edge("text_inserter", END)
    return g.compile()


_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline_v4()
    return _pipeline


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    image_b64 = _common.b64_image(slide_id)
    pipeline = _get_pipeline()
    result = pipeline.invoke({
        "image_b64": image_b64,
        "slide_id": slide_id,
        "slide_type": design["type"],
        "content": design["content"],
        "style": meta["style"],
        "model": model,
    })
    return _common.extract_html(result.get("assembled", ""))
