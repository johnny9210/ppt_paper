"""Icon Specialist Agent — 각 카드의 icon 영역을 보고 개념어 추출.

FontAwesome 라이브러리 검색 전용. SVG path 생성 시도 안 함.
"""
from __future__ import annotations

import json
import re

from .bbox_utils import draw_bbox_on_image
from .icon_library import concept_to_fa_class, fa_icon_html
from src.methods import crop_layer_agent as _la


ICON_CONCEPT_PROMPT = """이 슬라이드 이미지에서 빨간 사각형 **카드 {card_idx}** 내부의 아이콘을 관찰하라.

카드 왼쪽 또는 위쪽에 있는 작은 아이콘(그림/심볼)을 보고, 그것이 **어떤 개념**을 나타내는지 한 단어로 답하라.

유효한 개념 단어 (이 중에서 가장 가까운 것 하나):
- 비즈니스: chart, graph, analytics, data, metric, growth, revenue, dashboard, statistics
- 보안: shield, security, lock, key, verified
- 글로벌: globe, earth, world, network, cloud, server, wifi, broadcast
- 사람: user, people, team, handshake, partnership, customer
- 문서: document, file, folder, archive, clipboard
- 시간: clock, time, schedule, calendar, deadline, alarm
- 커뮤니케이션: mail, message, chat, phone, microphone
- 개발: code, terminal, robot, ai, gear, database
- 디자인: palette, brush, camera, image, star, heart
- 네비: arrow_up, arrow_right, play, refresh, rocket, target, flag
- 건축: building, office, factory, store
- 연구: flask, science, research, atom
- 교통: truck, delivery, ship, plane, car
- 기타: idea, innovation, info, warning, success, gift, award, trophy

JSON으로 출력:
```json
{{
  "concept": "단어 하나",
  "confidence": 0.0~1.0,
  "rationale": "짧은 설명 (왜 그 개념인지)"
}}
```
다른 텍스트 없이 JSON만."""


def identify_icon_concept(image_b64: str, card_bbox: tuple[float, float, float, float],
                           card_idx: int, model: str = "gpt-4o") -> dict:
    """카드의 bbox를 하이라이트한 full image → icon 개념어."""
    highlighted = draw_bbox_on_image(image_b64, card_bbox, color=(255, 0, 0), width=6,
                                      label=f"CARD_{card_idx}")
    prompt = ICON_CONCEPT_PROMPT.format(card_idx=card_idx)
    raw = _la._vision_call(highlighted, prompt, model, max_tokens=500)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"concept": "circle", "confidence": 0.0, "rationale": "parse_fail"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"concept": "circle", "confidence": 0.0, "rationale": "json_fail"}


def icon_agent_node(state) -> dict:
    """각 카드의 icon 개념을 식별해서 FA HTML 조각으로 변환, state에 저장."""
    analysis = state.get("analysis", {})
    cards = analysis.get("cards", [])
    if not cards:
        return {"card_icons": []}

    spec = state.get("design_spec", {})
    accent = spec.get("palette", {}).get("accent", "#D4AF37")
    full = state["image_b64"]
    model = state.get("model", "gpt-4o")

    card_icons: list[dict] = []
    for i, card in enumerate(cards):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))
        res = identify_icon_concept(full, bbox, i + 1, model=model)
        concept = res.get("concept", "circle")
        fa_cls = concept_to_fa_class(concept)
        card_icons.append({
            "card_idx": i + 1,
            "concept": concept,
            "fa_class": fa_cls,
            "html_snippet": fa_icon_html(concept, size_rem=1.8, color=accent),
            "confidence": res.get("confidence", 0.5),
        })
    return {"card_icons": card_icons}
