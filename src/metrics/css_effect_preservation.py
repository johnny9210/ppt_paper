"""
Metric 3: CSS Effect Preservation Score (CEPS)
시각 효과 관련 CSS 속성이 보존되었는지 측정. VLM 없이 완전 자동.

box-shadow, gradient, opacity, filter, backdrop-filter, transform 등
시각적 풍부함을 만드는 CSS 속성의 보존율.
"""

from __future__ import annotations

from src.utils.html_parser import parse_css_properties, load_html


def css_effect_preservation_score(
    reference_html: str,
    generated_html: str,
) -> dict:
    """CSS Effect Preservation Score 계산.

    reference는 원본 (AIDX PPT with rules) 또는 디자인 의도를 가진 코드.
    generated는 VLM이 생성한 코드.

    Returns:
        dict with:
        - score: 0.0 ~ 1.0 (1.0 = 모든 효과 보존)
        - reference_effects: 참조 코드의 효과 속성 수
        - generated_effects: 생성 코드의 효과 속성 수
        - detail: 속성별 비교
    """
    ref_css = parse_css_properties(reference_html)
    gen_css = parse_css_properties(generated_html)

    detail = {
        "box_shadow": {"ref": len(ref_css.box_shadows), "gen": len(gen_css.box_shadows)},
        "gradient": {"ref": len(ref_css.gradients), "gen": len(gen_css.gradients)},
        "opacity": {"ref": len(ref_css.opacities), "gen": len(gen_css.opacities)},
        "filter": {"ref": len(ref_css.filters), "gen": len(gen_css.filters)},
        "backdrop_filter": {"ref": len(ref_css.backdrop_filters), "gen": len(gen_css.backdrop_filters)},
        "transform": {"ref": len(ref_css.transforms), "gen": len(gen_css.transforms)},
        "border_radius": {"ref": len(ref_css.border_radii), "gen": len(gen_css.border_radii)},
    }

    ref_total = ref_css.effect_count
    gen_total = gen_css.effect_count

    if ref_total == 0:
        score = 1.0  # 참조에 효과가 없으면 loss 불가
    else:
        score = min(1.0, gen_total / ref_total)

    return {
        "score": round(score, 4),
        "reference_effects": ref_total,
        "generated_effects": gen_total,
        "detail": detail,
    }


def css_effect_from_files(reference_path: str, generated_path: str) -> dict:
    """파일 경로에서 CEPS 계산."""
    return css_effect_preservation_score(
        load_html(reference_path),
        load_html(generated_path),
    )


def css_richness(html: str) -> dict:
    """CSS Richness — reference 없이 CSS 효과 속성 절대 개수 측정.

    Returns:
        dict with:
        - total_effects: 전체 효과 속성 수
        - detail: 카테고리별 개수
        - unique_colors: 고유 색상 수 (rgba/hex)
    """
    css_props = parse_css_properties(html)

    detail = {
        "box_shadow": len(css_props.box_shadows),
        "gradient": len(css_props.gradients),
        "opacity": len(css_props.opacities),
        "filter": len(css_props.filters),
        "backdrop_filter": len(css_props.backdrop_filters),
        "transform": len(css_props.transforms),
        "border_radius": len(css_props.border_radii),
    }

    # 고유 색상 수
    import re
    colors = set()
    for match in re.finditer(r'(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))', html):
        colors.add(match.group(0).lower())

    return {
        "total_effects": css_props.effect_count,
        "detail": detail,
        "unique_colors": len(colors),
    }
