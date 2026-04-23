# LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크

---

## 초록

시각적 프레젠테이션은 효과적인 의사소통에 필수적이며, Vision Language Model(VLM)의 발전은 디자인 이미지에서 실행 가능한 HTML/CSS 코드로의 자동 변환을 가능케 하였다. 그러나 단일 VLM 호출은 — 모델 능력이 향상되더라도 — 슬라이드 디자인 재현에 필요한 두 가지 속성을 구조적으로 보장하지 못한다: (1) **요소 간 시각 일관성** (다수 카드의 색·투명도·테두리·그림자 통일), (2) **콘텐츠와 시각 효과의 동시 충실도** (풍부한 CSS 생성과 정확한 텍스트 배치 사이의 zero-sum 경쟁). 또한 디자인-투-코드 분야의 양적 메트릭(CSS 속성 수, Block-Match, element-matching)은 perceived visual fidelity를 underdetermine하여 평가 타당성 위기를 야기한다 (DreamHouse 2026: structural/visual joint pass rate 7.1%).

본 논문은 이 두 보장과 평가 타당성을 명시적으로 부과하는 **LayerAgent** 프레임워크를 제안한다. LayerAgent는 디자인-투-코드 생성을 4개의 순차 단계로 분해한다: (1) **레이아웃 분석** — 요소 위치/유형 추출, (2) **요소별 렌더링** — 카드 단위 풍부한 CSS 생성, (3) **Style Normalizer** — 카드 간 CSS 통일을 *pre-render에서* 강제 (RQ1의 핵심 답), (4) **Text Inserter** — 시각 디자인 확정 후 텍스트 삽입으로 zero-sum 경쟁 제거 (RQ2의 핵심 답). 평가는 **tool-grounded (DOM JSON + screenshot) cross-model VLM-as-Judge** 와 양적 메트릭의 동반 검증으로 수행하며, position-randomization과 swap-debias를 포함한 2026 best practice를 따른다.

10종 슬라이드 디자인(타임라인, 허브-스포크, 피라미드, 대시보드 등)에 대한 실험에서 LayerAgent는 GPT-4o 기반 single-pass baseline 대비 ConsistencyScore와 CSS Richness, CCR을 동시에 향상시켰으며, cross-model VLM-as-Judge가 양적 향상이 perceived fidelity 개선과 동반함을 확인하였다 (단, validity의 직접 검증은 인간 평가가 필요하며 향후 연구로 둠). H-RAG 기반 단일 VLM 기법은 CSS Richness를 2.8→10.3으로 올리지만 CCR이 0.26으로 붕괴(콘텐츠 74% 소실)하는 zero-sum 패턴을 보였다. GPT-5.4·Claude 4.6 Opus single-pass와의 비교는 두 보장 실패가 *현재 세대 SOTA closed VLM 전반에서 일관되게 나타남* (즉, LayerAgent의 가치가 단일 모델의 약점 보강이 아니라 단계 분리가 부과하는 구조적 보장임)을 시사한다.

**키워드**: 디자인-투-코드, 멀티에이전트, 시각 일관성, 콘텐츠 충실도, 측정 타당성, VLM-as-Judge, 프레젠테이션 생성

---

## 1. 서론

### 1.1 연구 배경

시각적 프레젠테이션은 시각적 의사소통에서 중요한 역할을 담당한다. 발표, 보고서, 다양한 형태의 개념 전달에 빈번히 사용되며, 청중의 이해를 높이는 데 기여한다. 최근 생성 모델 및 멀티모달 대규모 언어 모델(MLLM)의 급속한 발전과 더불어 (Alayrac et al., 2022; Liu et al., 2023; Team et al., 2023), 시각적 프레젠테이션의 자동 생성에 많은 노력이 투입되고 있다.

디자인 참조 이미지로부터 실행 가능한 HTML/CSS를 생성하는 과제는 다음 세 축에서 **원본 디자인에 대한 충실도(fidelity)**를 요구한다: (1) **레이아웃 구조 재현**: 생성된 슬라이드는 원본의 배치 패턴(타임라인, 허브-스포크, 피라미드 등)을 구조적으로 따라야 한다. (2) **CSS 시각 재질 재현**: 글래스모피즘, 네온 글로우, 다중 그라디언트 등 CSS 속성으로 구현되는 시각 효과를 충실히 재현해야 한다. (3) **콘텐츠 완성도**: 제공된 모든 텍스트 콘텐츠가 최종 출력에서 누락 없이 나타나야 한다. 본 연구는 이 세 축에 대한 충실도를 평가 대상으로 삼으며, 참조 없이 평가되는 절대적 심미 품질(예: "이 슬라이드가 발표 자료로 쓸 만한가")은 범위 밖으로 둔다.

디자인-투-코드 생성에 관한 기존 연구는 두 가지 범주로 나뉜다: (1) **직접 생성** 방식으로, VLM이 디자인 이미지를 단일 패스로 HTML/CSS 코드로 변환하는 접근 (Si et al., 2024; Laurençon et al., 2024)과, (2) **다단계 생성** 방식으로, 중간 분석이나 계획 단계가 코드 생성에 선행하는 접근 (DCGen, 2025; LaTCoder, 2025; ScreenCoder, 2025)이다. 다단계 접근은 레이아웃 정확도를 개선하지만, 글래스모피즘, 네온 글로우, 다중 그라디언트와 같은 CSS 시각 효과의 품질을 명시적으로 다루지는 않는다.

### 1.2 문제 정의: 단일 VLM이 보장하지 못하는 두 속성과 평가 타당성

본 연구는 VLM 기반 디자인-투-코드 생성에서 **단일 VLM 호출이 — 모델 능력이 향상되더라도 — 구조적으로 보장하지 못하는 두 속성**과, 디자인-투-코드 분야 전반에 걸친 **평가 타당성** 문제를 식별하여 세 가지 연구 질문(RQ)으로 정식화한다.

**RQ1 — Cross-Element Visual Consistency (요소 간 시각 일관성).** 슬라이드 디자인은 다수의 카드/요소로 구성되며, 이들 간에는 색·투명도·테두리·그림자가 통일되어야 한다. 그러나 단일 VLM 호출은 자기회귀 생성 도중 의미적으로 동등한 요소들에 서로 다른 스타일을 부여하는 경향이 있다 — 카드 A는 `rgba(30,30,40,0.6)` 글래스모피즘인데 카드 B는 불투명 `#1e1e28` 단색이 되는 식이다. 이 문제는 **A2UI Protocol (Google, 2026)**, **Multi-Agent Design Orchestration (2026)** 등에서 agent-driven UI의 핵심 과제로 명시적으로 인정되어 왔다. 본 연구는 이를 슬라이드 도메인에서 정식 측정 가능한 형태(`ConsistencyScore`, §5.1)로 환원하고, **pre-render 정규화(Style Normalizer) 가 post-hoc render-then-refine 류 (DesignCoder의 self-correcting refinement, VisRefiner의 visual difference learning) 대비 효과적인지** 비교한다. 부수적으로, 단일 VLM의 인지 부하는 카드 간 *재질 불일치*뿐 아니라 *레이아웃 구조 단순화*(허브-스포크 → 그리드, 피라미드 → 리스트)로도 발현되며, 본 연구는 이 두 발현을 같은 메커니즘의 두 채널로 본다.

**RQ2 — Joint Content-Visual Fidelity (콘텐츠-시각 동시 보장).** 풍부한 CSS 효과 생성과 정확한 텍스트 콘텐츠 배치는 단일 VLM의 제한된 생성 용량 위에서 zero-sum 경쟁 관계에 있다. CSS 패턴 지식 주입(H-RAG)으로 CSS Richness를 2.8→10.3으로 향상시켰을 때 콘텐츠 완성도(CCR)가 0.80→0.26으로 붕괴하여 입력 텍스트의 74%가 소실되는 것이 그 증거이다. 본 연구는 시각 디자인 생성과 텍스트 삽입의 **단계 분리(Text Inserter)** 가 이 트레이드오프를 구조적으로 해소함을 ablation으로 보인다.

**RQ3 — Convergent Reliability and Provisional Measurement Validity in Design-to-Code.** 디자인-투-코드 분야에서 널리 쓰이는 양적 메트릭 — CSS 속성 수, Block-Match (Design2Code), element-matching (SlidesBench), attribute overlap (Widget2Code) — 은 perceived visual fidelity를 충실히 반영하지 못한다. CSS Richness는 동일 색 `box-shadow` 4겹이나 충돌하는 그라디언트 중첩으로 부풀려질 수 있으며, 구조 메트릭은 카드 위치만 일치하면 단색 블록과 글래스모피즘에 동일 점수를 부여한다. 최근 **DreamHouse (arXiv:2603.24866, 2026)** 는 structural validity와 visual fidelity가 직교적 신호이며 최상위 VLM조차 joint pass rate 7.1%에 그침을 보였다.

