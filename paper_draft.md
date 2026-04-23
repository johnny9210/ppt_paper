# LayerAgent: Vision-Grounded Layer Decomposition for Design-to-Code Presentation Generation

*LayerAgent: 디자인-투-코드 프레젠테이션 생성을 위한 비전 기반 레이어 분해 멀티에이전트 프레임워크*

---

## 초록 (Abstract)

프레젠테이션 슬라이드는 배경·카드·텍스트·아이콘이 z축으로 겹치는 본질적으로 **계층적(layered)** 구조를 갖는다. 그러나 현재의 Vision Language Model(VLM) 기반 디자인-투-코드 시스템은 이 계층 구조를 **단일 평면(flat) 토큰 시퀀스**로 생성하여, 체계적인 시각 정보 손실을 일으킨다. 본 논문은 이 구조적 불일치를 분석하고 해결하는 두 가지 기여를 제시한다.

첫째, 프로덕션 환경에서 18개월간 관측한 시각 정보 손실을 5가지 유형으로 분류하고(배경 소실 43%, CSS 효과 소실 84%, 계층 충돌 100%), VLM이 계층 구조를 자연어로 100% 정확히 기술하면서도 코드(`z-index`)로는 0% 표현하는 **지각-생성 간극(Perception-Generation Gap)**을 실증한다.

둘째, 이 간극을 해소하기 위한 **LayerAgent** 프레임워크를 제안한다. LayerAgent는 LangGraph 기반 멀티에이전트 파이프라인으로, 슬라이드 생성을 4개 레이어(Background, Cards, Content, Icons)로 분해하고, 핵심적인 비대칭 설계를 적용한다: **스타일 생성 에이전트(BG, Cards)는 디자인 이미지를 직접 보고(Vision-Grounded)** 시각 디테일을 재현하고, **배치 에이전트(Content, Icons)는 이미지 없이 좌표만으로(Coordinate-Guided)** 요소를 정확히 배치한다. Cards Agent가 출력하는 bounding box 좌표가 LangGraph state를 통해 Content/Icons Agent에 전달되어 카드-텍스트 정렬을 보장한다.

10종의 다양한 레이아웃(timeline, dashboard, hub-spoke, pyramid 등)에 대한 5가지 방법의 공정 비교에서, flat 생성 방법(Baseline, Visual CoT, CoT+H-RAG)은 평균 LOA=0.00~0.30으로 계층을 거의 생성하지 않는 반면, LayerAgent는 LOA=0.95로 4-level 계층을 안정적으로 명시한다. CSS 효과는 Baseline(2.8) 대비 4.8배(13.3), 고유 색상 수는 2.9배(20.3 vs 6.9) 풍부하다. 특히 패턴 지식 주입(H-RAG)은 CSS를 높이지만 콘텐츠의 74%를 소실(CCR=0.26)하는 반면, 레이어 분해는 CCR과 LOA를 동시에 해결함을 실증한다.

**키워드**: Layer Decomposition, Multi-Agent, Design-to-Code, Vision Language Models, Presentation Generation, Coordinate Passing, Asymmetric Vision

---

## 1. 서론 (Introduction)

### 1.1 슬라이드는 계층이다

프레젠테이션 슬라이드는 포스터나 웹페이지와 달리, 명확한 **z축 계층 구조**를 갖는다. 하나의 슬라이드 안에서:
- **Layer 0 (Background)**: 그라디언트, 패턴, 장식 도형
- **Layer 1 (Cards)**: 글래스모피즘 카드, 컨테이너, 프레임
- **Layer 2 (Content)**: 제목, 본문, 태그, 메트릭
- **Layer 3 (Icons)**: 아이콘 배지, 장식 라인, 글로우 노드

이 네 계층이 정확한 z-index와 좌표로 겹쳐야 의도된 디자인이 구현된다. 텍스트가 카드 안에, 아이콘이 카드 위에, 카드가 배경 앞에 있어야 한다.

### 1.2 VLM은 평면적으로 생성한다

그러나 VLM 기반 디자인-투-코드 시스템은 이 계층 구조를 인식하지 못한 채, HTML/CSS를 **단일 자기회귀 토큰 시퀀스**로 생성한다. `<div>` 태그가 순서대로 나열되고, `z-index`는 사용되지 않으며, 요소 간 공간 관계는 DOM 순서에 암묵적으로 의존한다. 결과적으로:

- 배경 그라디언트가 단색으로 단순화된다 (43% 발생)
- CSS 효과(shadow, blur, transform)가 소실된다 (84% 발생)
- 텍스트가 카드 밖에 나타나거나 아이콘이 카드 뒤로 숨는다 (계층 충돌)
- `z-index`가 단 한 번도 사용되지 않는다 (0% 생성률)

저자들은 이러한 현상을 상용 엔터프라이즈 플랫폼에서 18개월간 AI 프레젠테이션 생성 기능을 운영하면서 체계적으로 관측하였다. 흥미로운 점은, 동일한 VLM(GPT-4o)에게 "이 이미지의 계층 구조를 설명해라"라고 물으면 5~7개 레이어를 정확히 기술한다는 것이다. **VLM은 계층을 완벽히 인식하지만, 코드로 표현하지 못한다** — 이것이 우리가 명명하는 **지각-생성 간극(Perception-Generation Gap)**이다.

