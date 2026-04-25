"""Ordinal → visual metaphor chain expansion.

Roadmap/timeline 카드가 step_1, step_2, ... 같은 "같은 서수" 레이블을 받으면
Icon Agent가 모두 같은 은유 (주황 원 등) 로 수렴하는 문제를 해결.

아이디어: 순서를 시각적 *이야기* 로 확장.
  step_1 → 'seed' (시작)
  step_2 → 'sprout' (성장)
  step_3 → 'milestone' (중간 목표)
  step_4 → 'rocket' (확장)
  step_5 → 'trophy' (완료)

Card Detail Agent 는 자신의 카드 content 에서 힌트를 얻고, 이 힌트를 Icon Agent 가 받아
해당 metaphor 에 가까운 concept 을 선택.
"""
from __future__ import annotations


# 5단계 roadmap용 기본 chain
STEP_METAPHORS_5: list[tuple[str, list[str]]] = [
    ("start",    ["rocket", "seed", "flag", "play", "lightbulb"]),
    ("growth",   ["arrow_up", "building", "code", "robot", "gear"]),
    ("milestone",["target", "award", "metric", "chart", "globe"]),
    ("expand",   ["network", "people", "shield", "database", "cloud"]),
    ("complete", ["trophy", "verified", "medal", "crown", "star"]),
]

# 4단계용
STEP_METAPHORS_4: list[tuple[str, list[str]]] = [
    ("start",    ["seed", "rocket", "flag"]),
    ("build",    ["code", "gear", "building"]),
    ("scale",    ["network", "growth", "globe"]),
    ("win",      ["trophy", "verified", "award"]),
]

# 3단계용
STEP_METAPHORS_3: list[tuple[str, list[str]]] = [
    ("start",   ["seed", "rocket"]),
    ("process", ["gear", "workflow"]),
    ("end",     ["trophy", "target"]),
]


def ordinal_concept_suggestions(step_idx: int, total_steps: int) -> list[str]:
    """step_idx (0-based) + total_steps → 제안 concept 리스트.

    Icon Agent 가 card content 를 보고 이 중 하나를 고르거나,
    content 에서 더 구체적 단서를 얻으면 무시 가능.
    """
    if total_steps >= 5:
        chain = STEP_METAPHORS_5
    elif total_steps == 4:
        chain = STEP_METAPHORS_4
    elif total_steps <= 3:
        chain = STEP_METAPHORS_3
    else:
        chain = STEP_METAPHORS_5

    # 비례 인덱스 매핑
    prop = step_idx / max(total_steps - 1, 1)
    target_idx = round(prop * (len(chain) - 1))
    target_idx = max(0, min(len(chain) - 1, target_idx))
    _, concepts = chain[target_idx]
    return concepts


def is_sequential_layout(layout_type: str) -> bool:
    """roadmap, timeline, pyramid 등 순서가 있는 레이아웃인가."""
    return (layout_type or "").lower() in {
        "roadmap", "timeline", "pyramid", "horizontal_row",
        "vertical_stack", "pipeline", "steps",
    }
