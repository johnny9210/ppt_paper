"""End-to-end smoke test — design_10_stats_hero 1개로 pipeline 연결 확인."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


def test_imports():
    from layeragent import LayerAgent, SUPPORTED_ABLATIONS, State
    assert "none" in SUPPORTED_ABLATIONS
    assert "no_style_norm" in SUPPORTED_ABLATIONS
    print("✓ Imports OK")


def test_library_functions():
    """라이브러리 함수 smoke test (외부 API 호출 없음)."""
    from layeragent.libraries.icon_library import concept_to_fa_class, fa_icon_html, shape_html
    from layeragent.libraries.pattern_library import background_pattern, bezier_path

    assert concept_to_fa_class("shield") == "shield-halved"
    assert "<i class=" in fa_icon_html("globe")
    assert "<svg" in shape_html("triangle_outline")
    assert "<svg" in background_pattern("circuit_grid")
    assert "M" in bezier_path((0, 0), (100, 100))
    print("✓ Library functions OK")


def test_cv_extractors():
    """CV 추출기 — 실제 이미지 로드."""
    from layeragent.libraries.cv_extractors import extract_palette_hex
    from layeragent.utils.common import b64_image

    b64 = b64_image("design_10_stats_hero")
    palette = extract_palette_hex(b64, n_colors=3)
    assert len(palette) == 3
    assert all("hex" in p for p in palette)
    print(f"✓ CV extractor OK: {[p['hex'] for p in palette]}")


def test_pipeline_build():
    """LangGraph 컴파일 — 실행 없이 build만."""
    from layeragent import build_pipeline

    pipeline = build_pipeline(ablation="none", use_visual_critic=False)
    assert pipeline is not None

    # Ablation variants
    for ab in ("no_style_norm", "no_text_inserter", "no_cv_facts", "no_designspec", "no_library"):
        pipeline = build_pipeline(ablation=ab, use_visual_critic=False)
        assert pipeline is not None
    print("✓ Pipeline build OK (all ablations)")


if __name__ == "__main__":
    test_imports()
    test_library_functions()
    test_cv_extractors()
    test_pipeline_build()
    print("\n🎉 All smoke tests passed!")