### 1.3 핵심 통찰: 분해와 비대칭

본 논문의 핵심 통찰은 세 가지이다:

1. **레이어 분해**: 하나의 VLM에게 전체 슬라이드를 맡기면 인지 부하로 계층이 무너진다. 4개 전문 에이전트로 분해하면 각자 맡은 레이어를 잘 처리한다.

2. **좌표 기반 통신**: 에이전트 간에 HTML을 전달하면 truncation과 해석 오류가 발생한다. 대신 Cards Agent가 **bounding box 좌표(JSON)**를 출력하고, Content/Icons Agent가 이 좌표를 받아 요소를 정확히 배치한다.

3. **비대칭 정보 제공**: 스타일을 만드는 에이전트(BG, Cards)에는 디자인 이미지를 제공하여 시각 디테일을 재현하고, 배치하는 에이전트(Content, Icons)에는 좌표만 제공하여 정확한 위치 정렬을 보장한다.

### 1.4 기여 (Contributions)

1. **지각-생성 간극의 실증과 시각 손실 분류 체계** (§3, §4): VLM이 계층을 100% 인식하면서 코드로 0% 표현하는 간극을 정량 증명하고, 프로덕션 관측에 기반한 5가지 손실 유형을 정의한다.

2. **LayerAgent 프레임워크** (§5): LangGraph 기반 레이어 분해 멀티에이전트 파이프라인. Vision-Grounded 스타일 생성(Stage 1)과 Coordinate-Guided 배치(Stage 2)를 결합하고, Cards Agent가 출력한 bounding box 좌표를 Content/Icons Agent에 전달하여 카드-텍스트 정렬을 보장한다.

3. **체계적 비교 실험과 요소 수준 메트릭** (§6): 5가지 방법의 단계적 비교를 통해 각 구성요소의 기여를 분리 측정한다. 이를 위해 CCR(Content Completeness Rate), LOA(Layer Ordering Accuracy), CSS Richness, IIR(Icon Integrity Rate) 4종의 reference-free, deterministic 메트릭을 설계한다.

---

## 2. 관련 연구 (Related Work)

### 2.1 디자인-투-코드 생성

Design2Code(Si et al., 2024)는 웹페이지 스크린샷-투-HTML 벤치마크를, DCGen(FSE 2025)은 분할정복 접근을, ScreenCoder(2025)는 인식·계획·생성의 3단계 에이전트 파이프라인을 제안하였다. LaTCoder(KDD 2025)는 레이아웃을 먼저 생성하는 접근을 채택하였다. 이들은 공통적으로 **단일 모델 또는 단일 에이전트**가 전체 페이지를 한 번에 생성하는 구조이며, 출력의 계층적 구조를 명시적으로 다루지 않는다.

### 2.2 프레젠테이션 생성 시스템

PPTAgent(Zheng et al., 2025)는 편집 기반 접근을, PreGenie(Xu et al., 2025)는 코드 리뷰·페이지 리뷰 이중 루프를, SlideCoder(Tang et al., 2025)는 계층적 RAG를 결합하였다. AutoPresent(Ge et al., 2025)는 구조화된 비주얼 설계 원칙을 제시하였다. 이들 중 **슬라이드의 z축 계층 구조를 명시적으로 분해하여 생성하는 접근은 없다**. 본 연구는 이 공백을 채운다.

### 2.3 멀티에이전트 코드 생성

최근 LLM 기반 멀티에이전트 시스템이 활발히 연구되고 있다. MetaGPT(Hong et al., 2023)는 소프트웨어 엔지니어링 역할(PM→아키텍트→개발자→QA)로 agent를 분담하고, ChatDev(Qian et al., 2023)는 대화 기반 협업을, CAMEL(Li et al., 2023)은 역할극 기반 통신을 제안하였다. 이들의 agent 역할 분담 기준은 **소프트웨어 개발 프로세스**(설계→구현→테스트)이다.

본 연구는 두 가지 점에서 다르다. 첫째, agent 역할을 개발 프로세스가 아닌 **시각 디자인의 z축 계층 구조**(배경→카드→텍스트→아이콘)로 분담한다. 이는 출력물의 물리적 구조가 agent 아키텍처를 결정하는 접근이다. 둘째, agent 간 통신을 자연어나 코드가 아닌 **구조화된 좌표 JSON**(bounding box)으로 수행한다. 기존 시스템에서 agent가 코드를 주고받으면 truncation, 해석 오류, 컨텍스트 오염이 발생하는데, 좌표 JSON은 타입이 고정되어 이러한 문제가 없다.

### 2.4 디자인-투-코드 평가