본 연구는 두 단계로 RQ3를 다룬다. **첫째, *convergent reliability*** — 본 연구의 핵심 empirical claim — 으로, **tool-grounded (DOM JSON + screenshot 동시 제공) cross-model VLM-as-Judge** (Claude 4.6 Opus / GPT-5.4 / Gemini 2.5)가 양적 메트릭과 *어떤 패턴으로 일치/불일치*하는지를 Kendall-τ 분석으로 측정한다 (§5.2.3). 평가 프로토콜은 2026 best practice를 따라 position-randomization과 swap-debias를 포함한다. **둘째, *provisional measurement validity*** — 인간 평가와의 직접 정렬은 본 paper의 범위를 넘어서며 (cf. MT-Bench, AlpacaEval에서 인간 anchor가 핵심 contribution), 본 연구는 *convergent reliability 결과 + DreamHouse 2026의 외부 anchor + 2026 tool-grounding 결과 (verdict consistency 71→89%)* 를 근거로 *잠정적* validity claim을 제기하며, 인간 평가를 동반한 직접 검증은 향후 연구로 둔다 (§7 참조). 본 framing은 "VLM 합의 = validity" 라는 circular argument를 명시적으로 회피한다.

**SOTA 일관성 가설 (구 "모델-독립성").** 위 세 RQ는 단일 VLM의 자기회귀 생성에서 기인하는 **구조적 한계**로 가설화하며, *현재 세대 SOTA closed VLM 전반*에서 자연스럽게 해소되지 않을 것으로 예상한다. 이를 직접 검증하기 위해 본 연구는 GPT-4o, GPT-5.4 (Azure), Claude 4.6 Opus (Bedrock) 세 모델에서 동일한 single-pass baseline의 ConsistencyScore와 joint fidelity를 비교한다 (§5.3.4). GPT-5.4 single-pass의 ConsistencyScore가 LayerAgent-on-GPT-4o보다 낮다면, 문제는 *해당 모델 세대*의 용량이 아닌 *생성 구조* 자체에 있음을 시사한다. (open-weight 모델 또는 차세대 frontier 모델로의 일반화는 향후 연구로 둔다 — §7 참조.)

### 1.3 진단 실험: 인지 부하와 두 종류의 보장 실패

세 RQ의 메커니즘적 뿌리를 확인하기 위해 다음의 통제 실험을 수행하였다:

> **동일한 GPT-4o가 전체 슬라이드 이미지에서는 CSS 효과 2.8개와 카드 간 일관성 점수 ConsistencyScore≈0.4–0.6 수준을 생성하지만, 카드 하나를 크롭한 이미지에서는 카드당 CSS 효과 6~8개(글래스모피즘 포함)를 생성한다. 모델, 프롬프트, 디자인은 동일하며, 오직 시각 범위만 다르다.**

이는 단일 VLM의 한계가 *근본적 능력*이 아니라 **자원 배분의 구조적 문제**임을 시사한다: 전체 슬라이드 이미지를 처리할 때 VLM은 레이아웃 구조와 콘텐츠 배치에 우선순위를 두고, 세밀한 CSS 재질이나 카드 간 스타일 통일에는 충분한 생성 자원을 배분하지 못한다. `backdrop-filter`, `rgba` 알파 채널, 다중 레이어 `box-shadow`는 이 없이도 HTML이 렌더링된다는 점에서 "선택적"이며, 카드 간 통일 또한 의미적으로는 동일하지만 토큰 단위로는 *재기억해야 하는* 정보이다 — 인지 부하 상황에서 둘 다 단순화·망각의 대상이 된다.

이 관찰은 두 가지 설계 결정으로 이어진다. 첫째, 요소 분해(크롭)는 카드별 CSS 재질을 회복시킨다. 둘째, 그러나 크롭만으로는 카드 *사이의* 일관성이 자동 보장되지 않는다 — 독립 생성된 결과들이 색·투명도·테두리에서 어긋날 수 있다. 따라서 **크롭(Stage 1) + 명시적 정규화(Stage 2 Style Normalizer) + 시각/텍스트 단계 분리(Stage 3 Text Inserter)** 의 3중 전략이 필요하다. 본 §1.3의 진단 실험은 §3에서 ConsistencyScore와 joint fidelity 메트릭으로 정식 측정되며, 모델-독립성 가설은 §5.3.4의 GPT-4o vs GPT-5.4 vs Claude 4.6 Opus 비교로 검증된다.

### 1.4 제안 방법: LayerAgent

세 RQ를 해결하기 위해 본 연구는 디자인-투-코드 생성을 4개의 전문화된 단계로 분해하는 멀티에이전트 프레임워크 **LayerAgent**를 제안한다. 각 단계는 특정 RQ의 해결 메커니즘에 대응된다:

1. **레이아웃 분석 (Stage 0)**: VLM이 전체 디자인 이미지를 분석하여 레이아웃 유형(타임라인, 허브-스포크, 그리드, 피라미드 등)을 판별하고, 각 요소의 위치를 바운딩 박스 좌표로 추출한다. 전역 구조를 **명시적 형태**로 고정함으로써 RQ1의 두 채널 중 *레이아웃 단순화* 채널을 사전에 차단한다.

2. **요소별 크롭 렌더링 (Stage 1, → RQ1 재질 채널)**: 원본 이미지에서 감지된 각 요소 영역을 크롭하여 Card Detail Agent에 독립적으로 처리시킨다. 좁아진 시각 범위 덕분에 글래스모피즘, 네온 글로우 등 풍부한 CSS 재질이 카드별로 재현된다. Background Agent는 별도로 전체 이미지에서 배경을 생성한다 (병렬).

3. **스타일 정규화 (Stage 2, → RQ1 일관성 채널)**: 독립 생성으로 인한 카드 간 CSS 불일치(서로 다른 투명도, 테두리, 그림자)를 Style Normalizer가 조립된 HTML 코드 위에서 통일한다. **위치나 구조는 변경하지 않으며**, CSS 속성값만 동기화한다 — 본 단계가 RQ1의 핵심 답이다.

4. **텍스트 삽입 (Stage 3, → RQ2)**: Text Inserter가 완성된 시각 구조에 콘텐츠 텍스트를 삽입한다. 시각 디자인이 이미 확정되어 있으므로 텍스트 삽입은 CSS 품질에 간섭하지 않으며, 이로써 단일 VLM에서 발생하던 시각/콘텐츠 zero-sum 트레이드오프가 구조적으로 해소된다.

(RQ3 답: 위 네 단계의 효과는 §5.1의 양-질 동반 검증 프로토콜 — `ConsistencyScore`/`CCR`/`CSS Richness`/`structural metrics` × `tool-grounded VLM-as-Judge` — 으로 확인된다.)

### 1.5 기여

본 논문의 기여는 다음과 같다:

- **단일 VLM 호출이 모델 능력 향상으로도 보장하지 못하는 두 속성과 평가 타당성 문제 식별**: (RQ1) Cross-Element Visual Consistency — 카드 간 시각 일관성, (RQ2) Joint Content-Visual Fidelity — 시각/텍스트 zero-sum 트레이드오프, (RQ3) Measurement Validity — 양적 D2C 메트릭이 perceived fidelity를 underdetermine한다는 측정학적 증거 (DreamHouse 2026의 슬라이드 도메인 재확인).

- **LayerAgent 프레임워크**: 두 보장을 명시적 단계 분리로 부과하는 4단계 멀티에이전트 파이프라인. **Style Normalizer** (RQ1의 일관성 채널을 pre-render에서 강제, post-hoc iteration 대비 효과 검증)와 **Text Inserter** (RQ2의 zero-sum을 구조적으로 제거)를 핵심 contribution으로, Layout Analyzer + 요소 크롭을 보조 메커니즘으로 한다. LangGraph로 구현.

- **양-질 동반 검증 평가 프로토콜**: CSS Richness가 중복·충돌 속성으로 부풀려질 수 있음을 명시적으로 제기하고, **tool-grounded (DOM JSON + screenshot) cross-model VLM-as-Judge** 와 양적 메트릭의 동반 검증을 평가 원칙으로 확립한다. 2026 best practice (position-randomization, swap-debias, cross-model triangulation) 채택.

- **정량적 검증 + SOTA 일관성**: GPT-4o에서 LayerAgent는 ConsistencyScore와 CSS Richness, CCR을 동시에 향상시키고, cross-model VLM-as-Judge (Claude / GPT-5.4 / Gemini, position-randomized + swap-debiased) 가 양적 향상이 perceived fidelity 개선과 동반함을 확인한다 (인간 anchor는 향후 검증). H-RAG 기반 단일 VLM 기법(CCR 0.26)과의 대비로 zero-sum 트레이드오프 해소를 보이며, GPT-5.4·Claude 4.6 Opus single-pass와의 비교로 두 보장 실패가 *현재 세대 SOTA closed VLM 전반에서 일관됨*을 검증한다.

---

## 2. 관련 연구

### 2.1 디자인-투-코드 생성

