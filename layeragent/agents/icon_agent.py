"""Icon Specialist — 카드 아이콘 개념 식별 후 FontAwesome class 매핑.

v10 개선:
- Anti-convergence: 이전 카드가 고른 개념을 현재 agent 에게 "피하라"고 전달
- Ordinal metaphor: sequential layout (roadmap/timeline/pyramid) 에서 step 위치 기반 메타포 힌트
- 순차 처리 (병렬 X) — 각 카드가 이전 결과를 보려면 반드시 순차
"""
from __future__ import annotations

import json
import re

from ..libraries.icon_library import concept_to_fa_class, fa_icon_html
from ..libraries.ordinal_metaphors import is_sequential_layout, ordinal_concept_suggestions
from ..utils.bbox import draw_bbox_on_image
from ..utils.llm import vision_call


ICON_CONCEPT_PROMPT_V10 = """이 슬라이드 이미지에서 빨간 사각형 **카드 {card_idx}** 내부의 아이콘을 관찰하라.

{diversity_hint}

{ordinal_hint}

유효 개념 단어 (이 중 하나):
- 비즈니스: chart, graph, analytics, data, metric, growth, revenue, dashboard
- 보안: shield, security, lock, key, verified
- 글로벌: globe, earth, world, network, cloud, server, wifi, broadcast, satellite
- 사람: user, people, team, handshake, partnership, customer
- 문서: document, file, folder, archive, clipboard
- 시간: clock, time, schedule, calendar, deadline, alarm
- 커뮤니케이션: mail, message, chat, phone, microphone
- 개발: code, terminal, robot, ai, gear, database, bug
- 디자인: palette, brush, camera, image, star, heart
- 네비: arrow_up, arrow_right, play, refresh, rocket, target, flag
- 건축: building, office, factory, store, home
- 연구: flask, science, research, atom, dna
- 교통: truck, delivery, ship, plane, car
- 기타: idea, lightbulb, innovation, info, warning, success,
       gift, award, trophy, medal, crown, seed, sprout, tree

JSON:
```json
{{
  "concept": "단어 하나",
  "confidence": 0.0~1.0,
  "rationale": "짧은 설명"
}}
```

★ 다른 카드와 시각적으로 구별되는 개념을 선택하라.
JSON만, 설명 없이."""


def _build_diversity_hint(already_chosen: list[str]) -> str:
    if not already_chosen:
        return ""
    chosen_str = ", ".join(f"'{c}'" for c in already_chosen)
    return (
        f"★ **이미 다른 카드에서 사용된 개념**: {chosen_str}\n"
        f"★ 위 개념들과 **시각적으로 구별되는 다른 개념**을 선택하라. 같은 개념 반복 금지."
    )


def _build_ordinal_hint(step_idx: int, total_steps: int, is_sequential: bool) -> str:
    if not is_sequential or total_steps < 2:
        return ""
    suggestions = ordinal_concept_suggestions(step_idx, total_steps)
    return (
        f"★ **순서 힌트** — 이 카드는 {total_steps}단계 중 {step_idx + 1}번째.\n"
        f"   각 단계는 스토리 일부이므로 진행 단계에 어울리는 은유:\n"
        f"   {' 또는 '.join(f'{c}' for c in suggestions[:4])}.\n"
        f"   카드의 실제 아이콘 내용을 우선하되, 해당 없으면 위 중 하나 선택."
    )


def identify_icon_concept(
    image_b64: str, card_bbox, card_idx: int, model: str = "gpt-4o",
    already_chosen: list[str] | None = None,
    step_idx: int = 0, total_steps: int = 1, is_sequential: bool = False,
) -> dict:
    highlighted = draw_bbox_on_image(image_b64, card_bbox, color=(255, 0, 0), width=6,
                                      label=f"CARD_{card_idx}")
    diversity_hint = _build_diversity_hint(already_chosen or [])
    ordinal_hint = _build_ordinal_hint(step_idx, total_steps, is_sequential)
    prompt = ICON_CONCEPT_PROMPT_V10.format(
        card_idx=card_idx, diversity_hint=diversity_hint, ordinal_hint=ordinal_hint
    )
    raw = vision_call(highlighted, prompt, model, max_tokens=500)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"concept": "circle", "confidence": 0.0, "rationale": "parse_fail"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"concept": "circle", "confidence": 0.0, "rationale": "json_fail"}


def icon_agent(state) -> dict:
    if state.get("ablation") == "no_library":
        return {"card_icons": []}

    analysis = state.get("analysis", {})
    cards = analysis.get("cards", [])
    if not cards:
        return {"card_icons": []}

    spec = state.get("design_spec", {})
    accent = spec.get("palette", {}).get("accent", "#D4AF37")
    full = state["image_b64"]
    model = state.get("model", "gpt-4o")
    layout_type = analysis.get("layout_type", "")
    seq = is_sequential_layout(layout_type)
    total_steps = len(cards)

    card_icons: list[dict] = []
    already_chosen: list[str] = []

    # 순차 처리 — 각 카드가 이전 결과를 참조
    for i, card in enumerate(cards):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))
        res = identify_icon_concept(
            full, bbox, i + 1, model=model,
            already_chosen=already_chosen,
            step_idx=i, total_steps=total_steps, is_sequential=seq,
        )
        concept = res.get("concept", "circle")

        # 수렴 방지: 같은 concept 나오면 metaphor chain 에서 fallback
        if concept in already_chosen and seq:
            suggestions = ordinal_concept_suggestions(i, total_steps)
            for s in suggestions:
                if s not in already_chosen:
                    concept = s
                    break

        already_chosen.append(concept)
        card_icons.append({
            "card_idx": i + 1,
            "concept": concept,
            "fa_class": concept_to_fa_class(concept),
            "html_snippet": fa_icon_html(concept, size_rem=1.8, color=accent),
            "confidence": res.get("confidence", 0.5),
        })
    return {"card_icons": card_icons}