기존 평가는 전역 유사도(CLIP, SSIM), 구조 매칭(Design2Code의 Block-Match, SlidesBench의 element-matching), 속성 수준(WebRenderBench의 SDA)으로 분류된다. 그러나 이들은 (i) **콘텐츠가 실제로 렌더링되었는가**(텍스트가 HTML에 있지만 겹쳐서 안 보이는 경우를 구분 못함), (ii) **z-index 계층이 명시되었는가**, (iii) **CSS 효과의 절대적 풍부성**을 측정하지 못한다. 특히 SSIM/CLIP은 디자인 템플릿(텍스트 없음)을 reference로 비교하면, 텍스트를 올바르게 추가한 method가 오히려 낮은 점수를 받는 역설이 발생한다. 본 연구의 CCR·LOA·CSS Richness·IIR은 이 공백을 reference-free, deterministic 방식으로 채운다.

---

## 3. 시각 정보 손실 분류 체계 (Visual Loss Taxonomy)

프로덕션 운영 18개월간의 관측과 13개 완화 규칙의 분석을 통해 5가지 반복적 손실 유형을 도출하였다. 본 절의 관측 빈도는 프로덕션 환경의 3개 주제 18장 슬라이드 파일럿 분석에서 도출한 수치이다.

### 3.1 왜 손실이 발생하는가: 구조적 불일치

PPT 슬라이드의 시각 구조는 **레이어 스택**이다:

```
z=30~39: Icons (아이콘 배지, 장식 라인, 글로우)
z=20~29: Content (제목, 본문, 태그)
z=10~19: Cards (글래스모피즘 카드, 컨테이너)
z=0~9:   Background (그라디언트, 패턴, 장식 도형)
```

그러나 VLM이 생성하는 HTML은 **순차적 DOM 트리**이다:
```html
<div>배경</div>
<div>카드<div>텍스트</div><div>아이콘</div></div>
```

이 구조적 불일치가 5가지 손실의 근본 원인이다.

### 3.2 다섯 가지 손실 유형

| 유형 | 손실 대상 | 원인 | 관측 빈도 |
|---|---|---|:---:|
| **A: 배경 소실** | 복합 그라디언트, 패턴, 장식 도형 | VLM이 배경을 "장식"으로 간주해 단순화 | 43% |
| **B: 아이콘 퇴화** | 아이콘 배지 → 깨진 img 태그 | 아이콘 자산을 생성할 수 없어 가상 URL 환각 | 30-40% |
| **C: 효과 소실** | box-shadow, backdrop-filter, transform | 복합 CSS 파라미터 조합이 학습 데이터에서 희소 | **84%** |
| **D: 계층 충돌** | z-index 미사용, 요소 겹침 순서 오류 | 자기회귀 생성이 순차적 DOM에 의존 | **100%** |
| **E: 스타일 단순화** | 정밀 border-radius, 간격, 색조 | 중앙값 회귀 경향 | 80-94% |

**Type A (배경 소실).** 원본의 다중 그라디언트 배경(예: linear-gradient + radial-gradient 글로우 2~3개 + 도트 패턴)이 `background: #0F172A` 같은 단색으로 대체된다. VLM은 전경 콘텐츠에 주의를 집중하고 배경을 부차화하는 경향이 있다. 프로덕션에서 topic2(다크 테마)의 BPS가 0.17로 최악을 기록한 것이 이를 뒷받침한다.

**Type B (아이콘 퇴화).** VLM은 "아이콘이 있다"를 인식하지만 재현할 수 없어, 존재하지 않는 `shield.png` 같은 가상 URL을 생성하거나 CSS `::before`로 도형을 그리려 시도한다. 이는 LLM 환각의 시각 버전이다. 프로덕션에서 "FontAwesome 또는 이모지만 허용"이라는 규칙을 도입하여 IIR=1.00으로 해결하였다.

**Type C (효과 소실).** `backdrop-filter: blur(20px)`, 다중 `box-shadow`, `transform: rotate()` 등 고급 CSS 효과가 누락된다. 이들은 정확한 파라미터 조합이 필요하고(blur 값, rgba 알파, offset 등), 부분만 생성하면 효과가 전혀 나타나지 않는 "all-or-nothing" 특성을 갖는다. 실험에서 gradient 손실률 98%, opacity 손실률 100%로 가장 심각하다.

**Type D (계층 충돌).** 본 연구의 핵심 관측이다. VLM은 HTML을 순차적으로 생성하면서 DOM 순서에만 의존하고, 명시적 `z-index`를 **단 한 번도 사용하지 않는다** (0/3 슬라이드, §4 실험). 이로 인해 텍스트가 카드 뒤로 숨거나 아이콘이 배경 아래로 밀리는 충돌이 발생한다. 이것이 "flat 생성 → 계층 붕괴"의 직접적 증거이며, LayerAgent가 해결하는 핵심 문제이다.

**Type E (스타일 단순화).** 디자이너가 의도한 정밀 스타일(16px 코너, 4px 액센트 바, `0 20px 40px -8px` 그림자)이 기본값(8px 코너, 그림자 없음, 균등 패딩)으로 평균화된다. 원본 119~220개 CSS 속성이 생성 코드에서 13~25개로 80~94% 감소한다.