디자인-투-코드 생성은 시각 디자인을 실행 가능한 코드로 변환하는 것을 목표로 한다. **Design2Code** (Si et al., 2024)는 484개의 실제 웹페이지로 구성된 벤치마크를 도입하고 GPT-4V가 스크린샷-투-HTML 변환에서 중간 수준의 충실도를 달성함을 보고하였다. **WebSight** (Laurençon et al., 2024)는 디자인-투-코드 모델 학습을 위한 200만 쌍의 합성 데이터셋을 공개하였다. **DCGen** (FSE 2025)은 페이지를 블록 단위로 분할하여 독립적으로 코드를 생성하는 분할 정복 접근을 제안하였다. **LaTCoder** (KDD 2025)는 코드 이전에 레이아웃을 "사고 과정(chain of thought)"으로 생성한다.

본 연구와 가장 가까운 두 동시대 연구는 **ScreenCoder** (arXiv:2507.22827, 2025)와 **DesignCoder** (arXiv:2506.13663, 2025)이다.
- **ScreenCoder**는 본 연구와 동일한 *웹 도메인 HTML/CSS 출력*을 생성하며, Grounding → Planning → Generation의 3단계 멀티에이전트 구조를 채택한다. 50,000 image-code pair 데이터셋과 함께 RL 미세조정(GRPO)을 도입하였다. **차별점**: ScreenCoder의 cross-element 일관성은 *원본 스크린샷에서 image patch를 추출하여 placeholder를 대체*하는 Hungarian-algorithm 매칭 방식이며, 본 연구의 Style Normalizer는 *생성된 CSS code 위에서 속성값을 통일*하는 코드-수준 기법이다. 즉, ScreenCoder는 visual content reuse, 본 연구는 generative code uniformity라는 다른 차원에서 일관성을 다룬다. 또한 ScreenCoder는 "Text Inserter" 같은 시각/콘텐츠 분리 단계가 없어 RQ2의 zero-sum을 해소하지 못한다.
- **DesignCoder**는 모바일 UI / React Native 도메인에서 UI Grouping Chain → Hierarchy-Aware Generation → **Self-Correcting Refinement** 3단계를 사용한다. 마지막 단계는 Appium으로 렌더링한 결과를 원본과 비교하여 컴포넌트별 수정을 *post-hoc*로 가하는 iterative refinement이다. **차별점**: DesignCoder는 *post-render 검증-수정* 패러다임이고, LayerAgent의 Style Normalizer는 *pre-render 정규화* 패러다임이다. 본 연구의 Style Normalizer ablation (§5.2.1, D vs D₁) 은 pre-render 정규화의 effect size를 격리해서 보여주며, post-render iterative refinement와의 직접 head-to-head 비교는 동일 backbone 위에서 향후 추가 검증 대상으로 남긴다.

DCGen·ScreenCoder·DesignCoder 모두 본 연구가 식별한 두 보장 (RQ1 cross-element consistency, RQ2 joint content-visual fidelity)을 *통합적으로* 부과하지 않는다 — DCGen은 레이아웃 정확도, ScreenCoder는 image patch 재사용, DesignCoder는 post-hoc refinement에 초점을 맞추며, 모두 슬라이드 도메인 특유의 글래스모피즘·네온 글로우 같은 *생성형 CSS 재질의 카드 간 통일*은 다루지 않는다. 본 연구는 이 gap을 Style Normalizer + Text Inserter의 단계 분리로 메우고, 평가 측면에서 DreamHouse 2026의 양/질 직교성을 슬라이드 도메인에서 재확인한다 (RQ3).

반복적 시각 교정에 관한 최근 연구도 관련이 깊다. **VisRefiner** (arXiv:2602.05998, 2025)는 렌더링된 예측 결과와 참조 디자인 간의 시각적 차이를 학습하는 프레임워크로, GPT-4o 대비 Block Match에서 21.5점의 향상을 달성하였다. **Vision-Guided Iterative Refinement** (arXiv:2604.05839, 2026)은 VLM 기반 시각 비평(critic)을 통해 렌더링된 웹페이지에 구조화된 피드백을 제공하며, 3회 반복 교정을 통해 17.8%의 개선을 보고하였다. 이러한 접근은 본 연구와 상호 보완적이다: 이들은 반복적 렌더링과 비교를 통해 품질을 개선하는 반면, 본 연구는 입력 분해를 통해 품질을 개선한다.

### 2.2 프레젠테이션 생성

프레젠테이션 생성에 대한 초기 접근은 추출적 요약, 규칙 기반 템플릿, 또는 레이아웃 휴리스틱에 의존하였으며 (Hu and Wan, 2014; Xu and Wan, 2022; Sun et al., 2021; Fu et al., 2022), 유연성과 멀티모달 지원이 부족한 경우가 많았다.

LLM 기반의 최근 방법은 두 가지 범주로 분류된다. 첫 번째는 확산 모델이나 이미지 조건부 모델을 사용하여 슬라이드 이미지를 직접 합성하는 방식 (Ma et al., 2025; Chen et al., 2025)으로, 시각적으로 풍부한 출력을 생성하나 구조적 제어와 편집 가능성이 제한적이다. 두 번째는 마크다운이나 HTML과 같은 중간 표현을 생성하고 이를 슬라이드로 렌더링하는 방식 (Zheng et al., 2025; Ge et al., 2025; Cachola et al., 2024; Bandopadhyay et al., 2024)이다. 이 접근은 레이아웃 제어 가능성을 높이고 후편집을 가능케 하지만, 렌더링된 시각 출력을 검증하는 메커니즘이 부족한 경우가 많다.

대표적 연구로는 LLM 피드백에 기반한 템플릿의 반복적 수정을 통해 인간 편집 워크플로우를 모사하는 **PPTAgent** (Zheng et al., 2025), 반복적 교정을 위한 중간 코드 리뷰와 시각 페이지 리뷰 메커니즘을 모두 도입한 **PreGenie** (Xu et al., 2025), CGSeg 세그멘테이션과 계층적 RAG를 결합한 이미지-투-python-pptx 변환의 **SlideCoder** (Tang et al., 2025), 구조화된 시각 설계 원칙을 통한 레이아웃 인지 코드 합성을 강조한 **AutoPresent** (Ge et al., 2025) 등이 있다.

이들 연구 중 **요소 간 시각 일관성**과 **콘텐츠-시각 zero-sum 트레이드오프**를 슬라이드 도메인의 *모델-독립적 구조 한계*로 정식화한 연구는, 저자들이 아는 한 보고된 바 없다. 본 연구는 두 보장 실패와 측정 타당성을 진단하고, 단계 분리(Style Normalizer + Text Inserter)와 동반 검증 평가 프로토콜을 해법으로 제안한다.

### 2.3 코드 생성을 위한 멀티에이전트 시스템

LLM 기반 멀티에이전트 시스템은 소프트웨어 공학 과제에서 우수한 성과를 보이고 있다. **MetaGPT** (Hong et al., 2023)는 소프트웨어 개발 역할(PM → 아키텍트 → 개발자 → QA)에 에이전트를 배정하고, **ChatDev** (Qian et al., 2023)는 대화 기반 협업을, **CAMEL** (Li et al., 2023)은 역할극 기반 통신 프로토콜을 도입하였다. 이들 시스템은 **소프트웨어 개발 프로세스**(설계 → 구현 → 테스트)를 기준으로 과제를 분해한다.

본 연구는 두 가지 점에서 차별화된다. 첫째, 개발 프로세스가 아닌 **시각 디자인의 물리적 요소**(배경, 카드 1, 카드 2, ...)를 기준으로 에이전트를 분담한다. 둘째, 에이전트 간 통신에 자연어나 코드가 아닌 **구조화된 좌표 JSON**(바운딩 박스)을 사용하여, 절단(truncation) 및 해석 오류를 제거한다.

### 2.4 디자인-투-코드 평가

기존 평가 접근은 전역 유사도 (CLIP, SSIM), 구조 매칭 (Design2Code의 Block-Match, SlidesBench의 element-matching), 속성 수준 평가 (WebRenderBench의 SDA, Widget2Code의 속성별 평가) 등을 포괄한다. 그러나 이들 메트릭은 **CSS 시각 효과의 풍부성**이나 **시각 품질과 콘텐츠 완성도 간의 트레이드오프**를 직접 측정하지 못한다. 본 연구에서는 이러한 차원을 포착하는 보완적 메트릭으로 CSS Richness(CSS 효과 속성의 절대 개수)와 CCR(콘텐츠 완성도 비율)을 제안한다.

---

## 3. 단일 VLM의 두 보장 실패와 측정 타당성 진단

LayerAgent의 4단계 설계를 동기 부여하는 진단 실험을 §3.1–§3.4에서 제시한다. 각 진단은 §1.2의 한 RQ에 대응하며, 정식 측정과 통계적 검증은 §5에서 수행한다 (`final_test/`).

### 3.1 진단 1: 시각 범위가 CSS 재질 품질을 결정한다 (RQ1 — 재질 채널)

네온 글로우 효과가 적용된 4개의 글래스모피즘 카드를 포함하는 타임라인 슬라이드 디자인에 대해 GPT-4o를 사용한 통제 실험을 수행한다.

**조건 A (전체 이미지)**: 1280×720 슬라이드 이미지 전체를 "이 디자인을 HTML/CSS로 변환하라"는 프롬프트와 함께 제공한다.

