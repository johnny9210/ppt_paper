"""Icon concept identification prompt (for FontAwesome library lookup)."""

ICON_CONCEPT_PROMPT = """이 슬라이드 이미지에서 빨간 사각형 **카드 {card_idx}** 내부의 아이콘을 관찰하라.

카드 왼쪽 또는 위쪽 작은 아이콘을 보고, 어떤 **개념**을 나타내는지 한 단어로 답하라.

유효 개념:
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

JSON:
```json
{{
  "concept": "단어 하나",
  "confidence": 0.0~1.0,
  "rationale": "짧은 설명"
}}
```
JSON만, 설명 없이."""
