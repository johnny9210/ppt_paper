"""
Metric 4: Layer Ordering Accuracy (LOA)
겹치는 요소들의 앞뒤 순서가 올바른지 측정.

방법:
1. HTML에서 position: absolute/relative + z-index 정보 추출
2. DOM 순서와 z-index로 실제 렌더링 순서 결정
3. (선택적) VLM에게 원본 이미지의 ground truth 순서 질문

DOM 기반 분석 (VLM 없이):
- position: absolute 요소가 z-index 없이 겹치면 → 잠재적 layer collision
- z-index가 명시된 경우 → 의도적 순서 지정 (좋음)
- z-index 없이 absolute 겹침 → 순서 불확실 (나쁨)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from bs4 import BeautifulSoup

from src.utils.html_parser import load_html


@dataclass
class LayerElement:
    """위치가 지정된 HTML 요소."""
    tag: str
    classes: str
    position: str  # absolute, relative, fixed
    z_index: int | None
    has_content: bool  # 텍스트나 자식 요소가 있는지
    dom_order: int  # HTML에서 등장 순서


def extract_positioned_elements(html: str) -> list[LayerElement]:
    """HTML에서 position이 지정된 요소들을 추출."""
    soup = BeautifulSoup(html, 'html.parser')
    elements = []
    dom_idx = 0

    for tag in soup.find_all(True):
        style = tag.get('style', '')

        pos_match = re.search(r'position:\s*(absolute|relative|fixed)', style)
        if not pos_match:
            continue

        position = pos_match.group(1)

        z_match = re.search(r'z-index:\s*(\d+)', style)
        z_index = int(z_match.group(1)) if z_match else None

        has_content = bool(tag.get_text(strip=True)) or bool(tag.find(['img', 'i', 'svg']))

        elements.append(LayerElement(
            tag=tag.name,
            classes=tag.get('class', [''])[0] if tag.get('class') else '',
            position=position,
            z_index=z_index,
            has_content=has_content,
            dom_order=dom_idx,
        ))
        dom_idx += 1

    return elements


def layer_ordering_accuracy(html: str) -> dict:
    """Layer Ordering Accuracy 계산.

    VLM 없이 DOM 구조만으로 분석하는 버전.

    측정하는 것:
    1. z-index 사용률: absolute 요소 중 z-index가 명시된 비율
    2. 잠재적 충돌: absolute 요소끼리 z-index 없이 공존하는 경우
    3. z-index 다양성: 고유한 z-index 값이 몇 개인지

    Returns:
        dict with:
        - z_index_usage_rate: absolute 요소 중 z-index 명시 비율
        - unique_z_levels: 고유한 z-index 값 수
        - absolute_count: position: absolute 요소 수
        - potential_collisions: z-index 없이 겹칠 수 있는 요소 수
        - has_explicit_layering: 명시적 레이어링이 있는지
    """
    elements = extract_positioned_elements(html)

    absolute_elements = [e for e in elements if e.position == 'absolute']
    abs_count = len(absolute_elements)

    if abs_count == 0:
        return {
            "z_index_usage_rate": 0.0,
            "unique_z_levels": 0,
            "absolute_count": 0,
            "potential_collisions": 0,
            "has_explicit_layering": False,
            "elements": [],
        }

    # z-index 사용률
    with_z = [e for e in absolute_elements if e.z_index is not None]
    z_usage_rate = len(with_z) / abs_count

    # 고유한 z-index 값
    z_values = [e.z_index for e in with_z]
    unique_z = len(set(z_values))

    # 잠재적 충돌: absolute인데 z-index 없는 요소
    without_z = [e for e in absolute_elements if e.z_index is None]
    potential_collisions = len(without_z)

    # 명시적 레이어링: 최소 2개 이상의 서로 다른 z-index
    has_explicit = unique_z >= 2

    return {
        "z_index_usage_rate": round(z_usage_rate, 4),
        "unique_z_levels": unique_z,
        "absolute_count": abs_count,
        "potential_collisions": potential_collisions,
        "has_explicit_layering": has_explicit,
        "elements": [
            {
                "tag": e.tag,
                "position": e.position,
                "z_index": e.z_index,
                "has_content": e.has_content,
                "dom_order": e.dom_order,
            }
            for e in absolute_elements[:20]  # 최대 20개만
        ],
    }


def layer_ordering_from_file(html_path: str) -> dict:
    """파일 경로에서 LOA 계산."""
    return layer_ordering_accuracy(load_html(html_path))