---

## 4. 지각-생성 간극 (The Perception-Generation Gap)

### 4.1 실험 설계

동일한 GPT-4o에 같은 디자인 이미지를 두 가지 방식으로 제시한다:
- **지각 테스트**: "이 이미지의 계층 구조를 설명해라" (이진 공간 관계 질문 9개)
- **생성 테스트**: "이 이미지를 HTML/CSS로 변환해라"

### 4.2 결과

| 측정 | 지각 테스트 | 생성 테스트 |
|---|:---:|:---:|
| 공간 관계 정확도 | **100%** (9/9) | — |
| 계층 기술 정확도 | **5~7개 레이어 정확 기술** | — |
| z-index 사용 | — | **0건** |
| CSS 효과 보존 (CEPS) | — | **0.16** |
| 배경 보존 (BPS) | — | **0.57** |

**VLM은 계층을 완벽히 인식하지만 코드로 표현하지 못한다.** 이것은 "시각 이해 부족"이 아니라 "**계층 구조를 flat 토큰 시퀀스로 번역하는 능력의 부족**"이다.

### 4.3 평가 메트릭

지각-생성 간극과 LayerAgent의 효과를 측정하기 위해, 논문의 각 claim에 1:1 대응하는 4가지 reference-free 메트릭을 설계한다:

- **CCR** (Content Completeness Rate): 입력 콘텐츠 텍스트가 생성된 HTML에 존재하는 비율. 문자열 매칭 기반으로 완전 deterministic하며, "콘텐츠가 소실되었는가"를 직접 측정한다.
- **LOA** (Layer Ordering Accuracy): position:absolute 요소 중 z-index가 명시된 비율 + 고유 z-index 레벨 수. "계층 구조가 코드에 표현되었는가"를 측정한다.
- **CSS Richness**: box-shadow, gradient, opacity, filter, backdrop-filter, transform 등 7개 CSS 효과 속성의 절대 개수. 원본 디자인 이미지의 복합 시각 효과(그라디언트, 글로우, 글래스모피즘 등)를 재현하기 위해 필요한 CSS 속성의 양을 proxy로 측정한다. CSS 속성 수가 시각 품질과 직접 등치되지는 않으나, 원본이 다수의 효과를 포함하는 경우 높은 CSS Richness는 디자인 충실도(visual fidelity)의 대리 지표로 기능한다.
- **IIR** (Icon Integrity Rate): 아이콘 요소를 proper(FontAwesome/이모지), broken(존재하지 않는 img src), empty(내용 없음)로 분류한 정상 비율.

4개 메트릭 모두 **reference-free이고 deterministic**이다. 기존의 SSIM/CLIP은 reference 이미지(디자인 템플릿)와 비교하는 구조인데, 디자인 템플릿에는 텍스트가 없으므로 텍스트를 올바르게 추가한 method가 오히려 낮은 점수를 받는 역설이 발생한다. 이것이 CCR 같은 요소 수준 메트릭이 필요한 근본적 이유이다.

---

## 5. LayerAgent: 레이어 분해 멀티에이전트 프레임워크

### 5.1 설계 원칙

지각-생성 간극의 근본 원인이 "flat 생성"이라면, 해법은 **생성 과정 자체를 계층적으로 분해**하는 것이다. 세 가지 설계 원칙:

1. **레이어별 전문화**: 각 에이전트가 하나의 z-index 범위만 담당하여 인지 부하를 줄인다.
2. **좌표 기반 통신**: 에이전트 간에 HTML이 아닌 bounding box JSON을 전달하여 위치 정렬을 보장한다.
3. **비대칭 Vision**: 스타일 에이전트는 이미지를 보고, 배치 에이전트는 이미지 없이 좌표만 따른다.

### 5.2 아키텍처

```
                    ┌─────────────────────┐
                    │  Visual CoT Analyzer │  이미지 → 레이어별 좌표 분석
                    │  (Vision, gpt-4o)    │
                    └──────────┬──────────┘
                               │ analysis (텍스트)
                    ┌──────────┴──────────┐
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
Stage 1  │ Background Agent │  │   Cards Agent    │
(병렬)   │ Vision-Grounded  │  │ Vision-Grounded  │
         │ z-index: 0~9     │  │ z-index: 10~19   │
         │ → bg_html        │  │ → cards_html     │
         └────────┬─────────┘  │ → card_bboxes[]  │
                  │            └────────┬─────────┘
                  │                     │ card_bboxes (JSON)
                  │          ┌──────────┴──────────┐
                  │          ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
Stage 2  │  Content Agent   │  │   Icons Agent    │
(병렬)   │ Coordinate-Guided│  │ Coordinate-Guided│
         │ Text-only (no img)│ │ Text-only (no img)│
         │ z-index: 20~29   │  │ z-index: 30~39   │
         └────────┬─────────┘  └────────┬─────────┘
                  │                     │
                  └──────────┬──────────┘
                             ▼
                    ┌─────────────────┐
                    │    Assembler    │  기계적 z-index 합침
                    └─────────────────┘
```

