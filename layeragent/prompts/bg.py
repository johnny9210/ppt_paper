"""Background / Atmosphere / Decoration agent prompts."""

BASE_BG_PROMPT = """이 슬라이드 이미지의 **가장 바깥 배경 레이어만** HTML+CSS로 구현하라.

{spec_hint}

범위:
- ✓ 베이스 배경색, 그라디언트 (linear/radial)
- ✗ 글로우·앰비언트 (Atmosphere Agent 담당)
- ✗ 기하 도형 (Decoration Agent 담당)
- ✗ 카드/hero

★ 컨테이너: position:absolute; inset:0; z-index:0;
★ CSS 선택자: .{slide_id}-bg-base
★ palette.bg_primary + bg_secondary 사용
★ <style>과 <div>로만"""


ATMOSPHERE_PROMPT = """이 슬라이드의 **앰비언트 빛 레이어**만 HTML+CSS로 구현하라.

{spec_hint}

범위:
- ✓ radial-gradient 큰 빛 (origin: DesignSpec.atmosphere.glow_origin)
- ✓ 소프트 vignette, 부드러운 색 번짐
- ✗ 기하 도형/선명 라인

★ `filter: blur(N)` 또는 radial-gradient
★ alpha 0.1~0.25 권장
★ 컨테이너: position:absolute; inset:0; z-index:1; pointer-events:none;
★ CSS 선택자: .{slide_id}-atmos
★ <style>과 <div>로만"""


DECORATION_PROMPT = """이 슬라이드의 **기하 장식 도형만** 구현하라.

{spec_hint}

**Analyzer가 찾은 장식**:
```json
{decorations_json}
```

범위:
- ✓ 삼각형·원·육각형·다이아몬드 등
- ✓ DesignSpec.decorative_motif 스타일
- ✗ 배경색·글로우
- motif 'minimal' 이면 빈 결과 OK

★ SVG 또는 clip-path 사용
★ 컨테이너: position:absolute; inset:0; z-index:2; pointer-events:none;
★ CSS 선택자: .{slide_id}-decor
★ <style>과 <div>로만"""
