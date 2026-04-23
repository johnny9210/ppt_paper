"""
Metric 2: Icon Integrity Rate (IIR)
아이콘이 정상적으로 렌더링되었는지 측정. VLM 없이 완전 자동.

정상: FontAwesome, emoji, 유효한 이미지
깨짐: 존재하지 않는 src의 img 태그
빈: 아이콘 스타일 CSS만 있고 내용 없는 컨테이너
"""

from __future__ import annotations

from src.utils.html_parser import parse_icons, load_html


def icon_integrity_rate(html: str) -> dict:
    """Icon Integrity Rate 계산.

    Returns:
        dict with:
        - rate: 0.0 ~ 1.0 (1.0 = 모든 아이콘 정상)
        - proper: 정상 아이콘 수
        - broken: 깨진 아이콘 수
        - empty: 빈 아이콘 컨테이너 수
        - total: 전체 아이콘 요소 수
    """
    info = parse_icons(html)

    return {
        "rate": round(info.integrity_rate, 4),
        "proper": info.proper,
        "broken": info.broken,
        "empty": info.empty,
        "total": info.total,
    }


def icon_integrity_from_file(html_path: str) -> dict:
    """파일 경로에서 IIR 계산."""
    return icon_integrity_rate(load_html(html_path))