LangGraph의 StateGraph로 구현되며, Stage 1과 Stage 2는 각각 병렬 실행된다. 총 5개 에이전트 + 1 Assembler로 구성. LangGraph는 구현 편의를 위한 선택이며, 본 연구의 핵심 기여는 특정 프레임워크가 아닌 설계 원칙(레이어 분해, 좌표 기반 통신, 비대칭 Vision)에 있다. 동일한 설계를 순차적 API 호출과 딕셔너리 전달로도 구현할 수 있다.

### 5.3 Visual CoT Analyzer

디자인 이미지를 입력받아 4개 레이어로 분해 분석한다. 각 요소의 위치를 슬라이드(1280×720px) 대비 % 단위로 출력한다. 이 분석 결과가 모든 하위 에이전트의 공통 입력이 된다.

### 5.4 Vision-Grounded 에이전트 (Stage 1)

**Background Agent**와 **Cards Agent**는 **디자인 이미지를 직접 보면서(Vision)** HTML/CSS를 생성한다. 이미지를 보는 이유는 미묘한 그라디언트 색상, 글래스모피즘 투명도, 장식 도형의 정확한 위치 등 **텍스트 분석만으로는 전달할 수 없는 시각 디테일**을 재현하기 위해서이다.

Cards Agent는 HTML 출력과 함께 **bounding box 좌표를 JSON으로 출력**한다:
```json
[
  {"card_id": "card_1", "left": 5, "top": 15, "width": 28, "height": 75,
   "padding": 3, "content_area": {"left": 8, "top": 18, "width": 22, "height": 69}}
]
```

`content_area`는 padding을 뺀 실제 콘텐츠 배치 가능 영역이다. 이 좌표가 LangGraph state를 통해 Stage 2 에이전트에 자동 전달된다.

### 5.5 Coordinate-Guided 에이전트 (Stage 2)

**Content Agent**와 **Icons Agent**는 **이미지 없이(Text-only)** bounding box 좌표만으로 요소를 배치한다. 스타일(그라디언트 색상, 카드 투명도)은 시각 정보에서만 얻을 수 있으므로 Stage 1 에이전트에는 이미지가 필요하지만, 위치(텍스트가 카드 안에 있어야 함)는 좌표에서 결정되므로 Stage 2 에이전트에는 좌표만 제공한다.

부수적으로, Content/Icons Agent에 디자인 이미지를 추가 제공하는 변형(F-vision)을 실험한 결과, CCR이 오히려 하락(1.00→0.93)하였다. VLM이 bbox 좌표보다 이미지 해석을 우선하여 일부 콘텐츠를 누락하기 때문이다. 이 관찰에 기반하여 LayerAgent는 배치 에이전트에 이미지를 제공하지 않는 설계를 채택하였다.

### 5.6 슬라이드 타입별 적응

콘텐츠 구조를 분석하여 Cards Agent에 힌트를 제공한다:
- **cover**: 카드 없이 제목+부제만. bbox = 빈 배열
- **three_column**: 최소 3개 bbox 필요 (컬럼 = 카드)
- **comparison**: 최소 2개 bbox 필요 (좌/우)
- **table_of_contents**: 항목 수만큼 bbox

---

## 6. 실험 (Experiments)

### 6.1 실험 설정

**데이터.** Gemini 2.5 이미지 생성 모델로 10종의 다양한 슬라이드 레이아웃을 생성하였다. 각 디자인은 프로덕션 환경에서 관찰되는 실제 레이아웃 유형을 반영하며, 복잡도와 구조가 상이하다:

| # | 레이아웃 | 구조 | 복잡도 |
|---|---|---|:---:|
| 01 | Timeline | 4노드 + 카드 + 네온 라인 | 높음 |
| 02 | Dashboard | 3 메트릭 카드 + 차트 영역 | 중간 |
| 03 | Comparison Split | 좌우 분할 + VS 배지 + 8카드 | 높음 |
| 04 | Pyramid | 3단계 계층 (1-2-3 카드) | 중간 |
| 05 | Hub & Spoke | 중앙 허브 + 6 연결 카드 | 높음 |
| 06 | Before/After | 좌우 변환 + 색상 전환 | 중간 |
| 07 | Feature Grid | 2×3 그리드 + 아이콘 + 태그 | 중간 |
| 08 | Roadmap | 5 페이즈 교차 배치 | 높음 |
| 09 | Layered Stack | 4층 겹침 + 레인보우 | 매우 높음 |
| 10 | Stats Hero | 히어로 넘버 + 4 스탯 카드 | 중간 |

모든 디자인은 다크 테마, 글래스모피즘, 네온 글로우 등 복합 시각 효과를 포함한다.

**공정 비교.** 모든 method에 동일한 콘텐츠 데이터를 제공한다 (fair comparison). 기존 design-to-code 연구의 method(A, B, C)는 이미지만 입력하는 것이 일반적이나, 본 실험에서는 텍스트 콘텐츠도 함께 제공하여 "콘텐츠를 줘도 flat 생성에서는 구조가 무너지는가"를 검증한다.