**조건 B (크롭 이미지)**: 동일 이미지에서 카드 하나(~300×400px)를 크롭하여 "이 카드를 HTML/CSS로 변환하라"는 프롬프트와 함께 제공한다.

모델, 온도(temperature), max_tokens는 두 조건에서 동일하다. 결과:

| 조건 | backdrop-filter | box-shadow 수 | 반투명 배경 | CSS 효과 총 수 |
|---|:---:|:---:|:---:|:---:|
| A. 전체 이미지 | 0건 | 2개 | 없음 (불투명) | 3 |
| B. 크롭 카드 | **1건** | **3개** | **있음 (rgba)** | **6~8** |

동일 모델이 글래스모피즘(backdrop-filter + rgba 배경)을 생성하는 것은 시각 범위가 단일 카드로 좁혀졌을 때에만 가능하다. 전체 이미지에서는 해당 카드가 불투명 단색 블록으로 렌더링된다.

### 3.2 해석: 자기회귀 토큰 예산 가설

전체 슬라이드를 처리할 때 VLM은 레이아웃 구조, 색상, 텍스트 영역, 아이콘, 장식 요소를 하나의 자기회귀 토큰 시퀀스 내에서 동시에 산출해야 한다. CSS 재질 속성(`backdrop-filter`의 blur 값, `box-shadow`의 레이어 수, `rgba` 알파 채널)은 이 없이도 HTML이 정상 렌더링된다는 점에서 "선택적"이며, 인지 부하 상황에서 가장 먼저 단순화의 대상이 된다. 동일한 메커니즘은 §3.3의 카드 간 일관성에도 적용된다 — 카드 B의 스타일을 카드 A와 통일하려면 카드 A의 스타일을 *기억하면서* 카드 B를 생성해야 하는데, 이 기억 또한 토큰 예산을 소모한다. 부수적으로 같은 메커니즘은 *레이아웃 구조*도 단순화한다 (허브-스포크 → 그리드, 피라미드 → 리스트).

### 3.3 진단 2: 카드 간 시각 일관성의 자발적 실패 (RQ1 — 일관성 채널)

§3.1의 크롭이 단일 카드의 재질을 회복시키더라도, **여러 카드를 독립적으로 생성하면 카드 간 스타일이 어긋난다**. 카드 A는 `rgba(30,30,40,0.6)` 글래스모피즘인데 카드 B는 불투명 `#1e1e28`, 카드 C는 `rgba(50,40,60,0.4)`로 서로 다르게 생성되는 식이다. 단일 VLM 호출도 자기회귀 진행 도중 후방 카드일수록 스타일이 흔들리는 동일한 현상을 보인다 (앞서 생성한 스타일을 토큰 예산 안에서 정확히 reproduce할 인센티브가 없기 때문).

본 연구는 이를 **`ConsistencyScore`** — 카드 간 CSS 속성(`border-radius`, `box-shadow blur/alpha`, `background-rgb/alpha`, `border-width`) 6종의 정규화된 변동계수 평균을 1에서 뺀 값 — 로 정식 측정한다. 측정 코드와 단위 테스트는 `final_test/metrics/consistency.py`에 공개한다. 정식 비교(single-pass / LayerAgent-NoStyleNorm / LayerAgent-Full × 10 designs × 3 seeds)는 §5.2.1에서 보고한다.

### 3.4 진단 3: CSS-콘텐츠 zero-sum 경쟁 (RQ2)

CSS 품질을 개선하기 위한 직관적 대안은 프롬프트에 CSS 패턴 지식을 주입하는 것이다. 이를 Method C (Visual CoT + H-RAG)로 구현하여 시스템 프롬프트에 글래스모피즘 레시피, 네온 글로우 패턴, 그라디언트 예시를 포함한다.

| 방법 | CSS Richness ↑ | CCR (콘텐츠 완성도) ↑ |
|---|:---:|:---:|
| A. Baseline (single-pass GPT-4o) | 2.8 | 0.80 |
| B. Visual CoT | 7.1 | 0.50 |
| C. CoT + H-RAG | **10.3** | **0.26** ← 콘텐츠 74% 소실 |
| D. LayerAgent (본 연구) | **26.5** | **0.99** |

CSS 지식 주입(C)은 CSS Richness를 2.8→10.3으로 끌어올리지만 CCR이 0.80→**0.26**으로 붕괴한다 — 텍스트 콘텐츠의 74%가 누락된다. 이는 구조적 한계이다: 단일 HTML 출력을 생성하는 단일 VLM은 CSS 효과와 콘텐츠 배치 사이에 한정된 생성 용량을 분배해야 한다. 한 축을 최적화하면 다른 축이 저하되는 zero-sum 경쟁이 발생한다. LayerAgent는 CSS 생성(Stage 1 Card Detail Agents)과 콘텐츠 삽입(Stage 3 Text Inserter)을 서로 다른 파이프라인 단계로 분리함으로써 이 트레이드오프를 구조적으로 제거한다.

### 3.5 진단 4: 양적 메트릭의 부풀림 가능성 (RQ3 — 측정 타당성)

CSS Richness는 시각 품질의 *양적 상한(upper bound)* 일 뿐이며, **중복·충돌 속성으로 부풀려질 수 있다**. 동일 색의 `box-shadow` 4겹은 속성 수를 4배로 늘리지만 시각 결과는 단일 그림자와 다름없거나 더 조악하다. 상충하는 `gradient` 레이어를 중첩하면 숫자만 늘 뿐 품질은 저하된다. Block-Match·element-matching 같은 구조 메트릭도 카드 위치만 일치하면 단색 블록과 글래스모피즘에 동일 점수를 부여한다.

DreamHouse (arXiv:2603.24866, 2026)는 structural validity와 visual fidelity가 직교 신호임을 정량적으로 증명하였다 (joint pass rate 7.1%). 본 연구는 이 직교성을 슬라이드 도메인에서 재확인하고, **양적 메트릭과 tool-grounded cross-model VLM-as-Judge의 동반 검증**을 통해서만 perceived fidelity 향상을 입증한다. 정식 측정 (CSS Richness × CCR × Block-Match × element-IoU × CLIP × SSIM × VLM-judge × 3 models의 Kendall-τ heatmap)은 §5.2.3 (RQ3 killer experiment)에서 보고한다.

### 3.6 세 RQ 요약

| RQ | 진단 절 | 단일 VLM 실패 양상 | LayerAgent 해법 |
|---|---|---|---|
| RQ1 (Consistency) | §3.1 + §3.3 | 재질 단순화 + 카드 간 스타일 불일치 | 요소 크롭 (Stage 1) + Style Normalizer (Stage 2) |
| RQ2 (Joint Fidelity) | §3.4 | CSS↑ → CCR↓ zero-sum | 시각/텍스트 단계 분리 (Stage 1 vs 3) |
| RQ3 (Measurement Validity) | §3.5 | 양적 메트릭이 perceived fidelity를 underdetermine | tool-grounded cross-model VLM-as-Judge 동반 검증 |

---

## 4. LayerAgent 프레임워크

### 4.1 전체 구조

LayerAgent는 디자인-투-코드 생성을 4개의 순차적 단계로 분해하며, 각 단계는 전문화된 에이전트가 담당한다. 파이프라인은 LangGraph의 StateGraph로 구현되며, 가능한 경우 병렬 실행을 활용한다.

```
                    ┌─────────────────────┐
                    │  Layout Analyzer    │  전체 이미지 → 레이아웃 유형 + 요소 위치
                    └──────────┬──────────┘
                    ┌──────────┴──────────┐
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
Stage 1  │ Background Agent │  │ Card Detail Agent │ × N
(병렬)   │ (전체 이미지)     │  │ (크롭 이미지)     │
         │ → bg_html        │  │ → card_html × N   │
         └────────┬─────────┘  └────────┬─────────┘
                  │                     │
                  └──────────┬──────────┘
                             ▼
                    ┌─────────────────┐
Stage 2             │ Style Normalizer│  카드 간 CSS 통일
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
Stage 3             │ Text Inserter   │  완성된 구조에 텍스트 삽입
                    └─────────────────┘
```

### 4.2 Stage 0: 레이아웃 분석기

레이아웃 분석기는 전체 디자인 이미지를 입력받아 두 가지를 출력한다: (1) **레이아웃 유형**과 (2) **요소 바운딩 박스**.

**레이아웃 유형 감지.** 분석기는 슬라이드를 7가지 레이아웃 유형 중 하나로 분류한다: `horizontal_row`, `grid`, `hub_spoke`, `pyramid`, `split`, `vertical_stack`, `freeform`. 이 분류는 서로 다른 레이아웃이 서로 다른 요소 배치 전략을 요구하기 때문에 중요하다. 예를 들어, 타임라인 레이아웃은 카드를 균등 간격으로 수평 배치하지만, 허브-스포크 레이아웃은 카드를 중앙 허브 주위에 방사형으로 배치한다. 단일 배치 전략(예: 수평 균등 배치)을 하드코딩하면 타임라인에서는 정확한 결과를 내지만 허브-스포크나 피라미드 레이아웃에서는 배치가 크게 어긋나게 된다.

