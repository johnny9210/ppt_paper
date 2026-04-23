"""Design Director prompt — 디자인 언어 결정."""
DIRECTOR_PROMPT = """너는 디자인 디렉터다. 이 슬라이드 이미지를 분석해서 **디자인 언어 spec**을 결정하라.
후속 agent(배경/카드/hero/장식)가 이 spec을 참조해서 일관되게 구현한다.

{facts_block}

위 CV 측정값과 이미지를 모두 활용하라.

**DesignSpec JSON**:
```json
{
  "aesthetic_label": "짧은 라벨 (예: 'luxury-dark-gold')",

  "typography": {
    "hero_family": "serif | sans-serif | display | slab",
    "hero_weight": 400-900,
    "hero_style_hint": "uppercase | italic | condensed | normal",
    "body_family": "sans-serif | serif",
    "body_weight": 400-700,
    "letter_spacing_hint": "tight | normal | wide"
  },

  "palette": {
    "bg_primary": "#hex", "bg_secondary": "#hex",
    "accent": "#hex", "accent_soft": "#hex rgba 낮은 채도",
    "frame_color": "rgba(...)",
    "text_bright": "#hex", "text_muted": "rgba(...)"
  },

  "frame_system": {
    "hero_frame": "자연어 1-2줄",
    "card_frame": "자연어 1-2줄",
    "bottom_accent_bar": true | false
  },

  "decorative_motif": {
    "style": "geometric-triangles-circles-hexagons | ambient-glow-only | minimal | neon-lines",
    "density": "sparse | moderate | dense",
    "detected_shapes": ["triangle", "circle"]
  },

  "atmosphere": {
    "has_radial_glow": true | false,
    "glow_origin": "top-left | ...",
    "glow_color": "#hex rgba",
    "background_depth": "flat | subtle-gradient | multi-layer"
  }
}
```

★ CV facts + 이미지 직접 관찰만
★ JSON만 출력"""