**비교 방법:**

| Method | 접근 방식 | 분석 | 패턴지식 | 레이어분해 | 좌표공유 | Vision |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **A. Baseline** | 단일 프롬프트 | - | - | - | - | - |
| **B. Visual CoT** | 분석 → 생성 (2단계) | ✓ | - | - | - | - |
| **C. CoT + H-RAG** | 분석 → CSS 패턴 검색 → 생성 | ✓ | ✓ | - | - | - |
| **E. Layer Agents** | 4 agent 독립 생성 | ✓ | - | ✓ | - | - |
| **F. LayerAgent (ours)** | LangGraph 좌표전달 + 비대칭 Vision | ✓ | - | ✓ | ✓ | ✓ |

**평가 메트릭.** 논문의 claim에 1:1 대응하는 4개 primary 메트릭:

| 메트릭 | 측정 대상 | Claim |
|---|---|---|
| **CCR** (Content Completeness Rate) | 입력 콘텐츠가 HTML에 존재하는 비율 | flat 생성은 콘텐츠를 소실시킨다 |
| **LOA** (Layer Ordering Accuracy) | z-index 사용률 + 고유 레벨 수 | 레이어 분해로 계층 구조가 생긴다 |
| **CSS Richness** | CSS 효과 속성 절대 개수 | Vision-Grounding이 시각 품질을 높인다 |
| **IIR** (Icon Integrity Rate) | 아이콘 proper/broken/empty 분류 | 아이콘이 정상 렌더링된다 |

**모델.** GPT-4o-2024-08-06, LangGraph 1.0.5, Playwright 1.58. 모든 method는 동일 모델, 동일 이미지, 동일 콘텐츠로 실행.

### 6.2 메인 결과

#### Table 1: 10개 디자인 평균

| Method | CCR ↑ | LOA ↑ | CSS Richness ↑ | Colors ↑ | Time |
|---|:---:|:---:|:---:|:---:|:---:|
| A. Baseline | 0.80 | 0.00 | 2.8 | 6.9 | 8s |
| B. Visual CoT | 0.50 | 0.30 | 7.1 | 7.0 | 14s |
| C. CoT + H-RAG | 0.26 | 0.13 | 10.3 | 9.2 | 15s |
| E. Layer Agents | **1.00** | **1.00** | 5.0 | 9.1 | 22s |
| **F. LayerAgent (ours)** | 0.85 | **0.95** | **13.3** | **20.3** | 60s |

*N=10 디자인. CCR, LOA, CSS Richness는 높을수록 좋음. 모든 method에 동일 콘텐츠 제공 (fair comparison).*

\* 모든 method에서 IIR=1.00 (FontAwesome/이모지 사용 지시에 의함). 규칙 미적용 시 30–40% 퇴화율이 관측됨(§3.2).

### 6.3 분석

#### 6.3.1 LOA: flat vs layered의 이진 분리

가장 명확한 결과는 **LOA에서의 이진 분리**이다:
- **A = 0.00**: 10개 디자인 전체에서 z-index를 **단 한 번도** 사용하지 않음
- **B = 0.30, C = 0.13**: 분석 단계에서 계층을 언급하면 간헐적으로 z-index를 생성하나 비일관적
- **E = 1.00, F = 0.95**: 레이어 분해 시 4-level 계층이 **거의 완벽히** 명시됨

이는 §4에서 실증한 지각-생성 간극의 대규모 확인이다. **분석(B), 패턴 주입(C) 등 단일 VLM 내부의 어떤 개입도 z-index 생성을 안정적으로 유도하지 못한다.** 레이어 분해(E, F)만이 계층 구조를 보장한다.

#### 6.3.2 H-RAG의 역설: CSS는 올리고 콘텐츠는 해친다

Method C(CoT + H-RAG)는 CSS Richness에서 10.3으로 B(7.1)보다 높지만, CCR에서 **0.26으로 전체 최악**이다. CSS 패턴 지식을 주입하면 VLM이 시각 효과 생성에 집중하여 **콘텐츠 배치를 소홀히** 한다. 이는 "지식 주입이 항상 긍정적인가?"에 대한 반례이며, 레이어 분해(E, F)가 CSS와 콘텐츠를 **분리된 에이전트**로 처리함으로써 이 trade-off를 해소함을 보인다.

#### 6.3.3 CSS Richness와 Colors: Vision-Grounding의 효과

CSS Richness에서 LayerAgent(F)가 전 방법을 압도한다:
- F = **13.3** vs E = 5.0 (**2.7배**), C = 10.3, A = 2.8 (**4.8배**)
- Colors: F = **20.3** vs 2위 C = 9.2 (**2.2배**)

E와 F는 동일한 레이어 분해 구조인데 CSS가 2.7배 차이나는 이유는 **Vision-Grounding**이다. F의 Background/Cards Agent는 디자인 이미지를 직접 보면서 그라디언트, 글로우, 글래스모피즘의 정확한 색상과 파라미터를 재현하지만, E는 텍스트 분석만으로 생성하여 시각 디테일을 놓친다.