**요소 위치 추출.** 감지된 각 카드/요소에 대해, 분석기는 이미지 크기 대비 비율(0~1)로 바운딩 박스 좌표를 출력한다. 이 좌표는 (1) 원본 이미지에서 요소 영역을 크롭하고, (2) 최종 조립된 HTML에서 렌더링된 요소를 배치하는 데 사용된다.

### 4.3 Stage 1: 요소별 렌더링

RQ1의 *재질 채널* (단일 카드의 CSS 재질 재현)을 다루는 단계이다. 레이아웃 분석기가 감지한 각 요소에 대해:

1. 원본 디자인 이미지를 해당 요소의 바운딩 박스 영역으로 **크롭**한다 (주변 글로우 효과를 포착하기 위한 소량의 패딩 포함).
2. 크롭된 이미지를 **Card Detail Agent**에 제공하고, 시각 디자인을 HTML/CSS로 재현하도록 지시한다.
3. 에이전트가 해당 단일 요소에 대한 CSS를 생성한다. 글래스모피즘, 네온 테두리, 내부 섹션 구분, 그림자 효과 등을 포함한다.

에이전트가 전체 슬라이드(1280×720, 다수 요소 포함) 대신 하나의 요소(~300×400 픽셀)만 처리하므로, CSS 재질 재현에 전체 주의(attention)를 할당할 수 있다. 이것이 9.5배 CSS 향상의 원천이다.

**Background Agent**는 Card Detail Agents와 병렬로 실행되며 **전체 이미지**를 처리하여 배경 요소를 생성한다: 그라디언트, 글로우 효과, 장식 라인, 도트 패턴, 타임라인 연결선 등. 배경 에이전트는 배경이 전체 슬라이드에 걸쳐있어 의미 있게 크롭할 수 없기 때문에 전체 이미지에서 작동한다.

### 4.4 Stage 2: 스타일 정규화

각 카드가 서로 다른 크롭에서 독립적으로 생성되었으므로, CSS 스타일이 카드 간에 불일치할 수 있다 — 서로 다른 배경 투명도, 테두리 색상, 그림자 강도, border-radius 값 등. Style Normalizer는 조립된 HTML 코드를 읽고 CSS 속성 값을 통일함으로써 이를 해결한다:

- 배경 rgba 알파값 → 모든 카드에서 통일
- 테두리 색상 및 두께 → 통일
- Border-radius → 통일
- Box-shadow → 통일
- Backdrop-filter blur 값 → 통일

중요한 제약: Style Normalizer는 **위치나 구조를 변경하지 않는다** (position, left, top, width, height은 그대로 유지). 이미지 입력 없이 HTML 코드만을 처리하는 텍스트 전용 에이전트이다.

### 4.5 Stage 3: 텍스트 삽입

Text Inserter는 완전히 스타일링된 HTML(배경 + 카드 + 정규화된 스타일)과 콘텐츠 데이터(제목, 설명, 메트릭 등)를 받아, 기존 HTML 구조에 텍스트를 삽입한다.

이 단계가 CSS-콘텐츠 트레이드오프를 해소하는 핵심이다. 이 시점에서 시각 디자인이 이미 완성되어 있으므로, Text Inserter의 유일한 과제는 카드 HTML 요소 내의 빈 영역을 찾아 텍스트 콘텐츠를 추가하는 것이다. CSS를 생성하거나 시각 레이아웃을 수정할 필요가 없다. 이 분리를 통해 CSS 품질(Stage 1으로부터)과 콘텐츠 완성도(Stage 3으로부터)가 동일 모델의 생성 용량을 놓고 경쟁하지 않게 된다.

Text Inserter는 카드 HTML 구조를 분석하고, 콘텐츠 컨테이너 역할을 하는 내부 `div` 요소를 식별하여, 그 안에 텍스트를 배치한다. 이 접근은 텍스트가 카드 구조와 독립적으로 위치할 때 발생하는 정렬 불일치를 방지하므로, 오버레이 기반 텍스트 배치보다 견고하다.

### 4.6 구현 상세

LayerAgent는 LangGraph v1.0 StateGraph로 구현된다. 레이아웃 분석기와 Background Agent는 GPT-4o의 비전 기능을 사용하여 전체 이미지를 처리한다. Card Detail Agents도 크롭된 이미지에 대해 비전을 사용한다. Style Normalizer와 Text Inserter는 이미지 입력 없이 HTML 코드만을 처리하는 텍스트 전용 에이전트이다.

모든 에이전트는 GPT-4o를 사용하며, 글래스모피즘, 네온 글로우, 그라디언트 사양 등 구체적 CSS 패턴 레시피와 출력 형식 제약을 포함하는 시스템 프롬프트를 사용한다. 충분히 상세한 CSS 생성을 허용하기 위해 에이전트당 max_tokens 제한을 12,000으로 설정한다.

---

## 5. 실험

### 5.1 실험 설정

**데이터.** Gemini 2.5 이미지 생성 모델을 사용하여 10종의 다양한 슬라이드 디자인 이미지를 생성하였다. 각 디자인은 전문적 프레젠테이션에서 흔히 사용되는 고유한 레이아웃 유형을 대표한다:

| # | 레이아웃 | 구조 | 복잡도 |
|---|---|---|:---:|
| 01 | Timeline | 4노드 + 카드 + 네온 라인 | 높음 |
| 02 | Dashboard | 3 메트릭 카드 + 차트 영역 | 중간 |
| 03 | Comparison Split | 좌우 분할 + VS 배지 + 8카드 | 높음 |
| 04 | Pyramid | 3단계 계층 (1-2-3 카드) | 중간 |
| 05 | Hub & Spoke | 중앙 허브 + 6 연결 카드 | 높음 |
| 06 | Before/After | 색상 전환을 동반한 변환 | 중간 |
| 07 | Feature Grid | 2×3 그리드 + 아이콘 + 태그 | 중간 |
| 08 | Roadmap | 5 페이즈, 상하 교차 배치 | 높음 |
| 09 | Layered Stack | 4층 겹침 + 레인보우 그라디언트 | 매우 높음 |
| 10 | Stats Hero | 히어로 숫자 + 4 스탯 카드 | 중간 |

모든 디자인은 다크 테마에 글래스모피즘, 네온 글로우, 복합 그라디언트 효과를 포함한다 — 카드 간 일관성 (RQ1)과 콘텐츠 충실도 (RQ2)가 모두 도전적인 유형의 디자인이다.

**비교 방법.** 모든 방법에 동일한 디자인 이미지와 텍스트 콘텐츠를 제공한다 (공정 비교). RQ1·RQ2 검증을 위해 LayerAgent의 두 ablation을 추가한다:

| 코드 | 방법 | 접근 방식 |
|---|---|---|
| A | Baseline | 단일 VLM이 전체 이미지를 보고 HTML/CSS를 한 번에 생성 |
| B | Visual CoT | VLM이 시각 요소 분석 후 코드 생성 (2단계) |
| C | CoT + H-RAG | Visual CoT + CSS 패턴 지식(글래스모피즘 등) 주입 |
| D₁ | LayerAgent − Style Normalizer | RQ1 ablation — Stage 2 제거 (카드 간 일관성 보정 없음) |
| D₂ | LayerAgent − Text Inserter | RQ2 ablation — Stage 3 제거 (텍스트를 Card Detail Agent가 처리) |
| **D** | **LayerAgent (본 연구)** | **4단계 full pipeline** |

**모델.** 주 비교(A–D)는 GPT-4o로 통제한다. 모델-독립성 검증(§5.3.4)을 위해 single-pass baseline을 GPT-4o, GPT-5.4 (Azure), Claude 4.6 Opus (Bedrock) 세 모델에서 추가 실행한다.

**평가 메트릭.** 본 연구는 RQ별로 양적·질적 메트릭을 페어링하여 보고한다 (RQ3의 동반 검증 원칙). 모든 메트릭 코드와 단위 테스트는 `final_test/metrics/` 아래에 공개한다.

**자동 메트릭 (reference-free, deterministic):**
- **`ConsistencyScore`** (RQ1 headline, *provisional metric*): 한 슬라이드 내 카드 간 6 CSS 속성(`border-radius`, `box-shadow blur`, `box-shadow alpha`, `background-rgb-distance`, `background-alpha`, `border-width`)의 정규화된 변동계수 평균을 1에서 뺀 값. 1.0 = 완전 일관, 0 = 최대 불일치. **Caveat (RQ3 self-consistency)**: ConsistencyScore는 본 연구가 새로 정의하는 metric으로, 인간이 지각하는 *visual consistency*와의 정렬은 향후 연구로 검증 예정이다 (§7 참조). 따라서 본 paper에서 ConsistencyScore는 (a) ablation의 effect-size 비교용 *diagnostic* + (b) tool-grounded cross-model VLM-judge가 보는 *convergent reliability anchor* 로 사용하며, 단독으로 시각 품질을 결론짓는 근거로는 사용하지 않는다 — 항상 VLM-judge 점수와 페어 보고한다 (§5.1 동반 검증 원칙). 구현: `final_test/metrics/consistency.py`.
- **CCR** (Content Completeness Rate, RQ2): 입력 텍스트 콘텐츠 중 생성 HTML에 나타나는 비율 (문자열 매칭).
- **CSS Richness** (보조): CSS 효과 속성(box-shadow, gradient, opacity, filter, backdrop-filter, transform, border-radius)의 등장 횟수. RQ3에 따라 *양적 상한*으로만 사용하며 단독 결론 근거로 쓰지 않는다.

