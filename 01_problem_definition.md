# 논문 방향 (최종 확정)

## 제목
**"What Vision Language Models See but Cannot Code: A Taxonomy of Visual Information Loss in Design-to-Code Generation"**

## 한 문장 요약
VLM은 디자인 이미지의 시각 요소를 정확히 인식하지만, 코드로 변환할 때 체계적으로 시각 정보를 잃어버린다.

---

## 1. 문제 발견 경위

AIDX PPT 생성 시스템을 프로덕션에서 운영하면서 발견:
- Gemini가 생성한 디자인 이미지를 Vision LLM(GPT-4o)이 HTML로 변환
- 변환 결과에서 배경 소실, 아이콘 깨짐, 효과 소실, 계층 충돌 등이 반복 발생
- 이를 막기 위해 시행착오로 13개 완화 규칙을 축적
- 이 규칙들이 존재해야 하는 이유를 체계적으로 분석하면 연구 기여가 됨

## 2. 핵심 관찰

### Pilot 실험 결과 (n=3)

**인식 테스트 (Q: "이 이미지의 계층 구조를 설명해"):**
- 3/3 정확히 인식. Layer 0~7까지 상세 분류.

**생성 테스트 (Q: "이 이미지를 HTML로 변환해"):**
- 배경 일러스트 → 사라짐
- 아이콘 배지 → 깨진 img 태그
- 그림자/글래스모피즘 → 소실
- 요소 겹침 순서 → 틀림
- 기본 텍스트/제목 → 보존됨

**Binary 인식 테스트 (Q: "A가 B 위에 있나?"):**
- 9/9 정확. VLM은 공간 관계를 완벽히 이해.

→ **인식은 되는데 코드에 반영 안 됨 = Perception-Generation Gap**

## 3. 연구 질문

"VLM이 design-to-code 변환에서 어떤 시각 정보를 잃어버리는가?
왜 잃어버리는가? 어떻게 줄일 수 있는가?"

## 4. Design2Code (NAACL 2025)와의 차이

| | Design2Code | 우리 |
|---|---|---|
| 측정 | 전체 시각 유사도 (CLIP, 스크린샷 비교) | **요소별 보존/소실 분석** |
| 분석 깊이 | "점수가 몇 점인가" | **"뭐가, 왜 소실되는가"** |
| 도메인 | 웹페이지 | 프레젠테이션 + 웹 UI + 포스터 |
| 산출물 | 벤치마크 점수 | **Visual Loss Taxonomy + Loss Rate + 완화 규칙** |

## 5. Contributions (예상)

### C1: Visual Loss Taxonomy
VLM design-to-code 변환에서 시각 정보 손실 유형 분류:
- Type A: Background Loss (배경 이미지, 그라디언트 소실)
- Type B: Icon Degradation (아이콘 깨짐, alt text로 대체)
- Type C: Effect Loss (그림자, blur, 글래스모피즘 소실)
- Type D: Layer Collision (요소 겹침 순서 오류)
- Type E: Style Simplification (복잡한 스타일 단순화)

### C2: 정량적 Loss Rate 측정
- 요소 유형별 보존/소실 비율
- VLM별 비교 (GPT-4o, Claude, Gemini)
- 이미지 복잡도별 분석

### C3: Perception-Generation Gap 분석
- VLM은 인식은 하지만 코드 생성에서 실패하는 요소 식별
- "인식 정확도 vs 코드 반영률" 갭 정량화
- 원인 분석 (CSS 표현 한계, 학습 데이터 편향, 프롬프트 의존성)

### C4: 프로덕션 검증된 완화 규칙
- 13개 규칙 × 각각 어떤 Loss Type을 어느 정도 줄이는지
- 규칙 적용 전/후 Loss Rate 비교

## 6. 실험 설계

### 데이터
- 50+ 디자인 이미지
- 3개 도메인: 프레젠테이션, 웹 UI, 포스터
- 복잡도 3단계: 단순, 중간, 복잡

### VLM
- GPT-4o
- Claude (Bedrock)
- Gemini

### 실험 구성
1. 각 이미지 × 각 VLM → 코드 생성
2. 원본 vs 생성 결과 → 요소별 보존/소실 판정
3. Loss Type 분류 + Loss Rate 계산
4. 인식 테스트 (binary 질문) → Perception 정확도
5. 완화 규칙 적용 전/후 비교

### 메트릭
- 요소별 보존율 (보존된 요소 / 원본 요소)
- Loss Type별 발생률
- Perception-Generation Gap (인식 정확도 - 코드 반영률)
- 완화 규칙 효과 (적용 전 Loss Rate - 적용 후 Loss Rate)

## 7. 논문 구조

1. Introduction: Design-to-code가 중요해지고 있지만, VLM이 시각 정보를 체계적으로 잃어버린다
2. Related Work: Design2Code, SlideCoder, VLM spatial reasoning
3. Visual Loss Taxonomy: 5가지 손실 유형 정의
4. Experiments: 50+ 이미지, 3 VLM, 정량적 분석
5. Analysis: 왜 손실이 발생하는가, Perception-Generation Gap
6. Mitigation: 완화 규칙과 그 효과
7. Discussion & Conclusion

## 8. 다음 할 것

### 즉시 (코드 짜기 전에)
1. Visual Loss Taxonomy 5가지 유형을 구체적 예시와 함께 정의
2. 판정 기준 수립: "이 요소가 보존됐다/소실됐다"를 어떻게 판단하는가
3. 50개 디자인 이미지 수집 계획

### 이후
4. 실험 코드 작성
5. 실험 실행
6. 결과 분석
7. 논문 작성