#### 6.3.4 Ablation: 각 구성요소의 기여 (10개 평균)

| 전환 | CCR | LOA | CSS | 해석 |
|---|:---:|:---:|:---:|---|
| A→B (분석 추가) | 0.80→0.50 | 0.00→0.30 | 2.8→7.1 | CSS 개선, LOA 약간 개선, CCR 하락 |
| B→C (패턴지식 추가) | 0.50→**0.26** | 0.30→0.13 | 7.1→10.3 | CSS 추가 개선, **CCR 최악** |
| A→E (레이어 분해) | 0.80→**1.00** | 0.00→**1.00** | 2.8→5.0 | **LOA 완전 해결, CCR 완전 해결** |
| E→F (좌표공유+Vision) | 1.00→0.85 | 1.00→0.95 | 5.0→**13.3** | **CSS 2.7배, CCR 약간 하락** |

핵심 발견: **패턴 지식(C)은 CSS를 올리지만 LOA를 해결하지 못하고 CCR을 해친다. 구조적 분해(E)는 LOA와 CCR을 동시에 해결한다.** 레이어 분해가 계층 구조를 안정적으로 보장하는 유일한 접근이다.

#### 6.3.5 E vs F: 좌표 공유의 필요성

Method E는 CCR=1.00으로 콘텐츠는 완전하지만, 시각적으로는 **텍스트가 카드 밖으로 흘러나오는** 치명적 결함을 보인다 (Figure 참조). 4개 agent가 독립적으로 좌표를 추정하기 때문에 Cards Agent가 만든 카드와 Content Agent가 배치한 텍스트의 위치가 불일치한다. LayerAgent(F)에서 Cards Agent가 bounding box 좌표를 JSON으로 출력하고 Content Agent가 이를 받아 사용하면서 이 문제가 해결된다.

#### 6.3.6 CCR의 역설: 왜 F(0.85)가 E(1.00)보다 낮은가

F의 Content Agent는 Cards Agent가 제공한 content_area 안에 텍스트를 배치해야 하므로, 공간 부족 시 **텍스트를 축약**한다. 반면 E는 좌표 제약 없이 텍스트를 전부 포함하되, 시각적으로는 겹쳐서 읽을 수 없다.

CCR은 "문자열이 HTML에 존재하는가"를 측정하지, "**시각적으로 읽히는가**"를 측정하지 않는다. E의 CCR=1.00은 텍스트가 겹쳐서 읽을 수 없는 상태에서도 달성된다. 이것이 **CCR·LOA·CSS Richness를 다축으로 함께 평가해야 하는 이유**이다.

---

## 7. 논의 (Discussion)

### 7.1 왜 레이어 분해가 효과적인가

단일 VLM이 전체 슬라이드를 생성할 때, 배경·카드·텍스트·아이콘을 **하나의 토큰 시퀀스**로 직렬화해야 한다. 이 과정에서:
- 배경은 "장식"으로 간주되어 단순화됨 (주의 배분 편향)
- z-index 같은 "선택적" 속성이 누락됨 (보수적 생성 편향)
- 요소 간 공간 관계가 암묵적 DOM 순서에 의존함

레이어 분해는 각 에이전트의 인지 범위를 **하나의 z-index 범위**로 한정하여, "배경만 잘 그려라", "카드만 잘 그려라"라는 단순한 과제로 변환한다. 이는 divide-and-conquer의 시각 버전이다.

### 7.2 좌표 기반 통신의 의의

기존 멀티에이전트 시스템은 자연어 또는 코드로 소통한다. LayerAgent는 **구조화된 좌표 JSON**으로 소통한다. 이 설계의 장점:
- **정보 손실 없음**: HTML 전달 시 발생하는 truncation 문제가 없음
- **타입 안전**: 좌표는 숫자이므로 해석 오류가 없음
- **검증 가능**: bbox가 슬라이드 범위(0~100%) 내인지 즉시 확인 가능

### 7.3 비대칭 Vision의 일반 원리

LayerAgent에서 발견한 "스타일은 이미지를 보고, 배치는 좌표만 따르라"는 원리는 다른 멀티에이전트 시스템에도 적용 가능할 수 있다:
- UI 생성: 디자인 에이전트는 참조 이미지를 보고, 코딩 에이전트는 spec만 따름
- 로봇 제어: 계획 에이전트는 전체 장면을 보고, 실행 에이전트는 좌표 명령만 따름
- 문서 생성: 레이아웃 에이전트는 템플릿을 보고, 콘텐츠 에이전트는 영역 spec만 따름

### 7.4 한계