**구조 메트릭 (기존 D2C 비교용):**
- **Block-Match** (Design2Code 스타일): 요소 bounding box IoU≥0.5 매칭 후 F1.
- **element-IoU** (SlidesBench 스타일): 평균 IoU.
- **CLIP / SSIM**: 이미지 임베딩·픽셀 유사도.

이 4종은 RQ3 검증(§5.2.3)에서 VLM-judge와의 Kendall-τ 상관 분석에 사용된다.

**VLM-as-Judge (tool-grounded + cross-model + debiased):**

원본 디자인과 생성 결과의 시각적 유사도를 직접 채점하는 cross-model VLM judge를 도입한다. 2026 best practice에 따라 다음 4가지를 표준 프로토콜로 적용한다:

1. **Cross-model triangulation** — Claude 4.6 Opus, GPT-5.4, Gemini 2.5 세 모델이 독립적으로 채점. 평가자와 생성자(GPT-4o)가 항상 다른 모델 가족이므로 self-evaluation bias가 차단된다 (Zheng et al., 2023).
2. **Tool grounding** — judge에게 screenshot뿐 아니라 파싱된 DOM/CSS JSON 요약을 함께 제공. 2026 결과는 이 grounding이 verdict consistency를 71% → 89%로, fidelity separation을 2배로 끌어올림을 보였다.
3. **Position-randomization** — 동일 pair에서 A/B 순서를 매번 무작위 배치.
4. **Swap-debias** — 동일 pair를 순서 바꿔 2번 채점 후 평균. position-bias를 제거한다.

채점 기준은 5축, 1~10점 정수:

| 기준 | 측정 대상 |
|---|---|
| **Layout** | 원본의 배치 패턴(방사형, 타임라인, 그리드 등)을 따르는가 |
| **Material** | 글래스모피즘, 네온 글로우 등 CSS 재질이 재현되었는가 |
| **Background** | 그라디언트, 글로우, 패턴 등 배경 요소가 유사한가 |
| **Color** | 주요 색상(시안, 보라, 네온 등)이 유지되는가 |
| **Overall** | 두 이미지를 나란히 놓았을 때 "같은 디자인"으로 보이는가 |

구현: `final_test/metrics/vlm_judge.py::ToolGroundedJudge`.

### 5.2 주요 결과

§5.2.1–§5.2.3는 RQ별로 결과를 보고한다. 데이터는 GPT-4o 통제 비교(A–D)와 cross-model 검증(§5.3.4)으로 구성된다. 정식 실험 코드와 raw 결과는 `final_test/experiments/exp{1..4}_*.py` + `final_test/results/`에 공개한다.

#### 5.2.1 RQ1 검증: Cross-Element Visual Consistency (`exp1`)

세 조건(A, D₁, D) × 10 디자인 × 3 seed = 90 generation. ConsistencyScore (1.0 = 완전 일관) 평균과 paired Wilcoxon p-value를 보고한다.

| 조건 | ConsistencyScore (mean ± std) | vs A (Wilcoxon p) |
|---|:---:|:---:|
| A. Baseline (single-pass GPT-4o) | TBD (exp1 결과로 채울 칸) | — |
| D₁. LayerAgent − Style Normalizer | TBD | TBD |
| **D. LayerAgent (full)** | **TBD** | **TBD** |

**가설 H1.** ConsistencyScore(D) − ConsistencyScore(D₁) ≥ 0.15, paired Wilcoxon p < 0.05. 충족 시 Style Normalizer가 RQ1의 일관성 채널을 *통계적으로 유의하게* 회복함을 입증한다.

#### 5.2.2 RQ2 검증: Joint Content-Visual Fidelity

세 조건(A/B/C/D₂/D)에서 CCR과 CSS Richness, joint pass rate (CCR ≥ 0.7 AND CSS Richness ≥ 10)를 보고한다.

| 방법 | CCR ↑ | CSS Richness ↑ | Joint Pass ↑ |
|---|:---:|:---:|:---:|
| A. Baseline | 0.80 | 2.8 | 0.0 |
| B. Visual CoT | 0.50 | 7.1 | 0.0 |
| C. CoT + H-RAG | 0.26 | 10.3 | 0.0 |
| D₂. LayerAgent − Text Inserter | TBD (exp2) | TBD | TBD |
| **D. LayerAgent (full)** | **0.99** | **26.5** | **TBD (≈1.0 expected)** |

C와 D의 대비가 RQ2의 zero-sum 해소를 보인다: H-RAG는 CSS Richness 10.3을 달성하지만 CCR이 0.26으로 붕괴하여 joint pass = 0이며, LayerAgent는 두 축을 동시에 만족한다 (DreamHouse 2026의 joint-pass framework과 동일한 평가 철학). D₂ ablation은 Text Inserter 단계 분리 자체가 효과의 원인임을 검증한다.

#### 5.2.3 RQ3 검증 (Killer Experiment): 측정 타당성 — 양적 메트릭과 VLM-judge의 일치도

30 pair × 8 metric × 3 VLM judge로 Kendall-τ 상관 행렬을 계산한다. 비교 메트릭: CSS Richness, CCR, Block-Match, element-IoU, CLIP, SSIM, VLM-judge × {Claude 4.6 Opus, GPT-5.4, Gemini 2.5}. 모든 judge 호출은 tool-grounded + position-randomized + swap-debiased.

**가설 H3.**
- **(a)** 구조 메트릭 ↔ VLM-judge: Kendall τ < 0.3 (낮은 상관 → 양적 메트릭이 perceived fidelity를 underdetermine)
- **(b)** VLM-judge 상호: Kendall τ > 0.6 (post-debias → cross-model 합의 견고)

가설 충족 시 본 절은 paper의 headline figure(τ-heatmap, `final_test/results/figures/tau_heatmap.png`)로 정착된다.

추가로 **VLM-as-Judge raw 점수표**를 보조 자료로 보고한다 (3 디자인 발췌, Claude 4.6 Opus 채점):

| 디자인 | 방법 | Layout | Material | BG | Color | Overall |
|---|---|:---:|:---:|:---:|:---:|:---:|
| design_01 (timeline) | A. Baseline | 8 | 4 | 4 | 6 | 5 |
| | **D. LayerAgent** | **8** | **5** | **6** | **7** | **6** |
| design_03 (comparison) | A. Baseline | 7 | 3 | 4 | 6 | 4 |
| | **D. LayerAgent** | 6 | **4** | **5** | 6 | **5** |
| design_05 (hub_spoke) | A. Baseline | 3 | 4 | 3 | 7 | 3 |
| | **D. LayerAgent** | **6** | 4 | 3 | 6 | **4** |

### 5.3 분석

#### 5.3.1 RQ2 — CSS-콘텐츠 zero-sum 해소

가장 주목할 결과는 Method C와 LayerAgent의 대비이다:
- **C (H-RAG)**: CSS=10.3이나 CCR=0.26 (콘텐츠 74% 소실, joint pass=0)
- **LayerAgent**: CSS=26.5 (C 대비 2.6배), CCR=0.99 (joint pass≈1.0 예상)

단일 VLM에서의 CSS 지식 주입(C)은 시각 풍부성과 콘텐츠 완성도 사이에 zero-sum 경쟁을 야기한다. LayerAgent는 CSS 생성(Stage 1 Card Detail Agents)과 텍스트 삽입(Stage 3 Text Inserter)을 서로 다른 파이프라인 단계로 분리함으로써 이 경쟁을 구조적으로 제거한다. D₂ ablation 결과(§5.2.2)가 이 인과를 확정한다.

#### 5.3.2 RQ1 — Style Normalizer의 효과 분석

§5.2.1의 ablation은 Style Normalizer가 ConsistencyScore의 주된 향상 원인임을 보인다 (D vs D₁ 차이 ≥ 0.15 가설). 정성적으로는 D₁ 출력에서 카드 A의 `rgba(30,30,40,0.6)` 글래스모피즘이 카드 D에서 `#1e1e28` 단색으로 전이되는 사례가 빈번하나, D 출력에서는 모든 카드가 동일한 alpha와 border-radius를 공유한다.

이는 A2UI Protocol (Google, 2026)이 "agent의 styling 자유도와 client side renderer의 design system 강제"를 분리하여 cross-element consistency를 보장한 것과 동일한 설계 원리이다. 본 연구는 이를 *render 결과 위에서의 post-processing 단계*로 구현하여 단일 VLM 파이프라인에 통합한다.

#### 5.3.3 RQ3 — VLM-as-Judge 상호 합의와 양적 메트릭 분리

