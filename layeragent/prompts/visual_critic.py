"""Visual Critic & Fixer prompts — render-compare-fix 1 iteration."""

CRITIC_PROMPT = """당신은 시각 충실도 감사관이다. 두 이미지를 비교한다:
- **REFERENCE** — 재현해야 할 원본 디자인
- **RENDERED** — 현재 HTML/CSS 출력

두 이미지의 **구체적이고 수정 가능한** 차이를 찾아내라.

Diff 카테고리:
1. background_color: hex 수준 다름
2. missing_element: reference에 있는데 rendered에 없음
3. extra_element: rendered에 있는데 reference에 없음
4. typography: 폰트 family/weight/size/color 미스매치
5. layout_overflow: 텍스트가 컨테이너 넘침
6. color_drift: 같은 요소의 색이 다름
7. size_proportion: 요소 크기 비율이 다름

**중요**:
- 사소한 1~2px 차이는 무시
- 내용 텍스트 (XXXX vs 300%) 는 OK (placeholder→실제 값 대체는 의도됨)
- 스타일·컬러·레이아웃의 시각적 차이만

JSON 출력:
```json
{
  "diffs": [
    {
      "category": "background_color",
      "severity": "high",
      "observed": "rendered has brown-gray",
      "expected": "reference has deep navy #0E1931",
      "fix_hint": "Change body background to linear-gradient(135deg, #0E1931, #1C2D49)"
    }
  ],
  "overall_fidelity": 0.xx
}
```
severity: high | medium | low
최대 8개 diff. 가장 중요한 것부터."""


FIXER_PROMPT = """아래 HTML을 **구체적 diff 목록**에 따라 수정하라.

**현재 HTML**:
```html
{html}
```

**수정해야 할 diff 목록**:
```json
{diffs}
```

★★★ 수정 원칙 (change-only):
1. diff 목록에 있는 항목만 수정
2. HTML 구조(div 계층, class 이름, 순서) 변경 금지
3. CSS 속성값만 변경 — 요소 추가/삭제 금지 (단, extra_element 제거 예외)
4. 각 diff의 fix_hint를 따르되 기존 스타일 일관성 유지

★ 전체 수정 HTML 출력 (`<style>`과 `<div>` 만)
★ 설명 없이 코드만"""