- **콘텐츠 완성도 vs 구조 정확도 trade-off.** LayerAgent(F)는 content_area 제약으로 긴 텍스트를 축약하여 CCR이 E보다 낮을 수 있다. 이는 좌표 기반 배치의 구조적 한계이며, 동적 font-size 조절이나 content_area 크기 자동 확장으로 완화할 수 있다.
- 현재 실험은 GPT-4o 단일 모델, 10개 디자인으로 규모가 제한적이다. 다양한 VLM(Claude, Gemini)과 대규모 슬라이드셋(100+)에서의 검증이 필요하다.
- Edit Agent가 구조적 문제(잘못된 bbox)는 교정하지 못한다. CSS 값 수정만 가능하며 레이아웃 재구성은 불가능하다.
- 원본 디자인 이미지가 필요하므로 텍스트-투-슬라이드(이미지 없는) 시나리오에는 직접 적용이 어렵다.
- 에이전트 수(5개) 증가로 API 비용과 지연 시간이 Baseline 대비 3~8배 증가한다 (8s vs 26~63s).
- **시각 교정 에이전트의 부재.** 현재 LayerAgent는 생성 후 시각적 검증/교정 단계가 없다. Playwright 스크린샷과 원본을 비교하여 font-size, overflow 등을 자동 교정하는 Edit Agent를 실험하였으나, 현재 구현에서는 유의미한 개선이 관측되지 않았다. 반복 교정(iterative refinement)이나 강화학습 기반 자기 교정으로 확장하는 것이 향후 과제이다.
- **CCR의 시각적 가시성 미반영.** CCR은 HTML 소스의 문자열 존재 여부만 측정하므로, display:none이나 font-size:0 등으로 시각적으로 숨겨진 텍스트도 '존재'로 판정한다. 향후 OCR 기반 visual CCR로 확장하여 실제 가독성을 측정할 수 있다.
- **4-layer 분해의 스타일 특수성.** 본 연구의 4-layer 분해(Background, Cards, Content, Icons)는 다크 테마 + 글래스모피즘 + 아이콘 배지 스타일의 프레젠테이션에 최적화되어 있다. 텍스트 중심 슬라이드나 사진 중심 레이아웃에서는 일부 레이어가 비거나 분해 기준이 부적합할 수 있다. 다만 핵심 원리 — 출력의 시각 구조에 맞게 에이전트를 분해한다 — 는 레이어 수와 역할을 조정하여 다른 디자인 스타일에도 적용 가능하다.

---

## 8. 결론 (Conclusion)

본 논문은 VLM 기반 디자인-투-코드 생성에서 발생하는 시각 정보 손실의 근본 원인이 **슬라이드의 계층적 구조와 VLM의 평면적 생성 간의 구조적 불일치**임을 밝히고, 이를 해결하는 LayerAgent 프레임워크를 제안하였다.

핵심 발견:
1. VLM은 계층을 100% 인식하지만 코드로 0% 표현한다 — 분석(B)이나 패턴 주입(C)으로는 LOA가 0.13을 넘지 못하며, 레이어 분해만이 LOA=1.00을 달성한다
2. 레이어 분해 + 좌표 기반 통신으로 계층 정렬이 보장되며, Vision-Grounding을 결합하면 CSS 효과가 2.7배 증가한다 (E=5.0 → F=13.3)

이 발견은 디자인-투-코드를 넘어, **VLM이 구조화된 출력을 생성하는 과제**에서 "출력 구조에 맞는 에이전트 분해 + 구조화된 좌표 통신"이라는 설계 원칙의 유효성을 시사한다.

향후 연구에서는 (a) 다양한 VLM(Claude, Gemini)과 대규모 슬라이드셋에서의 검증, (b) content_area 크기 동적 조절로 CCR 개선, (c) 반복 교정 에이전트를 통한 시각 품질 자동 향상, (d) 웹 UI·모바일·포스터 등 타 도메인으로의 일반화를 수행할 예정이다.

---

## 참고 문헌 (References)

### 디자인-투-코드 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "Modular Multi-Agent Design-to-Code Framework." 2025.
- Laurençon, H., et al. "WebSight Dataset." 2024.

### 프레젠테이션 생성
- Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.
- Zeng, X., et al. "SlideTailor: Preference-Guided Paper-to-Slides Generation." AAAI 2026.
- SlideGen / Paper2Slide. "Six Collaborative VLM Agents." 2025.

### 평가 벤치마크
- WebRenderBench. "Layout-Style Consistency with Reinforcement Learning." 2025.
- Widget2Code. "Apple HIG-inspired Per-Property Evaluation." 2025.
- Image2Struct. "VLM Benchmark for Image-to-Structure." NeurIPS 2024.

### 계층 및 중첩
- LayerD. "Decomposing Raster Graphic Designs into Layers." ICCV 2025.
- SLEDGE. "Step-by-Step Layered Design Generation." AAAI 2026.
- OverLayBench. "Evaluating Overlap Handling in Layout-to-Image." NeurIPS 2025.

### 멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024. arXiv:2308.00352
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024. arXiv:2307.07924
- Li, G., et al. "CAMEL: Communicative Agents for 'Mind' Exploration of Large Language Model Society." NeurIPS 2023. arXiv:2303.17760

### VLM
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Radford, A., et al. "CLIP: Learning Transferable Visual Models." ICML 2021.
- Wang, Z., et al. "SSIM: Image Quality Assessment." IEEE TIP, 2004.