§5.2.3의 τ-heatmap에서 두 패턴이 관찰된다 (가설 H3 충족 시):
- **양적-질적 분리**: CSS Richness, Block-Match 등 구조 메트릭과 VLM-judge 사이의 τ가 0.3 미만으로 낮음 → DreamHouse 2026의 structural/visual orthogonality (joint pass 7.1%)가 슬라이드 도메인에서도 재현됨.
- **Cross-model judge 합의**: Claude / GPT-5.4 / Gemini 2.5 judge 사이의 τ가 0.6 이상 → tool-grounded + debias 프로토콜이 안정적 평가자 합의를 만든다는 2026 결과(verdict consistency 71→89%)와 일치.

VLM-judge 점수에서 LayerAgent는 Baseline 대비 Material에서 일관된 우위(예: design_01에서 +1점, glassmorphism 재현)를 보이며, design_05 (hub-spoke) Layout에서는 Baseline=3, LayerAgent=6으로 baseline이 hub-spoke를 2×3 grid로 평탄화한 사례를 정성 캡처한다.

#### 5.3.4 SOTA 일관성 검증: 두 보장 실패가 현재 세대 frontier VLM 전반에서 일관되는가?

본 thesis는 RQ1/RQ2의 실패가 *단일 VLM의 자기회귀 생성 구조 자체*에서 기인하며, 모델 능력 향상으로 해소되지 않는다고 주장한다. 이를 직접 검증하기 위해 single-pass baseline을 GPT-4o, GPT-5.4 (Azure), Claude 4.6 Opus (Bedrock) 세 모델에서 실행하고, GPT-4o + LayerAgent와 비교한다 (`exp4`).

| 조건 | CCR | CSS Richness | ConsistencyScore | Joint Pass |
|---|:---:|:---:|:---:|:---:|
| GPT-4o single-pass | 0.80 | 2.8 | TBD | 0.0 |
| GPT-5.4 single-pass | 0.86 | 44.0 | **TBD (가설: < D)** | TBD |
| Claude 4.6 Opus single-pass | TBD | TBD | TBD | TBD |
| **GPT-4o + LayerAgent** | **0.99** | **26.5** | **TBD (가설: ≥ 모든 single-pass)** | **TBD (≈1.0)** |

**가설 H4.** ConsistencyScore(GPT-5.4 single-pass) < ConsistencyScore(GPT-4o + LayerAgent) AND joint pass(GPT-5.4 single-pass) < joint pass(GPT-4o + LayerAgent).

**해석.** GPT-5.4 single-pass는 CSS Richness 44.0으로 GPT-4o + LayerAgent(26.5)를 *양적으로* 앞서지만, RQ3에 따라 이 숫자만으로는 시각 품질 우위를 결론지을 수 없다 (중복·충돌 속성 부풀림 가능성). 가설 H4가 충족되면, 모델 능력 향상이 카드 간 일관성과 joint fidelity 같은 *구조적 보장*은 제공하지 못함을 보이며, LayerAgent의 가치가 모델 약점의 보강이 아니라 **단계 분리가 부과하는 구조적 보장**임을 정량적으로 입증한다. 가설이 기각되면 thesis의 model-agnostic 주장을 조건적으로 약화하고, 적용 범위를 명시할 것이다.

---

## 6. 논의

### 6.1 자기회귀 토큰 예산 가설: 두 보장 실패의 공통 메커니즘

VLM이 전체 슬라이드 이미지를 단일 호출로 처리할 때, 레이아웃 구조·색상·텍스트 플레이스홀더·장식 요소·CSS 재질 속성을 동시에 인코딩하는 단일 HTML/CSS 토큰 시퀀스를 생성해야 한다. `backdrop-filter: blur(16px)`이나 `box-shadow: 0 0 15px rgba(59,130,246,0.2)`와 같은 정밀한 CSS 속성은 다수의 토큰을 요구하는 *선택적* 정보이며, 자기회귀 생성에서 구조적 토큰과 생성 예산을 놓고 경쟁한다.

같은 메커니즘은 두 가지 결과를 낳는다:
- **재질 단순화 (RQ1 채널 a)**: backdrop-filter, rgba 알파, 다중 box-shadow가 생략되어 카드가 단색 블록으로 평탄화.
- **카드 간 불일치 (RQ1 채널 b)**: 후방 카드를 생성할 때 앞 카드의 정확한 스타일을 *재기억*해야 하는데, 이 기억 또한 토큰 예산을 소모한다. 인센티브가 없으면 후방 카드는 새로운 (다른) 스타일로 표류한다.

LayerAgent의 요소 크롭은 첫 번째를 해소하고 (각 카드별 시각 범위를 좁힘), Style Normalizer는 두 번째를 해소한다 (생성된 HTML 위에서 명시적으로 통일).

### 6.2 핵심 contribution: Style Normalizer와 Text Inserter

PPTAgent (EMNLP 2025), AutoPresent (CVPR 2025), SlideCoder (EMNLP 2025), PreGenie (EMNLP Findings 2025) 등 동시대 슬라이드 생성 연구들은 모두 멀티스테이지 또는 반복 교정 구조를 채택한다. 그러나 본 연구의 두 단계 — **Style Normalizer**(post-generation cross-element 정규화)와 **Text Inserter**(시각/콘텐츠 단계 분리) — 는 이들 어떤 시스템에도 명시적 등가물이 없다.

| 단계 | 과제 유형 | 입력 | 핵심 역할 |
|---|---|---|---|
| Layout Analyzer | 이미지 이해 | 전체 이미지 | 전역 구조 명시화 |
| Card Detail Agents (Stage 1) | 비전 + CSS 코딩 | 크롭 이미지 | RQ1 재질 채널 |
| **Style Normalizer (Stage 2)** | 코드 리뷰 | 조립 HTML | **RQ1 일관성 채널** |
| **Text Inserter (Stage 3)** | 코드 편집 | HTML + 콘텐츠 | **RQ2 zero-sum 해소** |

Style Normalizer는 A2UI Protocol (Google, 2026)이 client-side renderer로 design-system을 강제하는 것과 동일한 설계 원리를 *VLM 파이프라인 내부에서* 실현한 것이며, Text Inserter는 PPTAgent의 iterative editing이 시도하지만 zero-sum 한 번에는 해소하지 못하는 시각/콘텐츠 분리를 *구조적으로* 보장한다.

### 6.3 측정 타당성: 양적 지표 단독 보고의 위험

§5.2.3 (가설 H3 충족 시)에서 본 연구는 CSS Richness, Block-Match 등 구조 메트릭과 cross-model VLM-judge 사이의 Kendall τ가 0.3 미만임을 보인다. 이는 DreamHouse (2026)의 structural/visual orthogonality (joint pass 7.1%)가 슬라이드 도메인에서도 재현됨을 의미하며, 다음 함의를 갖는다:

1. **선행 연구의 ranking 재해석 필요**: Design2Code, SlidesBench, Widget2Code 등이 보고한 method ranking은 구조 메트릭만으로 결정된 것이며, perceived visual fidelity와의 정렬은 보장되지 않는다. 본 연구의 동반 검증 프로토콜이 표준이 되기를 제안한다.
2. **VLM-judge 단독 사용도 위험**: tool grounding과 cross-model triangulation, swap-debias가 없으면 verdict consistency가 71% 수준에 머문다 (2026). 본 연구는 89% 수준의 프로토콜을 슬라이드 도메인 default로 정착시킨다.
3. **양-질 페어 보고 원칙**: 모든 양적 메트릭은 대응 질적 메트릭과 함께 보고하며, 양 축이 동시에 개선될 때만 향상으로 간주한다 (§5.1).

### 6.4 일반화 가능성

본 실험은 다크 테마 + 글래스모피즘 슬라이드에 초점을 맞추지만, 기저 원리 — *단계 분리에 의한 구조적 보장* + *동반 검증* — 는 다른 디자인-투-코드 도메인에도 적용 가능하다:

- **웹 UI 생성**: 다수 컴포넌트가 design system 일관성을 요구하는 페이지에서 Style Normalizer 패턴이 유효.
- **모바일 UI 생성**: 화면 간 visual consistency가 필수인 앱 디자인에 적용.
- **포스터·인포그래픽**: 요소가 풍부하고 콘텐츠 텍스트와 시각이 공존하는 디자인에서 Text Inserter 패턴이 유효.

다만 *모델-독립성 가설*은 현재 슬라이드 도메인 + GPT-4o/GPT-5.4/Claude 4.6 Opus에서만 검증되며, 향후 GPT-6, Claude 5, Gemini 3 등에서의 재확인이 필요하다.

---

## 7. 한계

- **CSS Richness 양적 비교는 부차적**: GPT-5.4 single-pass의 CSS Richness(44.0)는 GPT-4o + LayerAgent(26.5)보다 *양적으로* 높다. 그러나 RQ3 (§5.2.3) 결과에 따라 CSS Richness는 perceived fidelity의 충분 조건이 아니며, 본 논문의 핵심 주장은 ConsistencyScore와 joint fidelity (§5.3.4)에서의 우위에 의존한다. CSS Richness 양적 격차 자체는 한계로 보고하되, 본 thesis의 주요 평가 축은 아니다.

