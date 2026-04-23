"""Text Inserter prompt — assembled HTML에 content 텍스트 삽입."""

TEXT_INSERT_PROMPT = """아래 HTML은 슬라이드입니다. Hero와 Card 구조가 완성되어 있습니다.
각 영역의 **빈 div**에 텍스트를 삽입하세요.

[현재 HTML]
```html
{html}
```

[삽입할 콘텐츠]
{content_json}

★★★ 핵심 규칙:
1. 기존 HTML의 CSS/구조는 그대로 유지 (style, class, position 절대 변경 X)
2. 빈 div 안에만 텍스트 삽입
3. 덮는 오버레이 만들지 마세요

★★★ Hero 영역 (.hero-1 등)이 있으면:
- content.hero_value, content.title, content.description 활용
- Hero의 큰 숫자/제목 placeholder를 실제 값으로 교체

★★★ Card 영역 (.card-1 등):
- content.items/steps/metrics/stats/features 순서대로 매핑
- STEP/번호, 이모지, 제목, 설명 배치

★★★ 텍스트 색상은 **배경에 맞게 자연스럽게**:
- Hero 큰 숫자: palette의 accent 사용
- Card 제목: 밝은 대비 색
- Card 설명: 중간 대비 색

★ 전체 HTML 출력, <style>과 <div>만"""