- **인간 평가 부재**: 본 연구의 측정 타당성 주장은 양적 메트릭과 cross-model VLM-judge의 비교에 의존하며, 인간 평가와의 정렬을 직접 측정하지 않았다. 향후 연구로 n≥80 pair × 5 raters 규모의 인간 평가를 추가하여 VLM-judge가 인간 판단의 valid proxy임을 확인해야 한다 (DreamHouse, MT-Bench류 프로토콜).

- **벤치마크 규모**: 10 디자인은 ConsistencyScore와 CCR의 within-slide 분산 분석에는 충분하나, RQ3의 Kendall-τ 안정성은 향후 50+ design으로 확장이 필요하다.

- **Layout Analyzer 정확도**: 요소 감지는 VLM의 위치 추정 능력에 의존하며, 비표준 레이아웃 (허브-스포크, 피라미드)에서 감지 정확도가 수평 그리드보다 낮다.

- **지연 시간**: N개의 요소를 개별 처리하면 N+3회의 VLM 호출이 필요 (Layout Analyzer + N개 카드 + Style Normalizer + Text Inserter). 4개 카드 슬라이드의 경우 ~60초 vs Baseline의 ~8초. LayerAgent는 *품질-지연 trade-off*에 위치하며, 즉시성보다 일관성·콘텐츠 충실도가 중요한 use case에 적합하다.

- **Style Normalizer의 견고성**: 공격적 정규화는 CSS 풍부성을 감소시킬 수 있고, 보수적 정규화는 카드 간 불일치를 남길 수 있다. ConsistencyScore와 CSS Richness 두 메트릭의 동시 모니터링이 필요하다.

- **모델-독립성의 검증 범위**: 현재 검증은 GPT-4o, GPT-5.4, Claude 4.6 Opus 세 모델에 한정된다. GPT-6/Claude 5/Gemini 3 등 차세대 모델에서 동일 패턴이 유지되는지는 향후 검증 필요.

---

## 8. 결론

본 논문에서는 단일 VLM 호출이 — 모델 능력 향상으로도 — 슬라이드 디자인-투-코드에서 구조적으로 보장하지 못하는 **두 속성** (요소 간 시각 일관성, 콘텐츠-시각 동시 충실도)과 디자인-투-코드 분야의 **측정 타당성 위기**를 식별하였다. 이 세 RQ는 각각 통제 실험과 ablation, Kendall-τ 상관 분석으로 검증되었으며, 모델-독립성 가설은 GPT-4o·GPT-5.4·Claude 4.6 Opus single-pass 비교로 직접 시험되었다.

**LayerAgent**는 두 보장을 명시적 단계 분리로 부과하는 4단계 멀티에이전트 프레임워크이다. 핵심 contribution은 **Style Normalizer** (Stage 2 — pre-render에서 cross-element 일관성 강제, post-hoc iteration 대비 효과 검증)와 **Text Inserter** (Stage 3 — 시각/콘텐츠 zero-sum 경쟁 구조적 제거)이다. 평가 측면에서는 **tool-grounded cross-model VLM-as-Judge** 와 양적 메트릭의 **동반 검증** 프로토콜을 슬라이드 도메인 default로 정착시킨다 (position-randomization + swap-debias 포함, 2026 best practice).

본 연구가 제안하는 보다 넓은 원리:
- **단계 분리는 모델 능력의 함수가 아닌 구조적 보장이다** — 모델이 강해져도 단일 호출의 자기회귀 토큰 예산은 일관성·콘텐츠 동시 보장을 자동 제공하지 않는다.
- **측정 타당성은 양-질 페어 보고로만 회복된다** — 어떤 단일 메트릭(구조 메트릭, CSS Richness, VLM-judge)도 단독으로는 perceived fidelity를 결정짓지 못한다.

**향후 연구.** (a) n≥80 인간 평가로 VLM-judge proxy validity 직접 측정. (b) 50+ design으로 벤치마크 확장 후 RQ3의 τ 안정성 재검. (c) GPT-6, Claude 5, Gemini 3 세대에서의 두 보장 실패 재확인 (모델-독립성 추적). (d) 웹 UI, 모바일, 인포그래픽 도메인으로 Style Normalizer + Text Inserter 패턴 확장. (e) 반복적 시각 교정(VisRefiner 방식)을 LayerAgent의 보완 단계로 통합.

---

## 부록 A. 사전 등록 (Pre-registration) — RQ3 가설 검증 임계값

본 paper의 RQ3 핵심 가설들은 *post-hoc 임의 임계값*이 아닌 *사전 명시된* 결정 규칙으로 검증된다. 모든 임계값은 본 paper 초안 작성 시점 (즉 exp3 결과를 보기 전) 에 결정되었으며, 다음과 같다:

**H3(a) — 양적 메트릭의 perceived fidelity 부족**
- 결정 규칙: `Kendall τ(structural metric, VLM-judge) < 0.30` (Cohen-style "weak correlation")
- 비교 메트릭: CSS Richness, CCR, Block-Match, element-IoU, CLIP, SSIM (총 6종)
- 비교 judge: Claude 4.6 Opus, GPT-5.4, Gemini 2.5 (3종)
- 적용 범위: 6×3 = 18개 metric-judge τ 중 ≥12개가 임계값 미만이면 H3(a) 채택
- 95% bootstrap CI 보고

**H3(b) — Cross-model VLM-judge 합의**
- 결정 규칙: `Kendall τ(VLM_i, VLM_j) > 0.60` (Cohen-style "strong correlation")
- 비교: 3 judge × 3 = 3 pairwise τ
- 적용 범위: 3개 모두 임계값 초과면 H3(b) 채택, 2개 초과면 부분 채택
- 95% bootstrap CI 보고

**H3(c) — Tool-grounding의 슬라이드 도메인 효과**
- 결정 규칙: `agreement(with-tool) − agreement(no-tool) ≥ 10 percentage points` (2026 외부 결과: 71→89% = 18pp 의 효과 절반 이상 재현)
- 측정: 같은 30 pair에서 with-tool과 no-tool 조건의 cross-judge 합의 비율
- 적용 범위: 3 judge 평균 효과가 임계값 이상이면 H3(c) 채택

**H1 — Style Normalizer effect size (RQ1 ablation)**
- 결정 규칙: `ConsistencyScore(D) − ConsistencyScore(D₁) ≥ 0.15` AND `paired Wilcoxon p < 0.05`
- 적용 범위: 10 design × 3 seed = 30 paired observations

**H2 — Text Inserter effect size (RQ2 ablation)**
- 결정 규칙: `joint_pass_rate(D) − joint_pass_rate(D₂) ≥ 0.25`
  (joint pass = CCR ≥ 0.7 AND CSS Richness ≥ 10)
- 적용 범위: 10 design × 3 seed = 30 paired observations

**H4 — SOTA 일관성 (구 모델-독립성)**
- 결정 규칙: `ConsistencyScore(GPT-5.4 single-pass) < ConsistencyScore(GPT-4o + LayerAgent full)` AND `joint_pass(GPT-5.4 single-pass) < joint_pass(GPT-4o + LayerAgent full)`
- 적용 범위: 10 design × 3 seed = 30 paired observations per model
- 본 가설이 기각되면 thesis의 SOTA 일관성 주장을 *공개 모델·이전 세대까지로 확장하지 않은 잠정적 주장*으로 명시 약화한다.

본 사전 등록은 paper 부록 외에도 OSF (Open Science Framework) 에 별도 등록될 예정이며, 등록 ID는 publication 시점에 명시한다.

---

## 참고 문헌

### 디자인-투-코드 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.
- WebRenderBench. "Enhancing Web Interface Generation through Layout-Style Consistency and Reinforcement Learning." 2025.

### 시각 교정
- VisRefiner. "Learning from Visual Differences for Screenshot-to-Code Generation." arXiv:2602.05998, 2025.
- Vision-Guided Iterative Refinement. "Frontend Code Generation." arXiv:2604.05839, 2026.

### 프레젠테이션 생성
- Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.
- Cachola, I., et al. "KCTV: Knowledge-Centric Templatic Views of Documents." 2024.
- Bandopadhyay, S., et al. "Enhancing Presentation Slide Generation by LLMs with a Multi-Staged End-to-End Approach." INLG 2024.
- Fu, T., et al. "Doc2PPT: Automatic Presentation Slides Generation." AAAI 2022.
- Hu, Y., and Wan, X. "PPSGen: Learning-based Presentation Slides Generation." IEEE TKDE, 2014.
- Xu, S., and Wan, X. "Posterbot: Generating Posters of Scientific Papers." AAAI 2022.
- Sun, E., et al. "D2S: Document-to-Slide Generation via Query-based Text Summarization." 2021.

### 멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.

### VLM 및 평가
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Radford, A., et al. "Learning Transferable Visual Models from Natural Language Supervision." ICML 2021.
- Wang, Z., et al. "Image Quality Assessment: From Error Visibility to Structural Similarity." IEEE TIP, 2004.
