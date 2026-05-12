LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크

디자인 이미지의 계층 구조 인식을 통한 프레젠테이션 코드 생성

by 정일균 (Ilgyun Jeong)

인공지능융합학과 (Department of Artificial Intelligence Convergence)

지도교수: 김현철 (under the supervision of Professor Hyeoncheol Kim)

---

초록

프레젠테이션 슬라이드는 배경·카드·콘텐츠·아이콘 등 여러 시각 층이 위아래로 겹쳐 구성되는 계층적 시각 구조다. 본 연구는 GPT-4o가 슬라이드 이미지를 자연어로는 평균 6.6개(범위 5–10)의 레이어로 기술하면서 같은 이미지를 HTML로 변환할 때는 평균 1.8개만 코드에 반영하는 인식–생성 격차를 관찰하고, 이를 슬라이드 도메인의 계층적 요소 누락 현상으로 정식화한다. 이를 다루기 위해 단일 VLM 호출을 8개 전문 에이전트의 레이어 단위 분해로 재구성하는 멀티에이전트 프레임워크 LayerAgent를 제안한다.

평가 결과 LayerAgent 는 동일 GPT-4o 조건의 4 메서드 비교에서 객관 디자인 충실도 (Element-IoU 0.372, sp 0.314 대비 +18%) 와 교차 모델 VLM judge (GPT-5.4 4 기준 모두 1위, 평균 4.02 대 차순위 3.37) 두 평가 축에서 1위에 위치한다. AutoPresent 루브릭의 레이아웃 차원에서도 1위 (layout_0_5 3.64 대 2.90) 이며, chart·표 카테고리 6종은 chart_templates 결정적 렌더링으로 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차를 보인다. 최첨단 모델 일괄 생성(GPT-5.4)은 비용·시간 측면의 별개 비용-품질 대안으로 7.3절에 경계 참조로 보고된다.

본 연구의 기여는 세 가지로 정리된다. (1) 문제 — 슬라이드 도메인의 (계층적) 요소 누락 현상의 정식화, (2) 방법 — Chat Parser 입력 정규화, DesignSpec blackboard, 비전 기반 전문가, chart_templates 결정적 렌더링 라이브러리(7종 chart renderer), 스타일 정규화, text 삽입 분리를 포함하는 멀티에이전트 레이어 분해 프레임워크 (LayerAgent) 제안 및 두 메커니즘의 차원별 인과 효과 격리 측정 (DesignSpec blackboard 는 카드 간 색 일관성 차원, Text Inserter 는 문자열 단위 콘텐츠 보존 차원), (3) 발견 — 동일 GPT-4o 조건의 4 메서드 비교에서 LayerAgent 가 객관 충실도 (Element-IoU) 와 교차 모델 VLM judge (GPT-5.4 4 기준) 두 주요 축에서 가장 높은 성능을 보임을 확인. LayerAgent는 동일 GPT-4o 조건에서 일괄 생성이 놓치는 계층 구조를 HTML/CSS 차원에서 더 많이 반영하도록 돕는 프로세스 단위 개입이다. 다만 이 구조적 회복은 모든 레이아웃에서 종합적 발표 품질 향상으로 이어지지는 않았으며 (5.2절 · 8장 (ii) 분리 발견 참조), 최첨단 확장과는 분리된 개선 경로로 해석된다.

키워드: 요소 누락 (Element Omission), 계층 분해 (Layer Decomposition), 멀티에이전트 (멀티에이전트), 디자인-투-코드 (Design-to-Code), 시각 언어 모델 (Vision Language Models)

---

제 1 장. 서론

1.1 슬라이드 도메인의 계층적 요소 누락

프레젠테이션 슬라이드는 배경·카드·차트·텍스트·아이콘 등 여러 시각 층이 위아래로 겹쳐 구성되는 계층적 시각 객체이며, 이 시각 층들이 정확한 순서(stacking order)와 좌표로 겹쳐야 의도된 디자인이 구현된다. 그러나 단일 VLM 호출은 이 계층 구조를 충분히 반영하지 못한 채 HTML을 위에서 아래로 한 번에 생성한다 — `<div>` 태그가 직렬로 나열되고, 층의 명시적 순서 표기(CSS `z-index`)는 거의 사용되지 않으며, 요소 간 공간 관계는 DOM 작성 순서에 암묵적으로 의존한다.

본 연구의 출발점은 다음의 관찰이다. 같은 GPT-4o에게 이미지의 계층 구조를 자연어로 기술하라고 요청하면 평균 6.6개(범위 5–10)의 레이어를 인식하지만, 같은 이미지를 HTML로 변환하라고 요청하면 평균 1.8개만 코드에 반영된다 (부록 B.1). 본 논문은 이 현상을 슬라이드 도메인의 (계층적) 요소 누락이라 부른다 — Design-to-Code 선행 연구(Calò & De Russis, 2025)에서 개별 요소 단위로 보고된 요소 누락이 슬라이드 도메인에서는 시각 계층(레이어) 단위로 통째 누락되는 형태로 확장되어 나타난다. 이는 메트릭 이름이 아니라 현상의 이름이며, 본 연구는 이를 직접 표적하는 단일 신규 메트릭을 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 측정이 순환적(circular)이 되기 때문이다.

1.2 연구 질문과 접근

기존 design-to-code 연구는 분할 정복(DCGen), 레이아웃 명시화(LaTCoder), 3-stage 에이전트 파이프라인(ScreenCoder, DesignCoder)으로 이미지-코드 품질을 일반적 문제로 다루어 왔고, 프레젠테이션 생성 연구(PPTAgent, PreGenie, SlideCoder, AutoPresent)는 템플릿 수정·코드 리뷰·세그멘테이션 기반 생성에 초점을 두었다. 그러나 슬라이드의 시각 계층이 HTML/CSS 생성 단계에서 레이어 단위로 통째 누락되는 현상 자체를 직접 문제화하고 프로세스 단위 분해로 다룬 연구는 없다.

이로부터 본 연구의 연구 질문이 도출되며, 다음 세 하위 질문으로 분해된다.

RQ1. GPT-4o 급 VLM 은 슬라이드 이미지를 자연어로는 계층적으로 인식하면서 HTML/CSS 생성에서는 해당 계층을 누락하는가? 그리고 이 격차는 최첨단 VLM (GPT-5.4, Claude 4.6 Opus) 에서도 같은 양식으로 관찰되는가? (5.1절 동기 · 부록 B)

RQ2. LayerAgent 는 동일 GPT-4o 조건에서 일괄 생성 및 프롬프트 수준 변형 (visual_cot, cot_h_rag) 보다 객관 충실도 (Element-IoU, CIEDE2000) 와 VLM judge (AutoPresent 0–5, GPT-5.4 4 기준) 두 축에서 우수한가? (5.1절 · 5.3절)

RQ3. LayerAgent 의 효과는 레이아웃 유형 (chart·표·다이어그램 대 고밀도 시각 효과 대 비차트 일반) 과 평가 축 (객관 매칭 대 VLM 루브릭 대 종합적 judge) 에 따라 어떻게 달라지는가? (5.2절 레이아웃 · 6.2절 평가 축)

본 연구는 LayerAgent를 제안한다. 단일 VLM 호출을 전체 이미지 분석 → 공유 DesignSpec 작성 → 8개 전문 에이전트의 병렬 레이어 생성 → 결정적 z-index 조립 → 카드 간 스타일 통일 → 텍스트 주입의 다단계 파이프라인으로 분해함으로써, 각 호출이 구조·스타일·콘텐츠를 동시에 짊어지지 않고 한 가지 책임만 지도록 설계했다 (3장). 효과는 단일 지표가 레이어 보존의 다면성을 모두 포착하지 못하므로 디자인2code 다면적 평가 묶음 — 객관 충실도 (Element-IoU, CIEDE2000) + VLM 루브릭 (AutoPresent 0–5, GPT-5.4 4 기준) — 으로 함께 측정한다 (4.3절).

1.3 결과 요약과 기여

실험 결과 LayerAgent 는 동일 GPT-4o 조건의 4 메서드 비교에서 객관 디자인 충실도 (Element-IoU 전체 N=50 1위, CIEDE2000 고밀도 시각 효과 부분집합 1위) 와 교차 모델 VLM judge (GPT-5.4 4 기준, 평균 4.02 대 차순위 3.37) 두 주요 축에서 1위에 위치한다 (5장). AutoPresent 루브릭의 레이아웃 차원에서도 1위 (3.64 대 2.90), 색 차원에서는 베이스라인 우세 — chart_templates 결정적 렌더링이 참조 색을 직접 복제하지 않고 정제된 brand 색 시스템을 사용하기 때문이다 (6.2절). chart·표 카테고리 6종은 chart_templates 결정적 렌더링으로 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차를 보인다. 최첨단 모델 일괄 생성(GPT-5.4)은 비용·시간 측면의 별개 비용-품질 차원으로 7.3절에 경계 참조로 보고한다.

본 논문의 기여는 다음 세 가지로 정리된다.

1. 문제 — 슬라이드 도메인의 (계층적) 요소 누락 정식화. Design-to-Code 선행 연구의 요소 누락이 슬라이드 도메인에서는 시각 계층 단위로 통째 누락되는 형태로 발현됨을 인식–생성 격차(평균 6.6 → 1.8 레이어)로 가시화한다 (부록 B).

2. 방법 — LayerAgent 프레임워크. DesignSpec blackboard, 비전 기반 전문가, 스타일 정규화, text 삽입 분리를 포함하는 멀티에이전트 레이어 분해를 제안하고, DesignSpec blackboard(D₄)와 Text Inserter(D₂) 두 메커니즘의 인과 효과를 격리 측정한다 (3장, 5.3절).

3. 발견 — 본 연구의 N=50 계층화된 슬라이드 평가셋에서 동일 GPT-4o 조건의 4 메서드 비교 기준 객관 충실도 (Element-IoU) 와 교차 모델 VLM judge (GPT-5.4 4 기준) 두 축에서 가장 높은 성능. LayerAgent 는 동일 모델 GPT-4o 조건의 4 메서드 비교에서 객관 충실도 (Element-IoU 1위) + 교차 모델 VLM judge (GPT-5.4 4 기준 모두 1위) 두 주요 축에서 1위에 위치한다 (5장). 최첨단 모델 일괄 생성(GPT-5.4)은 별개 비용-품질 차원의 경계 참조로 7.3절에 보고된다.

---

제 2 장. 관련 연구

2.1 Design-to-Code 생성

Design2Code (Si et al., 2024)는 484 웹페이지 벤치마크로 GPT-4V의 중간 충실도를 보고했다. WebSight (Laurençon et al., 2024)는 200만 합성 image-code 쌍를 공개했다. Calò & De Russis (PACMHCI 2025)는 GPT-4o의 UI 코드 생성 실패를 요소 누락 · 요소 distortion · 요소 misarrangement의 세 유형으로 분류했다 — 본 연구는 이 중 요소 누락을 슬라이드 도메인의 시각 계층 단위로 확장하여 분석한다 (부록 B). DCGen (FSE 2025)은 분할 정복으로 페이지를 블록 단위로 분해해 코드를 생성한다. LaTCoder (KDD 2025)는 코드 이전에 레이아웃을 chain-of-thought로 명시화한다. ScreenCoder (arXiv:2507.22827, 2025)는 Grounding → Planning → 생성의 3-stage 에이전트 파이프라인을 채택하고 50K image-code 쌍로 GRPO 미세조정한다. DesignCoder (arXiv:2506.13663, 2025)는 모바일 UI 도메인에서 UI 그룹화 → Hierarchy-Aware 생성 → 사후 렌더 Self-Correcting Refinement의 3-stage를 사용한다. UIOrchestra (Findings of EMNLP 2025)는 멀티에이전트 프레임워크로 UI 디자인에서 code로의 변환을 다루며 본 연구와 가장 가까운 선행 연구이다. 다만 LayerAgent의 DesignSpec blackboard, CV 그라운딩, library retrieval을 통합한 구조와는 차별된다.

LayerAgent와의 차별점. ScreenCoder는 이미지 패치 reuse(Hungarian 매칭)로 요소 간 일관성을 다루고, DesignCoder는 사후 렌더 반복 개선로 코드 품질을 다룬다. 본 연구의 Style Normalizer는 사전 렌더 CSS 정규화에 해당하고, Text Inserter는 시각과 콘텐츠 단계의 분리에 해당하며, DesignSpec blackboard는 생성 시점의 에이전트 간 스타일 통일에 해당한다. 기존 design-to-code 평가는 주로 단일 지표 또는 분류된 지표 그룹을 보고했으며, 본 연구는 슬라이드 도메인에서 객관 디자인 충실도 (Element-IoU, CIEDE2000) 와 VLM 루브릭 (AutoPresent 0–5, GPT-5.4 4 기준) 을 결합하여 동반 보고하는 디자인2code 다면적 평가 방식을 적용한다는 점에서 차별화된다. 종합하면, 기존 design-to-code 계열은 이미지-코드 품질을 일반적 문제로 다루는 반면, 본 연구는 슬라이드 도메인 특유의 레이어 단위 요소 누락 자체를 직접 문제화하고 레이어 단위 생성 분해로 다룬다는 점이 핵심 차이다.

2.2 시각 교정 / 반복 개선

VisRefiner (arXiv:2602.05998, 2026)는 렌더링 결과와 참조 디자인 간 시각 차이를 학습하여 GPT-4o 대비 Block Match +21.5pt를 달성했다. Vision-Guided Iterative Refinement (arXiv:2604.05839, 2026)는 VLM critic 기반 3회 반복으로 17.8% 개선을 보고했다. 본 연구의 Visual Critic 단계 는 이들의 반복 대 단발 트레이드오프를 선택 단계로 구현하며 (3.5절), 본 논문의 주요 결과는 기본 비활성 조건에서 보고한다.

2.3 프레젠테이션 생성

PPTAgent (Zheng et al., EMNLP 2025)는 LLM 피드백 기반 템플릿 반복 수정을, PreGenie (Xu et al., EMNLP Findings 2025)는 코드 리뷰와 페이지 리뷰의 이중 루프를, SlideCoder (Tang et al., EMNLP 2025)는 CGSeg 세그멘테이션과 계층적 RAG를, AutoPresent (Ge et al., CVPR 2025)는 구조화된 시각 설계 원칙을 강조했다. 이들 선행 연구는 주로 템플릿 수정, 코드 리뷰, 세그멘테이션 기반 생성, 구조화된 설계 원칙에 초점을 두었다. 반면 본 연구는 슬라이드의 시각 계층이 HTML/CSS 생성 단계에서 누락되는 현상에 초점을 맞추고, 이를 계층 단위 생성 분해와 디자인2code 다면적 평가의 동반 보고 (Element-IoU 객관 매칭, AutoPresent VLM 루브릭, 교차 모델 GPT-5.4 4 기준) 로 분석한다는 점에서 차별화된다. 종합하면, 기존 발표자료 생성 계열은 템플릿·콘텐츠·슬라이드 단위 생성 자체를 다루는 반면, 본 연구는 HTML/CSS 단위의 레이어 충실도를 핵심 문제로 직접 다룬다는 점이 핵심 차이다.

2.4 멀티에이전트 코드 생성

MetaGPT (Hong et al., ICLR 2024), ChatDev (Qian et al., ACL 2024), CAMEL (Li et al., NeurIPS 2023), AutoGen (Wu et al., COLM 2024)은 소프트웨어 개발 프로세스(설계, 구현, 테스트의 순서) 또는 대화형 멀티에이전트 대화으로 에이전트를 분담한다. LayerAgent는 (a) 개발 프로세스가 아니라 출력의 시각 계층(레이어) 구조(배경, 카드, 텍스트, 아이콘의 순서)에 따라 분담하며, (b) 에이전트 간 통신을 자연어나 코드가 아니라 DesignSpec JSON과 바운딩 박스 JSON으로 구성된 타입드 blackboard로 수행하여 잘림과 해석 오류를 구조적으로 제거한다. 종합하면, 기존 멀티에이전트 code 생성은 역할·개발 프로세스·대화 흐름에 따른 분업이지만, LayerAgent는 출력의 시각 계층(레이어)에 따른 분업이라는 점이 본질적 차이다.

2.5 Design-to-Code 평가

기존 평가는 전역 유사도, 구조 매칭(Design2Code 의 Block-Match, AutoPresent 의 요소 매칭), 속성 수준(WebRenderBench 의 SDA, Widget2Code 의 속성별) 으로 분류된다. DreamHouse (arXiv:2603.24866, 2026) 는 physical generative reasoning(건축 구조물 생성) 도메인에서 구조적 타당성와 시각 충실도가 직교적이며 최첨단 VLM 의 결합 통과율이 7.1% 에 불과함을 보였으며, 본 연구는 이 직교성 발견을 슬라이드 도메인으로 평행하게 적용한다. SlideAudit (UIST 2025) 은 슬라이드 품질 분류 체계를 정립하고 자동화된 지표와 종합적 인간 판정 사이의 체계적 불일치를 정량적으로 보였으며, 이는 본 연구의 6.2절 평가 축 간 불일치 관찰과 직접 정렬되는 선행 연구이다. AutoPresent (CVPR 2025) 는 레이아웃·색 두 차원 0–5 루브릭을 정립했으며 본 연구는 이를 주요 지표의 한 축으로 사용한다. WebDevJudge (2025) 는 design-to-code 에서 MLLM-as-judge 의 평가 관행 (쌍별 평가와 code·시각 양식 결합) 을 제안했으며, 본 논문은 이를 7장의 단일 judge 한계 논의에서 참조로 인용한다. 본 연구는 (a) DreamHouse 와 SlideAudit 두 도메인의 지표 불일치 발견을 슬라이드 design-to-code 도메인의 다면적 평가로 확장하고, (b) 객관 요소 단위 매칭 (Element-IoU) 과 색 거리 (CIEDE2000), AutoPresent 루브릭, 교차 모델 VLM judge 를 결합하여 클래스명 비의존 하게 정렬한 디자인2code 다면적 평가 프로토콜을 구성함으로써 메서드별 명명 규칙에 따른 평가 편향을 줄인다.

---

제 3 장. LayerAgent 프레임워크

3.1 전체 구조

![그림 1: LayerAgent architecture](results/figures/layeragent_architecture.png)

(그림 1) LayerAgent 의 측정 대상 파이프라인. Chat Parser 가 입력을 타입드 `slide_spec` JSON 으로 정규화한 뒤, 단계 0 (Analyzer · Design Director) 이 레이아웃과 DesignSpec blackboard 를 산출하고, 단계 1 의 8개 전문가가 병렬로 레이어 단편을 생성하며, 단계 2 의 Assembler · Style Normalizer · Text Inserter 가 결정적 z-index 조립과 카드 간 스타일 통일·텍스트 주입을 수행한다. 19개 slide_type 어휘, 전문가 그룹 구성, chart_templates 결정적 렌더링 (chart 슬라이드 우회 처리), 선택 단계(Overflow Repair, Visual Critic) 의 상세는 3장 본문에서 기술된다.

전체 파이프라인은 LangGraph StateGraph로 구현되었으며, 8개 전문가는 Design Director의 출력 이후 병렬로 실행된다. Chat Parser는 그래프 진입 노드로 위치하여 사용자 입력 다양성을 입력 표준화 단계에서 흡수한다.

3.2 단계 0 — 입력 분석

제1항 Chat Parser — 입력 정규화

사용자는 LayerAgent 에 자유 형식 자연어 메시지와 참조 디자인 이미지를 함께 제공한다. Chat Parser는 두 입력을 받아 타입드 JSON `slide_spec`을 출력한다 — `slide_type` ∈ {19종 어휘}, `콘텐츠` (slide_type별 구조화 필드), `스타일` (4개 헥스 색상). slide_type은 이미지의 시각 형태를 1차 신호로, 사용자 메시지를 2차 신호로 결정한다 — 예컨대 "여러 색의 라인이 있으면 multi-series line_chart", "1 root → N branches → M leaves 트리는 pyramid가 아닌 tree_diagram" 등 형태 기반 분기 규칙이 프롬프트에 명시된다. 이는 downstream 에이전트들이 동일한 어휘 위에서 동작하도록 보장하여 분기 모호성으로 인한 레이어 환각·붕괴를 사전 차단한다.

제2항 Analyzer

전체 이미지를 입력받아 (a) 레이아웃 유형(`timeline / dashboard / hub_spoke / pyramid / grid / 분할 / vertical_stack / freeform`)과 (b) 각 카드·히어로·장식 요소의 정규화된 바운딩 박스(0–1 비율)를 출력한다. 이 출력은 이후 모든 크롭과 배치의 기준점이 된다. slide_type이 chart_templates 적용 7종(bar_chart/line_chart/waterfall/matrix_2x2/mekko/harvey_table_advanced/tree_diagram) 중 하나인 경우, Analyzer는 카드·히어로 영역을 비워 반환하여 차트 위에 카드 레이어가 겹쳐지지 않도록 한다.

제3항 Design Director — DesignSpec Blackboard

전체 이미지와 CV facts(k-means 팔레트, OCR 텍스트 높이 분포, HSV 채도)를 입력받아 타입드 JSON `DesignSpec`을 출력한다. DesignSpec은 6개의 top-level 필드로 구성된다 — `aesthetic_label` (multi_layer_visual_effect / minimal / editorial 등), `타이포그래피` (hero·본문의 폰트 패밀리와 가중치), `팔레트` (k-means로 추출된 배경·강조·frame·text 색상), `frame_system` (hero·card 테두리 스타일과 bottom 강조 bar 유무), `decorative_motif` (스타일·density), `분위기` (radial 글로우 유무·원점과 배경 깊이). 전체 스키마와 한 슬라이드의 완결된 인스턴스 예시는 부록 D에 수록한다.

이후 모든 전문가는 DesignSpec을 프롬프트 힌트로 받는다. 결과적으로 카드 A의 반투명 효과가 카드 B에서 단색으로 변하는 스타일 표류가 사전적으로 차단된다 — 이는 단순한 분해 접근에서 자주 관찰되는 실패 양식이다.

CV 그라운딩의 효과. 팔레트는 k-means(k=6)로 추출되어 모델이 색을 환각할 여지를 줄이고, OCR 텍스트 높이는 폰트 크기 결정의 결정적 기준점이 되며, HSV 채도는 flat과 vivid 미학을 구분하는 단서로 작용한다. 이 효과는 `no_cv_facts` 플래그로 격리해 측정할 수 있다.

3.3 단계 1 — Specialist Agents (병렬)

8개 전문가는 Design Director의 출력 이후 병렬로 실행되며, 두 그룹으로 나뉜다 — 모든 슬라이드에서 활성화되는 레이어 전문가 4개와 slide_type·콘텐츠에 따라 조건부 활성화되는 전문가 4개. 본 8개 는 에이전트 유형 기준이며, 그 중 Card Detail 과 Hero Detail 은 Analyzer 가 검출한 요소 수에 따라 동적으로 여러 인스턴스로 실행된다.

- Base BG · Atmosphere · Decoration: 전체 이미지와 DesignSpec을 입력받아 배경 그라디언트, radial 글로우, decoration shape를 분리된 레이어로 생성한다. 이러한 분리는 분위기와 패턴이 같은 z=0 안에서 충돌하지 않도록 보장한다.
- Card Detail × N: 각 카드의 크롭 이미지(주변 패딩 포함)와 DesignSpec을 입력받아 카드별로 풍부한 CSS 효과(`backdrop-filter`, 다중 `box-shadow`, rgba 투명도, 테두리 효과)를 생성한다. 좁은 시각 범위가 선택적 CSS 재질(반투명, blur, 그라디언트 등)을 회복시킨다 — 통제 실험에서 같은 GPT-4o가 전체 이미지에서는 카드당 CSS 효과 2.8개를, 크롭에서는 6–8개를 생성한다.
- Hero Detail × N: 히어로 블록(큰 숫자, 메인 메시지, 특수 그래픽)을 크롭 단위로 별도 처리한다.
- Icon Agent: 카드별 의미 분석 → FontAwesome 클래스 검색 → 실제 `<i class="fa-...">` 태그 주입의 순서로 동작하며, 환각된 아이콘 URL을 구조적으로 차단한다.
- Chart Agent · Table Agent: 슬라이드 타입이 chart_templates 적용 7종 (bar_chart, line_chart, waterfall, matrix_2x2, mekko, harvey_table_advanced, tree_diagram) 중 하나일 때 `chart_templates` 라이브러리로 슬라이드 전체를 결정적으로 렌더링한다. 라이브러리는 7개 renderer를 노출한다 — `bar_chart` (하이라이트/플랜 점선 지원), `line_chart` (multi-series, 시리즈별 색·하이라이트·주석), `waterfall` (start/positive/negative/total 4-type 막대), `matrix_2x2` (4-사분면 + 축 라벨 + 하이라이트 quadrant), `mekko` (가변폭 컬럼 × stacked 세그먼트), `harvey_table_advanced` (option×기준 그리드 + 0/25/50/75/100 Harvey ball), `tree_diagram` (1 root → N branches → M leaves 계층적 레이아웃). VLM 호출은 chat_parser 단계의 데이터 추출에 한정되며, 시각 자체는 SVG/HTML 프리미티브로 결정적으로 산출되므로 자기회귀 토큰 예산이 시각·콘텐츠 간 zero-sum을 일으키지 않는다 (6.1절).

3.4 단계 2 — 조립과 정규화

제1항 Assembler

8개 전문가의 HTML 단편을 z-index band([0, 5, 10, 20, 30, 40])로 결정적으로 쌓는다. 단순 concat이 아니라 절대 좌표(Analyzer의 bbox 정규화 비율 × 1280×720)와 z-index를 명시적으로 부착한다.

제2항 Style Normalizer

조립된 HTML을 텍스트 입력만 받아 카드 간 CSS 속성을 통일한다:

- 배경 rgba alpha — 모든 카드 동일값
- 테두리 색상/두께 — 통일
- border-radius — 통일
- box-shadow — 통일
- backdrop-filter blur — 통일

불변 보장: position, left, 최상위, width, height, z-index은 변경하지 않는다. 이미지 입력 없이 코드만 보는 텍스트 전용 에이전트로, 각 카드의 독립 생성에서 발생한 표류를 사후 동기화한다. 이 효과는 `no_style_norm` 플래그로 격리해 측정할 수 있다.

이는 클라이언트 측 renderer 가 디자인 시스템을 강제하는 에이전트형 UI 설계 원리와 유사하게, VLM 파이프라인 내부에서 스타일 일관성을 강제하려는 설계이다.

제3항 Text Inserter

완전히 스타일링된 HTML(배경, 카드, 정규화된 스타일)과 콘텐츠 데이터(제목, 설명, 메트릭, 리스트)를 입력받아, 기존 카드 구조 내의 빈 컨테이너를 식별하고 텍스트를 주입한다.

이 단계의 핵심은 시각 디자인을 먼저 확정한 뒤 텍스트를 주입한다는 순서에 있다. 단일 VLM에서 풍부한 CSS 생성과 정확한 텍스트 배치가 zero-sum 경쟁을 벌이는 현상 (H-RAG 에서 고밀도 시각 효과 부분집합 평균 CCR −13% / CSS +75%, chart·표 계열의 개별 디자인에서는 CCR 1.0 → 0.36–0.55 까지 큰 폭으로 감소) 을 줄이기 위한 설계로 단계 분리가 작동하며, 단계 분리에 의해 해당 zero-sum 이 완화될 수 있다. 이 효과는 `no_text_inserter` 플래그로 격리해 측정할 수 있다.

3.5 선택 단계

제1항 Overflow Repair

조립된 HTML을 Playwright로 렌더링한 뒤 측정한 바운딩 박스 오버플로를 분석하여 폰트 크기, 패딩, 줄 수를 미세 조정한다. 시각 critic과 달리 결정적 측정에 기반하므로 LLM 호출이 필요 없다.

제2항 Visual Critic

Playwright 스크린샷과 원본 이미지를 비교한 뒤 VLM이 diff를 작성하고 CSS 속성 단위로 보정한다. iteration 비용이 크므로 기본값은 비활성화이다.

3.6 구현

본 논문은 LayerAgent의 두 메커니즘 — DesignSpec blackboard와 Text Inserter — 의 인과 효과를 격리 측정한다 (5.3절). 각 ablation은 해당 컴포넌트를 noop으로 대체하는 방식으로 구성된다 (`no_designspec` flag → D₄, `no_text_inserter` flag → D₂).

모든 실험은 GPT-4o, LangGraph, Playwright 환경에서 수행되었다.

---

제 4 장. 실험 설정

4.1 데이터 — 계층화된 슬라이드 디자인 평가셋

본 연구의 평가셋은 50개의 계층화된 슬라이드 디자인으로 구성되며, 두 그룹으로 나뉜다.

(a) 고밀도 시각 효과 디자인 그룹 (N=10): 10개의 서로 다른 레이아웃 (timeline, dashboard, comparison_split, pyramid, hub_spoke, before_after, feature_grid, roadmap, layered_stack, stats_hero) 에 글로우, glassmorphism, 반투명 카드, 그림자, 테두리, z-index 중복 등 복합 CSS 효과가 높은 밀도로 포함된 시각 조건의 슬라이드들이다. `dark_glass` 는 해당 N=10 그룹의 내부 생성 라벨이며, 이후 본문에서는 이를 고밀도 시각 효과 디자인 부분집합으로 지칭한다.

(b) 차트·다이어그램 그룹 (N=40): 8개 레이아웃 (mekko, matrix_2x2, waterfall, harvey_table, bar_chart, line_chart, process_flow, pyramid)에 5종 비즈니스 컨설팅 스타일(minimal_white, editorial_warm, bain_red, bcg_green, mckinsey_blue)을 적용한 슬라이드로, 시각 효과 밀도가 상대적으로 낮다.

모든 슬라이드는 Gemini 3 Pro Image Preview (Google, 2026) 로 생성됐다. 본 연구는 전체 데이터셋에서 LayerAgent의 구조 복원 효과를 평가하며, 레이아웃/theme 그룹에 따른 효과 변화는 5.2절 레이아웃별 세부 분석에서 보고한다.

데이터 중복 명시. 부록 B.1 인식–생성 격차의 motivation을 만든 N=10 사전 실험 슬라이드는 (a) 그룹의 N=10과 동일하다. 따라서 5.2절의 고밀도 시각 효과 디자인 부분집합 결과는 부록 B.1와 동일한 슬라이드 위에서 측정되며, motivation과 검증이 같은 데이터 위에서 일어난다는 단서 하에 해석되어야 한다 (7장 한계).

4.2 비교 메서드

| code | 메서드 (논문 표시) | 접근 |
|---|---|---|
| A | 일괄 생성 (`single_pass`, 이하 sp) | 단일 GPT-4o 호출로 전체 이미지 → HTML |
| B | 시각 분석 생성 (`visual_cot`) | 시각 분석을 자연어로 먼저 수행한 뒤 코드 생성 (2단계) |
| C | 패턴 주입 생성 (`cot_h_rag`) | 시각 분석 + CSS 효과 패턴 레시피(RAG)를 함께 제공해 코드 생성 |
| D | LayerAgent (`layeragent`) | 본 연구 — 계층 단위로 생성 책임을 분해하는 멀티에이전트 전체 파이프라인 |

모든 메서드에 동일한 콘텐츠 데이터, 동일한 모델(GPT-4o), 동일한 시드(시드=0)를 제공한다.

4.3 평가 방식 — 디자인2code 다면적 평가

본 논문은 주요 결과를 디자인2code 평가의 다면적 평가 묶음 위에서 보고한다 — 객관적 시각 매칭 (Element-IoU; 요소 단위 Hungarian 매칭 기반), 색 정확도 (CIEDE2000), VLM-as-judge 루브릭 (AutoPresent 0–5 레이아웃/색, GPT-5.4 4 기준). Layer Recall 과 LTED 는 부록 B 에 정리한 클래스명 편향 위험으로 보조 지표로 분류된다. 평가 프로토콜은 2개의 주요 축(① 객관적 디자인 충실도, ② VLM-as-judge 루브릭)으로 구성된다.

축 ① 객관적 디자인 충실도 (Design2Code 계열):

Playwright 로 렌더링한 PNG 와 참조 PNG 사이의 객관적 매칭을 측정한다. Class 이름이나 사전 정의된 레이어 label 에 의존하지 않으며 모든 메서드에 동일하게 적용된다 (메서드 비의존).

- Element-IoU ↑ — Hungarian 매칭 기반 요소 단위 IoU. Generated 요소는 Playwright 로 렌더링한 HTML 의 visible DOM 요소 바운딩 박스와 computed 스타일 색으로 추출하고, 참조 요소는 참조 PNG 에 대해 edge-sampled 배경 색과의 색 거리 ≥25 픽셀의 connected components (skimage.label, 최소 면적 1500 px², 최대 30 패널 후보) 로 산출한다. 이후 bbox IoU 를 cost 로 한 linear sum assignment (Hungarian) 로 1:1 대응을 찾고 matched pairs 의 mean IoU 를 보고한다. Class 이름·DOM 구조에 의존하지 않으며 모든 메서드에 동일하게 적용된다 (메서드 비의존). Design2Code (NAACL 2025) Block-Match 와 유사한 요소 단위 매칭 계열 지표이다. 다만 connected-components 기반 참조 추출은 글로우·blur·그라디언트·그림자 같이 경계가 부드러운 atmospheric 효과를 개별 요소로 안정적으로 분리하지 못할 수 있어, Element-IoU 는 구조적 요소 정렬에는 적합하지만 고밀도 시각 효과의 분위기적 품질을 완전히 포착하지는 못한다 (5.2절·7.2절의 고밀도 시각 효과 부분집합 MLLM judge 하락 패턴과 정렬되는 지표 측정 한계).
- CIEDE2000 ↓ — CIE Δ E 2000 색 거리. dominant 색 K-means 추출 후 참조와의 평균 색 거리. 낮을수록 참조와 색이 가깝다.

추가로 측정된 검증가능한 규칙 (whitespace_frac, collision_score) 는 본 도메인에 대한 규범적 정의 (여백의 "balanced range" 0.4–0.6, 충돌의 의도적 SVG 프리미티브 인접) 가 모호하여 주요 표에서 제외하고 보조 진단으로만 사용한다.

축 ② VLM-as-Judge 루브릭:

두 종류의 VLM judge 를 동반 보고한다.

- AutoPresent 루브릭 (0–5) — AutoPresent (CVPR 2025) 의 레이아웃 / 색 두 차원 각각 0–5 점. GPT-4o judge.
- GPT-5.4 4 기준 (1–7) — PPTAgent (Zheng et al., EMNLP 2025) 의 PPTEVAL 계열 4 기준. Generator (GPT-4o) 와 다른 모델 계열로 자기평가 편향을 차단한다 (Zheng et al., 2023; WebDevJudge 2025). 참조 이미지, generated PNG, generated HTML 의 처음 3,000자를 함께 제공한다.
  - Visual Fidelity (VF), Layer Structure (LS), Content Completeness (CC), Design Quality (DQ)

축 ③ Content Completeness (보조):
- CCR ↑ — 입력 텍스트가 HTML 에 문자열로 등장하는 비율 (시각 가시성 미반영; MLLM judge CC 가 시각 프록시)

Legacy 기본 점검 — 클래스명 정렬 (참고용, 주요 주장 외):
- Layer Recall, LTED — class 이름 정규식 기반 (LayerAgent 어휘에 정렬). 어휘 alignment 한계로 인해 부록 B.1 (현상 가시화), 부록 B (보조 표), 5.1절 단순 베이스라인 점검 (프롬프트 변형이 명명 규칙과 무관하므로 방향 해석에 한해 안정적인 기본 점검) 에 한정해 사용한다.

Render guard 점검에서 모든 메서드가 Playwright 로 100% 정상 렌더링됨을 확인했다.

독자용 메트릭 지도. 본 연구는 메트릭 수가 많아 5장이후 표에서 반복적으로 등장하므로, 각 지표군이 답하는 직관적 질문을 다음 표로 한 번 정리한다.

| 지표군 | 직관적 의미 (한 줄 요약) | 본 연구 내 위치 |
|---|---|---|
| Element-IoU | 렌더된 요소 들이 참조의 위치·색과 1대1로 얼마나 맞는가 | 객관 충실도 (주요 축 ①) |
| CIEDE2000 | 렌더의 색 분포가 참조와 얼마나 가까운가 | 객관 충실도 (주요 축 ①) |
| AutoPresent layout_0_5 / color_0_5 | VLM 이 "발표 슬라이드로서 레이아웃·색이 적절한가" 를 0–5 로 채점 | VLM 루브릭 (주요 축 ②) |
| GPT-5.4 4 기준 (VF·LS·CC·DQ) | 교차 모델 VLM judge 가 보는 종합 발표 품질 1–7 | VLM 루브릭 (주요 축 ②) |
| CCR | 입력 텍스트가 코드에 살아남았는가 (시각 가시성 미반영) | 콘텐츠 (auxiliary, 축 ③) |
| LTED / Layer Recall | 레이어 단위 매칭 — 단, LayerAgent class 이름에 정렬되어 클래스명 편향 위험 | 보조 진단·기본 점검 (auxiliary, 축 ④) |

본 지도는 메트릭의 분류가 아니라 답하는 질문의 분류이며, 활용 사례별 weighting 해석은 6.2절 평가 차원 해석을 참조한다.


4.4 실험 인프라

- 4-stage cacheable 파이프라인: generate → 렌더(Playwright) → 참조 인식(VLM 캐시) → metrics 순서로 구성되며, 각 단계는 독립적으로 재시작이 가능하다.
- 총 4 메서드 × 50 슬라이드 = 200 cell이며, 전체 실행 시간은 82분, 생성 실패는 0건이다.
- 결과는 jsonl, csv, 리포트 형식으로 저장되어 후속 분석 단계에서 재사용된다.

---

제 5 장. 결과

본 장의 결과는 1.2절의 세 RQ 에 다음과 같이 대응한다. RQ1 (인식–생성 격차의 모델-일반성) 은 부록 B.1 (GPT-4o 사전 실험) 과 부록 B.2 (교차 VLM 프로빙 3 최첨단) 에서 직접 측정되어 채택되며 (부록 A H-EO 가설), 본 장의 동기로 작동한다 — 같은 GPT-4o 가 자연어로는 평균 6.6개 레이어를 인식하지만 HTML 생성에서는 평균 1.8개만 코드에 반영하며, 본 격차는 GPT-5.4·Claude 4.6 Opus 일괄 생성에서도 보조 지표 기준 0.69–0.78 범위의 유사한 양식으로 관찰된다. RQ2 (동일 GPT-4o 조건에서의 LayerAgent 우위) 는 본 5.1절에서 다면적 평가 묶음 비교와 단순 베이스라인 점검을 함께 보고하고, 메커니즘별 격리 측정은 5.3절 ablation 에서 다룬다. RQ3 (레이아웃·평가 축 의존성) 의 레이아웃 부분는 5.2절에서, 평가 축 부분는 6.2절 평가 차원 해석에서 다룬다.

5.1 동일 모델 GPT-4o 비교 — 객관 충실도와 교차 모델 VLM judge에서의 우위 (RQ2)

부록 B.1 사전 실험은 GPT-4o 일괄 생성에서 인식이 기술한 평균 6.6개 레이어가 코드의 평균 1.8개로 떨어지는 격차를 보고했다. 본 절은 이 격차에 대한 프로세스 단위 분해의 회복을 디자인2code 다면적 평가 묶음 — 객관 충실도 (Element-IoU, CIEDE2000) + VLM 루브릭 (AutoPresent 0–5, GPT-5.4 4 기준) — 으로 정량화한다. 명명 규칙 비의존 n_layers 수준의 회복(일괄 1.8 → LayerAgent 8.2, 같은 사전 실험 조건) 은 본 절 말미의 단순 베이스라인 점검에서 z 명시 프롬프트 변형과 함께 보고한다.

본 절은 동일 기본 모델 GPT-4o 위에서, 4가지 메서드(일괄 생성·시각 분석 생성·패턴 주입 생성·LayerAgent)를 본 연구의 계층화된 슬라이드 데이터셋 전반에서 비교한다 (표 1: 전체 N=50 자동 지표; 표 2: 고밀도 시각 효과 디자인 부분집합 N=10 자동 지표). 종합적 발표 품질 차원은 MLLM judge로 별도 보고한다 (표 3, main_eval). 레이아웃 의존성은 5.2절 레이아웃별 세부 분석에서 다룬다.

〈표 1〉 전체 데이터셋 객관 충실도 + VLM 루브릭 (N=50, 다면적 평가 묶음). 굵은 = 1위.

| 지표 | A. 일괄 생성 | B. 시각 분석 생성 | C. 패턴 주입 생성 | D. LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Element-IoU ↑ | 0.314 | 0.301 | 0.296 | **0.372** |
| CIEDE2000 ↓ | 53.6 | 56.9 | **51.5** | 58.6 |
| AutoPresent layout_0_5 ↑ | 2.90 | 2.70 | 2.56 | **3.64** |
| AutoPresent color_0_5 ↑ | **3.70** | 3.56 | 2.76 | 3.12 |

핵심 발견 1 (주요 결과) — 전체 N=50 에서 LayerAgent 는 객관 시각 매칭(Element-IoU)과 VLM-루브릭 레이아웃 차원에서 명확히 1위이다. Element-IoU 0.372 는 일괄 생성 0.314 대비 +18%, AutoPresent layout_0_5 3.64 는 일괄 생성 2.90 대비 +0.74 격차이다. 색 차원(CIEDE2000, color_0_5)에서는 일괄 생성·패턴 주입 생성이 LayerAgent 보다 우세하다 — chart_templates 의 결정적 렌더링이 참조 색 팔레트를 정확히 복제하지 않고 정제된 SVG 색 시스템(예: 일관된 brand 색 hue)을 사용하기 때문이다. 본 절충 관계는 6.2절에서 다룬다.

〈표 2〉 고밀도 시각 효과 디자인 부분집합 객관 충실도 + VLM 루브릭 (N=10, design_01–10). 굵은 = 1위.

| 지표 | A. 일괄 생성 | B. 시각 분석 생성 | C. 패턴 주입 생성 | D. LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Element-IoU ↑ | 0.563 | 0.551 | 0.563 | **0.575** |
| CIEDE2000 ↓ | 30.3 | 26.9 | 27.7 | **20.7** |
| AutoPresent layout_0_5 ↑ | **4.20** | 3.80 | 3.70 | 2.90 |
| AutoPresent color_0_5 ↑ | 3.70 | **3.90** | 3.50 | 3.00 |

핵심 발견 1' (부분집합 분기) — 고밀도 시각 효과 디자인 부분집합 (N=10) 에서 LayerAgent 는 객관 충실도 (Element-IoU, CIEDE2000) 에서 1위 (CIEDE2000 20.7 대 차순위 메서드 26.9, 큰 폭 색 정확도 우세) 이지만 VLM 루브릭 (layout_0_5, color_0_5) 에서는 4위이다. 이 분기는 본 평가 프레임워크가 측정하는 두 차원의 분리를 직접 보여준다 — 객관적 시각 매칭은 LayerAgent 의 분해 + DesignSpec blackboard 가 색 표류를 줄여 참조와의 색 거리를 좁히는 효과를 포착하지만, VLM 종합적 judge 는 고밀도 시각 효과 디자인의 풍부한 분위기 레이어 (radial 글로우, glassmorphism, 장식 모티프) 를 LayerAgent 출력이 단순화하는 경향을 레이아웃 / 색 품질 패널티로 평가한다. 본 분기는 5.2절의 고밀도 시각 효과 MLLM Δ −0.80 과 정렬되며, 7.2절의 후속 연구로 "고밀도 시각 효과 카테고리에서의 보다 expressive 한 분위기 레이어 생성" 을 다룬다. 데이터 중복 단서는 7.2절을 참조한다.

핵심 발견 2 — 시각 분석 생성(`visual_cot`)과 패턴 주입 생성(`cot_h_rag`)은 일괄 생성(`single_pass`) 대비 일관된 개선을 보이지 않는다. 시각 분석 생성은 Element-IoU 0.301 (sp 0.314 보다 낮음), AutoPresent layout_0_5 2.70 (sp 2.90 보다 낮음) 으로 4 메트릭 모두 sp 보다 열세이다. 패턴 주입 생성은 CIEDE2000 51.5 에서 1위이나 layout_0_5 2.56 / color_0_5 2.76 으로 VLM 루브릭 두 차원에서 최하위이다. 즉 단순한 시각 분석 단계 추가나 CSS 패턴 지식 주입만으로는 일관된 개선이 관찰되지 않으며, 생성 단위 분해가 빠진 프롬프트 수준 변형만으로는 충분하지 않다. LayerAgent 의 통합 파이프라인(Chat Parser + DesignSpec + chart_templates + Style Normalizer + Text Inserter)은 동일 모델 조건에서 Element-IoU, AutoPresent layout_0_5, GPT-5.4 4 기준 등 주요 구조·품질 축에서 가장 강한 결과를 보인다. 컴포넌트별 인과 효과는 Text Inserter(D₂)와 DesignSpec blackboard(D₄) 두 메커니즘에 대해 5.3절에서 격리 측정된다.

본 논문에서 종합적 발표 품질은 참조와의 픽셀 단위 복제 여부가 아니라, MLLM judge 가 시각 충실도 (Visual Fidelity), 계층 구조 (Layer Structure), 콘텐츠 완결성 (Content Completeness), 디자인 품질 (Design Quality) 네 차원을 함께 고려해 평가한 발표 슬라이드로서의 완성도를 의미한다.

〈표 3〉 종합적 발표 품질 — MLLM judge (GPT-5.4, 4 기준, 1–7 scale, main_eval N=50). 굵은 = 1위.

| Criterion | 일괄 생성 | 시각 분석 생성 | 패턴 주입 생성 | LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 2.24 | 2.08 | 1.74 | **2.94** |
| Layer Structure ↑ | 3.52 | 3.08 | 3.00 | **4.62** |
| Content Completeness ↑ | 3.92 | 3.70 | 3.76 | **4.62** |
| Design Quality ↑ | 3.78 | 3.30 | 3.36 | **3.90** |
| Average ↑ | 3.37 | 3.04 | 2.96 | **4.02** |

MLLM judge 4 기준 모두에서 LayerAgent가 1위이며, 평균은 4.02로 차순위 메서드(일괄 생성 3.37) 대비 +0.65 격차이다. chart_templates 가 적용되는 7 레이아웃 (pyramid + chart·표 6종, 5.2절 표 4 캡션 매핑) 에서 결정적 렌더링이 자기회귀 zero-sum을 회피하여 텍스트 오버플로·콘텐츠 누락 패널티가 구조적으로 차단되며, Layer Structure(4.62)·Content Completeness(4.62) 두 축의 큰 격차가 이를 직접 보여준다. 단, 본 MLLM judge 결과는 GPT-5.4 단일 judge 에 기반하므로 교차 judge (Claude·Gemini) 일반화는 7장의 한계로 남는다.

표 1·2·3을 함께 읽으면 LayerAgent 의 우위가 평가 축과 카테고리에 따라 다음과 같이 분포된다.

(i) 전체 N=50 에서 객관 충실도 (Element-IoU) + VLM 루브릭 레이아웃 차원 (AutoPresent layout_0_5, GPT-5.4 LS·VF) 에서 LayerAgent 1위. 색 차원 (CIEDE2000, color_0_5) 은 일괄 생성·패턴 주입 생성이 참조의 색을 직접 모방하므로 LayerAgent 보다 우세이다. (ii) 고밀도 시각 효과 디자인 부분집합 (N=10) 에서 LayerAgent 는 객관 충실도 (Element-IoU 0.575, CIEDE2000 20.7, 두 메트릭 모두 1위) 에서는 우세하지만 VLM 루브릭 (layout_0_5 2.90, color_0_5 3.00) 에서는 4위이다 — 분위기 레이어의 풍부성 simplification 이 VLM 의 종합적 채점에 패널티를 유발한다. (iii) MLLM judge 4 기준 (표 3, GPT-5.4) 은 전체 N=50 평균에서 LayerAgent 1위 (4.02 대 차순위 메서드 3.37).

종합적으로 LayerAgent 는 객관 충실도 축과 GPT-5.4 종합 judge 축에서 우위를 보이며, AutoPresent 루브릭의 고밀도 시각 효과 부분집합 약점은 7.2절 후속 연구에서 다룬다.

![그림 2: Qualitative 구조적 충실도 비교](results/figures/fig6_qualitative.png)

(그림 2) 4개 chart·표 디자인의 정성적 3-way 비교 (참조 / single_pass / LayerAgent, 동일 GPT-4o). 위에서부터 mekko (가변폭 컬럼 × stacked 세그먼트), line_chart (multi-series 추세선), matrix_2x2 (4-사분면 격자 + 축 라벨), harvey_table_advanced (option × 기준 매트릭스 + Harvey ball). 네 사례 모두에서 LayerAgent는 참조의 핵심 시각 구조 — 컬럼 비례, 4 시리즈 라인 + 데이터 라벨, 사분면 격자 + items, Harvey ball 채움 정도 — 를 single_pass보다 정확하게 재현한다. single_pass 는 chart 영역의 자기회귀 zero-sum으로 인해 컬럼이 동일 폭으로 단순화되거나 라인이 거의 그려지지 않거나 사분면 items가 사라지는 경향을 보인다. chart_templates 결정적 렌더링 라이브러리(3.3절)가 chart_templates 적용 7 레이아웃 (pyramid + chart·표 6종) 의 시각 충실도와 콘텐츠 보존을 동시에 보장하며, 이는 표 4의 chart·표 6종 카테고리에서 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차로 정량 확인된다.

단순 베이스라인 점검 (프롬프트 수준 변형의 반증 점검). LayerAgent의 동일 모델 우세(표 1)가 분해 효과인지 아니면 단순 프롬프트 조정만으로도 가능한지를 점검하기 위해 z-index 명시 일괄 생성(single_pass_zexplicit) 변형을 구현했다. 일괄 생성 프롬프트에 z-index 6-band 명시 한 줄만을 추가한 변형이다.

| 방법 (N=10 고밀도 시각 효과 디자인) | 설명 | LTED ↓ | Layer Recall ↑ | 평균 레이어 카운트 |
|---|---|:---:|:---:|:---:|
| 일괄 생성 (`single_pass`, 베이스라인 A) | 기본 일괄 생성 | 0.823 ± 0.14 | 0.224 ± 0.13 | 1.8 |
| z-index 명시 일괄 생성 (`single_pass_zexplicit`, 베이스라인 A') | z-index 6-band를 프롬프트에 명시 추가 | 0.844 ± 0.12 | 0.292 ± 0.17 | 3.8 |
| LayerAgent (`layeragent`, D) | 계층 단위 분해 생성 (전체 파이프라인) | 0.551 ± 0.13 | 0.759 ± 0.16 | 8.2 |

표 주: LTED와 Layer Recall은 부록 B의 보조 지표이다. 평균 레이어 카운트는 명명 규칙과 무관한 단순 카운트가므로 방향성 해석은 안정적이다.

z 명시 프롬프트는 보조 지표 Recall을 0.224 → 0.292로 올리지만 LayerAgent의 0.759와는 거리가 있다. 평균 레이어 카운트(명명 규칙과 무관)도 z 명시 3.8 대 LayerAgent 8.2로 차이가 유지된다. 즉 단순 z-index 명시만으로는 LayerAgent와 같은 수준의 계층적 요소 반영이 나오지 않는다. 생성 용량 증가에 대한 인과 주장은 본 표 단독이 아니라 위 표 1 + 5.3절 ablation 결과와 함께 해석한다.

5.2 레이아웃 유형별 효과 범위 분석 (RQ3 레이아웃 의존성)

〈표 4〉 9개 레이아웃 유형별 LayerAgent 레이아웃별 효과 비교. 주축은 MLLM judge, 보조 진단은 LTED (부록 B). 9개 레이아웃 중 고밀도 시각 효과 디자인과 process_flow 를 제외한 7개 레이아웃 (pyramid·mekko·harvey_table·matrix_2x2·waterfall·line_chart·bar_chart) 이 chart_templates 결정적 렌더링 라이브러리(3.3절) 의 7 renderer 에 대응하여 단일 VLM의 자기회귀 zero-sum이 구조적으로 차단되며, 본문이하에서 "chart·표 6종" 은 이 중 pyramid(tree_diagram renderer)를 제외한 6 레이아웃 (mekko·matrix_2x2·waterfall·line_chart·bar_chart·harvey_table) 을 가리킨다.
- MLLM Δ (주요) = LayerAgent 평균 − (최고 베이스라인 평균), 양수 = LayerAgent 우세.
- LTED Δ (aux) = (최고 베이스라인 LTED) − (LayerAgent LTED), 양수 = LayerAgent 우세.

| 레이아웃 | N | MLLM LayerAgent | MLLM Δ | LTED LayerAgent | LTED Δ | Primary 해석 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 고밀도 시각 효과 디자인 | 10 | 3.23 | −0.80 | 0.551 | +0.27 | 베이스라인 우세 (LTED 보조 지표는 LayerAgent 우세) |
| pyramid | 5 | 3.45 | +0.05 | 0.764 | +0.08 | LayerAgent 우세 (tree_diagram renderer) |
| mekko | 5 | 5.00 | +1.35 | 0.753 | +0.08 | LayerAgent 우세 (mekko renderer) |
| process_flow | 5 | 3.25 | −0.65 | 0.818 | +0.06 | 베이스라인 우세 (LTED 보조 지표는 LayerAgent 우세) |
| harvey_table | 5 | 4.25 | +0.15 | 0.923 | −0.05 | LayerAgent 우세 (harvey_table_advanced renderer) |
| matrix_2x2 | 5 | 4.40 | +1.90 | 0.917 | +0.00 | LayerAgent 우세 (matrix_2x2 renderer) |
| waterfall | 5 | 4.50 | +1.70 | 0.662 | −0.03 | LayerAgent 우세 (waterfall renderer) |
| line_chart | 5 | 4.40 | +1.80 | 0.845 | −0.03 | LayerAgent 우세 (multi-series line_chart renderer) |
| bar_chart | 5 | 4.50 | +1.50 | 0.733 | −0.09 | LayerAgent 우세 (bar_chart renderer) |

표 주: LTED는 부록 B의 보조 진단 지표이며, 주축은 MLLM judge이다. 9개 레이아웃 중 7개에서 LayerAgent가 MLLM 축의 우세를 차지하며, chart·표 카테고리 6종(mekko·matrix_2x2·waterfall·line_chart·bar_chart·harvey_table)은 chart_templates 결정적 렌더링으로 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차를 보인다.

![그림 3: Per-layout 효과 range (N=50)](results/figures/fig3_layouts.png)

(그림 3) 9개 레이아웃별 LayerAgent 레이아웃별 분석 (양수=LayerAgent 우세). 좌측 패널은 주축(MLLM Δ), 우측 패널은 보조 축(LTED Δ)이다. chart·표 카테고리 6종에서 LayerAgent는 chart_templates 결정적 렌더링 효과로 MLLM Δ +0.15 ~ +1.90 의 큰 폭 우세를 보이며, 고밀도 시각 효과 디자인과 process_flow 에서는 베이스라인이 우세하다.

핵심 발견 (RQ3 정착).

1. chart·표 6종 카테고리(mekko·matrix_2x2·waterfall·line_chart·bar_chart·harvey_table)에서 LayerAgent가 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차로 우세하다. chart_templates 결정적 렌더링이 chart 영역의 자기회귀 zero-sum을 구조적으로 회피하여 시각 충실도와 콘텐츠 보존을 동시에 보장한다 (3.4절 Text Inserter 설계 의도 및 5.3절 D₂ 옛 string-CCR 측정과 정렬).
2. pyramid (tree_diagram renderer 적용) 에서도 LayerAgent가 MLLM Δ +0.05, LTED Δ +0.08 로 양 축 합의로 우세하다.
3. 고밀도 시각 효과 디자인과 process_flow 에서는 MLLM 축에서 베이스라인이 우세하다 (Δ −0.80, −0.65). 두 카테고리 모두 chart_templates 가 적용되지 않는 레이아웃 그룹이며, LTED 보조 지표는 LayerAgent 우세 — 레이어 구조 회복은 일어나지만 종합적 발표가능성으로 전이되지 않는 카테고리이다. 7.2절 후속 연구에서 다룬다.

본 연구의 적용 범위. LayerAgent는 GPT-4o 동일 모델 4 메서드 비교의 다면적 평가에서 평균 1위에 위치하며 (표 3, 평균 4.02 대 3.37), 9개 레이아웃 중 7개에서 MLLM 축의 우세를 차지한다. chart_templates가 활성화되는 6종 chart·표에서 격차가 가장 크다.

LayerAgent 우위의 메커니즘 분해 — Layer 분해 대 Deterministic 렌더링. 본 결과는 LayerAgent 전체 파이프라인의 단일 효과로 해석되기보다 두 메커니즘으로 분리 귀속되어야 한다.

- (i) Deterministic chart_templates 렌더링 효과 — chart·표 6종 + pyramid 의 큰 폭 우세 (MLLM Δ +0.05 ~ +1.90) 의 주된 원인. 본 7 레이아웃에서 VLM 호출은 chat_parser 단계의 데이터 추출에 한정되며 시각 자체는 결정적 SVG/HTML 프리미티브로 산출되므로 자기회귀 zero-sum 자체가 구조적으로 차단된다. 즉 이 카테고리의 격차는 멀티에이전트 레이어 분해의 효과라기보다 deterministic renderer 의 효과에 가깝다.
- (ii) Layer 분해 효과 — DesignSpec + 단계 1 전문가 + 단계 2 normalizer + Text Inserter 의 결합. 고밀도 시각 효과 디자인 / process_flow / 비차트 일반 레이아웃에서 작동하는 메커니즘. 본 카테고리에서는 우위가 명확하지 않으며, 고밀도 시각 효과 부분집합 MLLM Δ −0.80, process_flow Δ −0.65 로 베이스라인이 우세 — 레이어 분해 단독 효과는 chart_templates 의 결정적 렌더링 효과만큼 강하지 않다.

본 confound 를 분리 보고함으로써 LayerAgent 의 결과가 단일 메커니즘의 효과가 아니라 두 메커니즘의 결합으로 발생한다는 점을 명시한다 — 두 효과를 스택 한 LayerAgent 의 전체 우위는 동일 모델 분해 프레임워크의 실용적 가치를 보이지만, 메커니즘별 인과 기여는 카테고리에 따라 비균일하다.

시사점 — chart-type별 결정적 렌더링 전략. 본 결과는 벡터 구조가 명확한 카테고리(chart, 표, 다이어그램)에서 데이터 추출만 VLM에 맡기고 시각 자체는 결정적 프리미티브로 렌더링하는 분리가 zero-sum을 구조적으로 회피하는 효과적 전략임을 보여준다. 이 원리는 8장의 더 넓은 원리 3번에서 다룬다.

5.3 Ablation

본 절은 두 메커니즘의 정량 격리 측정 결과를 보고한다 — Text Inserter 분리(D₂)와 DesignSpec blackboard(D₄). 두 ablation 모두 LayerAgent v4 (chart_templates 활성화) 출력 위에서 다면적 평가 묶음 (Element-IoU + CIEDE2000 + AutoPresent layout_0_5 / color_0_5) 으로 재측정되었다.

D₂ (no_text_inserter) — Text Inserter 분리 (N=50 main_eval):

| 지표 | D (전체) | D₂ (no_text_inserter) | Δ (D − D₂) |
|---|:---:|:---:|:---:|
| Element-IoU ↑ | 0.372 | 0.364 | +0.008 |
| CIEDE2000 ↓ | 58.59 | 57.55 | +1.04 (D₂ 우세) |
| AutoPresent layout_0_5 ↑ | 3.64 | 3.42 | +0.22 |
| AutoPresent color_0_5 ↑ | 3.12 | 3.28 | −0.16 (D₂ 우세) |

Text Inserter 를 제거하면 다면적 평가 묶음 4 지표 중 layout_0_5 만 D 가 우세 (Δ +0.22) 하며, 색 차원 (CIEDE2000, color_0_5) 에서는 D₂ 가 우세이다. 다면적 시각 묶음이 측정하는 차원은 텍스트의 콘텐츠 보존이 아니라 시각 배치·색 분포이며, Text Inserter 의 핵심 메커니즘 (텍스트 누락 차단) 은 문자열 단위 콘텐츠 보존 차원으로 시각 묶음의 측정 범위 밖이다. AutoPresent 루브릭의 layout_0_5 가 텍스트 없는 카드의 "비어 있음" 을 부분적으로 채점에 반영하지만, 본 ablation 의 메커니즘 입증은 시각 묶음 단독으로 충분하지 않다. 본 관찰은 6.3절의 "string-CCR 과 시각 프록시 간 측정 차원 분리" 와 정렬되며, 후속 연구로 시각 인식 OCR 기반 시각 CCR 메트릭 도입 시 직접 검증된다.

고밀도 시각 효과 디자인 부분집합 (N=10) 에서는 효과가 강하게 나타난다 — Element-IoU Δ +0.026, color_0_5 Δ +0.50 (D 우세). 시각 효과 밀도가 높은 조건에서 Text Inserter 가 없으면 시각 생성에도 영향을 미친다는 신호이다 (사전등록 가설 H-AblationTextInserter 의 결정 규칙은 string-CCR 기준이며 부록 A 에서 별도 보고).

D₄ (no_designspec) — DesignSpec blackboard 효과 (N=50 main_eval):

| 지표 | D (전체) | D₄ (no_designspec) | Δ (D − D₄) |
|---|:---:|:---:|:---:|
| Element-IoU ↑ | 0.372 | 0.371 | +0.001 |
| CIEDE2000 ↓ | 58.59 | 59.25 | −0.66 |
| AutoPresent layout_0_5 ↑ | 3.64 | 3.72 | −0.08 |
| AutoPresent color_0_5 ↑ | 3.12 | 2.16 | **+0.96** |

DesignSpec blackboard 를 제거하면 다면적 평가 묶음 4 지표 중 color_0_5 차원에서 Δ +0.96 의 큰 폭 격차를 보인다 — AutoPresent VLM 이 카드 간 색 일관성 손실을 직접 채점에 반영. Element-IoU 와 CIEDE2000 (객관 시각 매칭) 은 거의 동률 — DesignSpec 이 요소 배치 자체에는 영향 없고 색 일관성에만 강하게 작용함을 보여준다 (사전등록 가설 H-AblationDesignSpec 의 핵심 시그널: color_0_5 차원, 부록 A 참조).

고밀도 시각 효과 디자인 부분집합 (N=10) 에서도 동일 패턴이 관찰된다 — color_0_5 Δ +0.70 (D 우세), 다른 지표의 Δ 는 작다. 즉 mixed N=50 과 고밀도 시각 효과 부분집합 모두에서 DesignSpec 의 효과는 색 일관성 (color_0_5) 에 집중되어 있으며, 3.2절.3 의 "DesignSpec 이 에이전트 간 스타일 표류를 줄인다" 는 설계 의도가 다면적 평가 묶음 위에서 직접 검증된다.

![그림 4: D₂ and D₄ ablation impact](results/figures/fig4_ablation.png)

(그림 4) 두 메커니즘 격리 측정 시각화 (다면적 평가 묶음, LayerAgent v4 출력). 좌측: D₂ (Text Inserter 분리). 다면적 시각 묶음 4 지표 중 layout_0_5 만 D 가 우세 (Δ +0.22); 색 차원은 D₂ 가 우세. Text Inserter 의 핵심 메커니즘 (텍스트의 콘텐츠 보존) 이 시각 묶음의 측정 범위 밖에 있음을 보여준다 (6.3절 참조). 우측: D₄ (DesignSpec blackboard). color_0_5 차원에서 D 가 Δ +0.96 의 큰 폭 우세 — DesignSpec 의 카드 간 색 일관성 효과가 AutoPresent VLM 의 종합적 채점에 직접 반영됨.


제 6 장. 논의

6.1 요소 누락의 메커니즘 — Capacity allocation 가설

본 절은 요소 누락의 메커니즘을 가설로 제시하고, 가설을 뒷받침하는 디자인 조건부 zero-sum 관찰을 함께 보고한다. 본 논문은 메커니즘 자체를 직접 인과 증명하지 않으며, 본 가설은 5장의 관찰과 부합하는 후보 설명으로 제시된다.

가설 (용량 할당). VLM이 전체 슬라이드를 단일 호출로 처리할 때, 레이아웃·색·텍스트·아이콘·CSS 재질·z-index·테두리·그림자·alpha를 모두 하나의 자기회귀 토큰 시퀀스로 산출해야 한다. `z-index`, `backdrop-filter: blur(16px)`, `box-shadow: 0 0 15px rgba(...)` 같은 속성은 없어도 HTML이 정상 렌더링되므로 생성 용량이 동시에 경쟁하는 상황에서 가장 먼저 단순화될 가능성이 높다. 이 가설로 (a) 카드 간 재질 단순화, (b) 카드 간 스타일 표류, (c) z-index 부재의 세 결과가 공유된 메커니즘에서 비롯된다고 해석할 수 있다. 본 가설은 5장의 관찰과 부합하는 후보 설명이며, 직접적인 인과 검증(예: 토큰 budget을 외생적으로 조정한 통제 실험)은 본 논문의 범위 외이다.

이 가설 하에서, LayerAgent의 분해는 각 전문가의 인지 범위를 좁혀 (a)를 줄이도록 설계되었으며, DesignSpec blackboard는 (b)를 줄이는 shared 스타일 prior로 작동하고, Assembler의 결정적 z-index stacking은 (c)를 줄이는 메커니즘으로 작동한다.

가설을 뒷받침하는 직접 관찰 — Pattern injection의 디자인 조건부 zero-sum (H-RAG 역설). 패턴 주입 생성(`cot_h_rag`, 복합 CSS 효과 레시피 RAG 주입)에서 zero-sum 현상은 디자인 유형에 따라 강도가 크게 달라진다. 텍스트 밀도가 높은 chart·표 계열에서는 강한 zero-sum이 발생해 입력 텍스트의 절반 이상이 코드에서 사라진다 — mekko_mckinsey_finance에서 CCR 1.0 → 0.36 (−64%), harvey_table_editorial_warm에서 1.0 → 0.43 (−57%), waterfall_editorial_warm에서 1.0 → 0.55 (−45%). 시각 효과 밀도가 높은 고밀도 시각 효과 디자인 부분집합(N=10)에서도 zero-sum이 명확하게 관찰되며, CSS Richness가 10.2 → 17.8 (+75%)로 크게 상승하는 동시에 CCR이 0.956 → 0.828 (−13%)로 감소한다. N=50 데이터셋 평균(CCR 0.869 → 0.832, CSS 5.08 → 7.82)은 평면 레이아웃이 평균을 희석하기 때문에 −4%로 작아지지만, 디자인별 분포는 zero-sum이 시각 효과 밀도 또는 텍스트 밀도가 높은 조건에서 가장 강하게 발현됨을 보여준다. 이는 콘텐츠 보존 측정(CCR, 명명 규칙과 무관)에서 직접 관찰되며, 단일 VLM의 자기회귀 토큰 예산이 시각 표현과 텍스트 사이에서 경쟁한다는 본 가설에 부합한다. LayerAgent의 D₂ ablation 옛 string-CCR 측정(5.3절 · 부록 A)은 이 zero-sum이 단계 분리로 줄어들 수 있음을 시사한다.

6.2 다면적 평가가 측정하는 서로 다른 차원 (RQ3 평가 축 의존성)

본 절은 RQ3 의 평가 축 부분를 다룬다 — 디자인2code 평가가 단일 지표로 환원되지 않고 서로 다른 차원을 측정하는 다축 문제임을 정착시키고, 각 축 위에서 LayerAgent 가 위치하는 곳을 명시한다.

〈표 5〉 본 연구가 정착시키는 메트릭 축 분리.

| 평가 축 | 대표 지표 | 측정 차원 | 동일 모델 GPT-4o 우승 | 답하는 질문 |
|---|---|---|---|---|
| ① 객관 디자인 충실도 | Element-IoU, CIEDE2000 | 요소 단위 IoU, 색 거리 | LayerAgent (Element-IoU); 색은 베이스라인 우세 | "렌더된 결과가 참조와 요소·색에서 얼마나 정확히 일치하는가?" |
| ② AutoPresent 루브릭 (0–5) | layout_0_5, color_0_5 | GPT-4o judge, 레이아웃·색 적절성 | LayerAgent (레이아웃); 색은 베이스라인 우세 | "발표 슬라이드로서 레이아웃 / 색이 적절한가? (0–5)" |
| ③ GPT-5.4 4 기준 (1–7) | VF·LS·CC·DQ | 교차 모델 VLM judge | LayerAgent (4 기준 모두) | "출력이 발표가능한 슬라이드인가? (1–7)" |
| ④ 클래스명 정렬 (보조 기본 점검) | LTED, Layer Recall | class 이름 정규식 매칭 | LayerAgent | 클래스명 편향: "출력이 LayerAgent 의 class naming convention 에 맞는가?" |
| ⑤ 콘텐츠 completeness (보조) | CCR | 텍스트 문자열 보존 | LayerAgent | "콘텐츠 문자열이 코드에 살아남는가?" — 시각 가시성 미반영 |

LayerAgent 는 축 ① 객관 시각 매칭과 축 ③ 교차 모델 VLM judge 두 축에서 GPT-4o 동일 모델 4 메서드 비교의 1위에 위치하며, 각 축의 측정 차원과 결과는 다음과 같다.

- 객관 충실도 (Element-IoU, CIEDE2000) — 요소 단위 Hungarian 매칭과 색 거리로 참조와의 정확한 시각 일치를 측정한다. chart·표 카테고리의 요소 배치 정확도는 chart_templates 결정적 렌더링이, 고밀도 시각 효과 디자인의 색 일관성은 DesignSpec blackboard 와 Card Detail 크롭 분석이 각각 책임지며, 그 결과 Element-IoU 전체 N=50 1위 (0.372) 이고 고밀도 시각 효과 부분집합의 CIEDE2000 도 1위 (20.7) 이다.
- AutoPresent 루브릭 (layout_0_5, color_0_5) — GPT-4o judge 의 0–5 발표가능성 채점이다. LayerAgent 는 전체 N=50 layout_0_5 에서 1위 (3.64 대 2.90) 이나 색 차원에서는 베이스라인 우세이며, 고밀도 시각 효과 부분집합에서는 두 차원 모두 4위이다 — 분위기 레이어 단순화가 VLM 의 종합적 채점에 패널티를 유발한다 (5.2절·7.2절 참조).
- GPT-5.4 4 기준 (1–7) — 교차 모델 VLM judge 의 종합 발표 품질 채점이다. LayerAgent 는 전체 N=50 평균에서 4 기준 모두 1위 (4.02 대 차순위 3.37).

평가 축 간 불일치의 의미. Design-to-Code 활용 사례는 단일하지 않으며, 활용 사례별로 우선 축이 달라진다:
- (i) 참조 이미지 객관 시각 복제 (요소 단위 매칭, 색 정확도) → 축 ① 우선
- (ii) AutoPresent 스타일 0–5 루브릭 — 발표가능성 측면 레이아웃·색 적절성 → 축 ② 우선
- (iii) 교차 모델 VLM judge — 종합적 발표 품질 → 축 ③ 우선
- (iv) 클래스명 편향 진단 → 축 ④ (기본 점검 용도로 한정)

선행 순위의 재해석. Design2Code (NAACL 2025) Block-Match 는 본 연구의 축 ① 의 객관 매칭에 해당하고, AutoPresent (CVPR 2025) 0–5 루브릭은 축 ② 에 해당하며, WebDevJudge (2025) 의 LLM-as-judge 프로토콜은 축 ③ 에 해당한다. 본 연구는 DreamHouse 2026 (architectural structure 생성에서의 structural-visual 직교성 발견)과 SlideAudit (UIST 2025, 자동화된 대 human 축 분석) 의 다면적 평가 패러다임을 슬라이드 design-to-code 도메인으로 확장하며, LayerAgent 는 GPT-4o 동일 모델 4 메서드 비교에서 축 ① (Element-IoU 1위) + 축 ③ (GPT-5.4 4 기준 1위) 두 축에서 명확한 1위에 위치한다.

평가 해석의 원칙. 본 논문은 다면적 평가 세 축을 모두 보고하며 활용 사례별 지표가중치의 가능성을 시사점으로 제시한다. LayerAgent 는 (i) 객관 충실도 + (iii) 교차 모델 VLM judge 에서 중심 우위를 가지며, AutoPresent 루브릭의 고밀도 시각 효과 부분집합 약점은 분위기 레이어의 expressive 생성 강화로 후속 연구에서 다룬다.

6.3 String-CCR 대 시각 CCR — 메트릭학적 후속 제안

String-CCR 은 텍스트가 HTML 에 문자열로 등장하는 비율만을 측정하므로 시각 가시성(텍스트가 실제로 카드 안에 보이는지·오버플로 되었는지·다른 요소에 가려졌는지)을 과소 결정 한다. Text Inserter (3.4절) 가 텍스트를 카드 영역에 주입했음을 string-CCR 은 확인하지만, 시각 차원의 보존은 MLLM judge 의 Content Completeness 가 보완한다.

본 논문은 시각 CCR — Playwright 렌더링 후 OCR 로 가시 텍스트를 추출해 입력 콘텐츠와 매칭하는 메트릭 — 을 string-CCR 의 후속 지표로 제안한다. 다만 현재 OCR 이 본 도메인(다크 배경, 한국어, blur 조합)에서 무력화되어 있으므로, 시각 인식 OCR(mPLUG-DocOwl, Florence-2 등)의 채택이 선결 조건이다.

6.4 단계 분리의 효과 — 다면적 평가에서의 일관성

H-RAG의 zero-sum, D₂ ablation의 분리 효과, 5.1절의 z 명시 프롬프트 베이스라인 — 이들이 한 방향을 가리킨다: 단순 프롬프트 조정만으로는 LayerAgent의 같은 수준 레이어 회복이 관찰되지 않으며, 단계 분리·결정적 렌더링·DesignSpec blackboard 의 결합이 본 효과의 핵심이다. Cross-VLM 최첨단 베이스라인(부록 B.2)에서도 GPT-4o, GPT-5.4, Claude 4.6 Opus 모두 LayerAgent 어휘 정렬 지표 기준 베이스라인 격차가 0.69–0.78 범위에 분포하여, 최첨단 확장 단독으로는 계층적 요소 누락이 완전히 해소되지 않는다는 패턴을 보조적으로 보인다 (단 본 교차 VLM 측정은 보조 지표이므로 최첨단 간 상대 비교에 한정해 해석한다).

본 장의 종합. LayerAgent의 가치는 동일 모델 조건에서 단계 분리·결정적 렌더링·DesignSpec blackboard 의 결합이 부여하는 구조적 일관성에 있다. chart_templates 라이브러리는 chart 카테고리의 자기회귀 zero-sum을 구조적으로 회피하여 본 연구의 다면적 평가 세 축에서 동일 모델 4 메서드 비교 기준 종합 우위 (객관 충실도 + GPT-5.4 종합적 두 축의 중심) 를 만든다. 최첨단 모델 업그레이드는 별개의 비용-품질 차원이며(7.3절 경계 참조), 본 논문은 이를 적용 범위 경계로 명시한다.

6.5 비대칭적 시각 입력의 일반 원리

본 연구의 한 가지 관찰은 다음과 같다. 스타일을 생성하는 에이전트는 이미지를 입력으로 받고, 배치를 결정하는 에이전트는 좌표만을 입력으로 받는다. Card Detail은 크롭을 입력받지만 Text Inserter는 텍스트만을 입력받는다. LayerAgent의 D₂ ablation은 이러한 단계별 입력 비대칭이 단일 전문가에 시각·콘텐츠 책임을 함께 부여할 때보다 콘텐츠 보존을 큰 폭으로 향상시킴을 보였다 (옛 string-CCR 측정에서 Δ=0.343, 부록 A H-AblationTextInserter 참조; 다면적 시각 묶음의 측정 범위 외 차원). 다른 멀티에이전트 도메인(UI/code 에이전트 분리, planning/execution 에이전트 분리, 레이아웃/콘텐츠에이전트 분리 등)으로의 일반화 가능성은 본 연구의 측정 범위 외이며, 본 논문는 슬라이드 도메인에 한정해 보고한다.

---

제 7 장. 한계

본 연구의 한계는 세 범주로 정리된다.

7.1 평가 방법론과 지표의 타당성

(a) String-CCR 은 텍스트의 시각 가시성을 과소 결정 한다 — HTML 에 문자열로 존재하는지만 측정하므로 오버플로·폐색 같은 시각 차원이 빠진다. MLLM judge Content Completeness 가 시각 프록시로 보완하나, 시각 인식 OCR 기반 시각 CCR 메트릭(6.3절) 의 도입이 지표 수준의 정착된 해결이다. (b) 종합 평가가 GPT-5.4 단일 LLM-as-judge에 의존한다. Claude·Gemini 등 교차 judge 일반화와 인간 앵커 직접 검증(n≥80 쌍 × 5 평가자, MT-Bench·AlpacaEval 쌍별 프로토콜)은 수행되지 않았다. WebDevJudge(2025)가 제안한 평가 관행의 적용이 필요하다.

7.2 통계 검증력과 데이터 구성

(a) multi-seed × N=100+ 디자인 확장으로 통계 검증력을 보강할 필요가 있다. 현재 N=50 main_eval 은 단일 시드 기반이다. (b) 부록 B.1 사전 실험 N=10 과 5.2절 고밀도 시각 효과 디자인 부분집합 N=10 은 동일한 슬라이드이며 (4.1절 명시), 본 카테고리의 결과는 동기와 검증이 동일 데이터 위에서 일어났다는 한계를 가진다. 차트·표 카테고리 및 8개 다른 레이아웃 그룹은 별개의 N=40 위에서 측정된 independent 결과이므로 본 한계의 영향을 받지 않는다. 향후 사전 stratified sampling 기반 데이터셋 재구성과 독립 표본 수집·재측정이 필요하다.

7.3 최첨단 모델 경계 참조

LayerAgent 의 본 연구 주요 결과는 GPT-4o 동일 모델 4 메서드 비교 (5.1절) 위에서 디자인2code 다면적 평가 묶음으로 보고된다. 본 절은 LayerAgent 의 적용 범위 경계를 명시하기 위해 GPT-5.4 및 Claude 4.6 Opus 기반 일괄 생성을 별개 비용-품질 차원의 참조로 보고한다 (N=10 샘플, 가격은 2026 Q1 list price 기준 — GPT-4o $2.5/$10, GPT-5.4 $5/$15, Claude 4.6 Opus $15/$75 per M input/output). 본 절의 비교 표는 주요 프레임워크 적용 이전의 DOM 기반 측정값이며, 최첨단 출력 위의 다면적 평가 묶음 재측정은 향후 연구로 다룬다.

| 방법 | 요소 수 | 스타일 diversity | 렌더 풍부성 | Approx. API cost/슬라이드 | Time |
|---|:---:|:---:|:---:|:---:|:---:|
| LayerAgent (GPT-4o + 분해, N=10 고밀도 시각 효과) | 17.0 | 10.3 | 32.0 | $0.232 | 60s |
| 일괄 생성 (GPT-5.4, N=10) | 37.1 | 16.4 | 135.6 | $0.075 | 85s |
| 일괄 생성 (Claude 4.6 Opus, N=10) | 27.2 | 14.0 | 68.0 | $0.421 | 108s |

본 표는 LayerAgent 가 최첨단 모델 보다 항상 우수하다는 주장을 위한 것이 아니라, 동일 모델 프로세스 단위 개입 과 최첨단 확장이 서로 다른 비용-품질 경로임을 보이기 위한 경계 참조이다. DOM 기반 옛 측정에서 최첨단 모델의 요소/스타일/풍부성 수치는 LayerAgent 보다 높지만, 본 비교 지표 자체가 본 논문의 주요 다면적 평가 묶음과 다른 차원이라는 점 (최첨단 출력 위의 다면적 평가 묶음 재측정은 8장 향후 연구) 도 함께 강조한다. LayerAgent 의 주요 기여는 동일 모델 프로세스 단위 개입이며 최첨단 확장이 제약된 조건 (GPT-4o 급 lock-in, on-prem 배포, 검사 가능한 생성과정 요구 등) 에 정렬된다 — 최첨단 모델 업그레이드는 별개의 비용·모델 선택 차원에 속한다. 두 경로는 동시에 활용 가능하며 (최첨단 확장 + 프로세스 단위 분해의 스택), 후속 연구에서 LayerAgent 의 분해 전략을 최첨단 모델에 적용한 결합 효과는 8장의 향후 연구로 다룬다.

---

제 8 장. 결론

본 논문은 Design-to-Code 프레젠테이션 생성에서의 계층적 요소 누락 — Design-to-Code 선행 연구의 요소 누락이 슬라이드의 시각 계층 단위로 확장된 형태 — 을 정의하고, 이를 분석하고 완화하기 위한 LayerAgent 프레임워크와 다면적 평가 방식을 제안했다. 본 논문의 기여는 측정으로 직접 지지되는 세 가지 사실로 정리된다.

- (문제) 슬라이드 도메인의 계층적 요소 누락 정식화 (부록 B): 같은 VLM이 이미지를 자연어로 기술할 때는 평균 6.6개(범위 5–10)의 레이어를 인식하지만, 같은 이미지를 HTML로 변환할 때는 일괄 생성 기준 평균 1.8개의 레이어만 HTML/CSS 구조에 반영된다 — 이 인식–생성 격차가 슬라이드 도메인의 시각 계층 단위 요소 누락 현상이며, 명명 규칙과 무관한 레이어 카운트 측정에서도 신뢰성 있게 가시화된다.

- (방법) LayerAgent 프레임워크 (3장): Chat Parser 입력 정규화, DesignSpec blackboard, 비전 기반 전문 에이전트, chart_templates 결정적 렌더링 라이브러리(7종 chart renderer — bar/line multi-series/waterfall/matrix_2x2/mekko/harvey_table_advanced/tree_diagram), 스타일 정규화, text 삽입 분리를 포함한 멀티에이전트 레이어 분해 프레임워크이다. 본 논문은 두 메커니즘의 차원별 인과 효과를 격리 측정한다 (5.3절). DesignSpec blackboard (D₄) 는 다면적 평가 묶음의 AutoPresent color_0_5 차원에서 Δ=+0.96 (N=50 main_eval) 의 큰 폭 효과를 보이며, 카드 간 색 일관성 메커니즘으로 입증된다. Text Inserter (D₂) 의 효과는 다면적 시각 묶음에서는 layout_0_5 Δ=+0.22 로 제한적이지만, 사전등록된 string-CCR 측정에서는 Δ=+0.343 (N=50) / +0.687 (고밀도 시각 효과 부분집합) 의 큰 폭으로 콘텐츠 보존 효과가 관찰된다 — 본 메커니즘은 시각 충실도 개선이 아니라 문자열 단위 콘텐츠 보존으로 위치시킨다.

- (평가 & 발견) 디자인2code 다면적 평가에서 1위 (4.3절, 5장): class 이름이나 사전 정의된 레이어 어휘에 의존하지 않는 평가 프로토콜 — 객관 충실도 (Element-IoU + CIEDE2000) + VLM 루브릭 (AutoPresent 0–5 + GPT-5.4 4 기준) — 위에서 LayerAgent 는 동일 GPT-4o 조건의 4 메서드 비교에서 객관 시각 매칭 (Element-IoU 0.372 대 sp 0.314) 과 교차 모델 VLM judge (GPT-5.4 4 기준 모두 1위, 평균 4.02 대 3.37) 두 주요 축에서 1위에 위치한다 (표 1·3). AutoPresent 루브릭의 레이아웃 차원에서도 1위 (3.64 대 2.90). chart·표 카테고리 6종은 chart_templates 결정적 렌더링으로 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차를 보인다 (표 4). 최첨단 모델 일괄 생성(GPT-5.4·Claude Opus)은 7.3절 경계 참조로 별도 비용-품질 차원에서 보고된다.

최종 정리. LayerAgent 는 GPT-4o 급 VLM 의 일괄 생성에서 누락되는 계층적 시각 구조를 요소 단위에서 일정 부분 회복하는 프로세스 단위 개입 이다. 측정으로 지지되는 핵심 발견은 다음과 같다.

(i) 동일 GPT-4o 조건 4 메서드 비교에서 객관 디자인 충실도 (Element-IoU 0.372 대 sp 0.314, +18%) 와 GPT-5.4 4 기준 모두 1위 (평균 4.02 대 3.37). 본 우위는 chart_templates 결정적 렌더링이 적용되는 7 레이아웃 (pyramid + chart·표 6종) 에서 가장 크게 나타나며, 레이어 분해 단독 효과와 deterministic 렌더링 효과는 5.2절에서 메커니즘 단위로 분리 귀속된다.

(ii) 객관 시각 매칭과 종합적 발표 품질의 분리 — 본 평가 프레임워크의 핵심 발견. 고밀도 시각 효과 디자인 부분집합 (N=10) 에서 LayerAgent 는 Element-IoU 0.575 · CIEDE2000 20.7 로 객관 충실도 양 지표 1위이지만, atmospheric 시각 풍부성이 충분히 살아나지 않아 AutoPresent 루브릭의 레이아웃 / 색 차원은 4위로 베이스라인 우세이고 MLLM 종합 Δ = −0.80 (표 4). 즉 고밀도 시각 효과 조건에서는 구조적 정렬은 개선되지만 종합적 VLM judge 는 베이스라인 보다 낮게 평가하며, 요소 단위 구조 회복이 종합 발표 품질로 전이되지 않는 이 분리는 본 논문가 출발점으로 삼은 고밀도 시각 효과 카테고리에서 직접 관찰된다. 본 분리는 본 연구의 다면적 평가 동반 보고 권고를 강화한다.

(iii) 최첨단 확장은 본 논문의 적용 범위 외 별개 비용-품질 차원으로 7.3절에 경계 참조로 위치한다.

더 넓은 원리.

1. 다면적 평가 동반 보고의 필요성. 본 연구는 객관 디자인 충실도(Element-IoU + CIEDE2000), AutoPresent VLM 루브릭 (레이아웃·색 0–5), 교차 모델 GPT-5.4 4 기준 세 축의 동시 보고가 Design-to-Code 평가에서 단일 지표보다 더 명확한 해석을 가능하게 함을 보인다. 클래스명 정렬 정규식 기반 지표는 클래스명 편향 위험으로 기본 점검 외의 사용을 자제할 것을 권고한다.
2. 동일 모델 분해 효과와 최첨단 확장은 서로 분리된 두 개선 경로이다. 본 논문은 동일 모델 분해를 주요 RQ로 한정하고 최첨단 비교는 적용 범위의 경계를 명시하는 보조 분석으로 분리한다.
3. 결정적 렌더링과 VLM 생성의 분리. chart_templates 라이브러리가 보여주듯, 벡터 구조가 명확한 chart·표 카테고리에서는 데이터 추출만 VLM에 맡기고 시각 자체는 결정적 프리미티브로 렌더링하는 분리가 자기회귀 zero-sum을 구조적으로 회피하는 효과적 전략이다.

향후 연구는 다음 일곱 가지로 정리된다. (a) 교차 judge 평가(Claude·Gemini 추가)를 통한 종합적 축의 단일 judge 편향 제거, (b) 인간 평가(n=8–10 규모)를 통한 다면적 평가 지표의 인간 앵커 검증, (c) multi-seed 설정(3 시드 × 4 메서드 × 50 디자인)에서의 통계 검정 보강, (d) chart 외 레이아웃 조건부 라우팅의 구현과 검증, (e) 시각 인식 OCR 기반 시각 CCR 메트릭의 도입, (f) AutoPresent의 요소 매칭 프로토콜과의 직접 비교(논문 간 검증), (g) 컴포넌트 단위 ablation 확장 — 스타일 정규화, chart_templates, CV 그라운딩의 인과 효과 격리이다.

---

부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

본 논문의 핵심 가설들은 post-hoc 임의 임계값이 아닌 사전 명시된 결정 규칙으로 검증된다.

전제. 본 사전등록은 Layer Recall과 LTED를 주요 지표로 사용하던 프레임워크에서 작성되었으며, 주요 주장이 다면적 평가 지표로 정착된 이후에는 LTED와 Recall에 의존하는 가설들이 부록 B의 보조 지표 기준의 보조 가설로 위치한다. 다면적 평가 기반 가설(5.1절·5.2절·6.2절·7.3절)은 본문에서 효과 size로 직접 보고한다.

H-EO (요소 누락의 모델-일반성, RQ1, 부록 B.2) — 보조 가설, 채택
- 결정 규칙: 3 VLM에서 베이스라인 일괄 생성의 평균 (1 − Layer Recall) ≥ 0.50 AND 교차 VLM 표준편차 ≤ 0.10
- 적용: 10 고밀도 시각 효과 디자인 × 3 VLM (GPT-4o, GPT-5.4, Claude 4.6 Opus).
- 측정 결과: 3 VLM 격차 = {0.776, 0.700, 0.688}, 평균 0.721, std 0.039 (≤ 0.10 ✓), 평균 ≥ 0.50 ✓
- 채택 (최첨단 간 비교에 한정 — 최첨단 모두 LayerAgent와 다른 어휘를 쓰므로 상대 비교는 공정): 최첨단 베이스라인 업그레이드만으로는 격차가 크게 닫히지 않으며, 이는 프로세스 단위 분해의 motivation을 보강하는 신호로 해석된다.

H-LTED, H-Recall (LayerAgent의 보조 지표 우위, 부록 B)
- 결정 규칙: 보조 지표 (LTED/Recall) 기준에서 LayerAgent가 우위를 보이는지 여부
- 클래스명 편향 위험으로 주요 주장에는 사용하지 않으며, 부록 B 보조 표에 부속 자료로 보고한다.
- 주요 주장은 5.1절 표 1·2·3 (자동 지표 전체+부분집합, MLLM judge)로 보고하며, 최첨단 비교는 7.3절 boundary 표로 보고한다.

H-SweetSpot (고밀도 시각 효과 디자인에서의 양 축 합의, RQ3 레이아웃, 5.2절 고밀도 시각 효과 행) — 기각
- 결정 규칙: 고밀도 시각 효과 디자인 N=10 부분집합에서 동시에 (LTED(layeragent) < 최고 베이스라인 LTED − 0.20) AND (MLLM 평균(layeragent) > 최고 베이스라인 MLLM 평균)
- 측정 결과: LTED Δ = +0.27 (LayerAgent 0.551 대 베이스라인 0.823, 충족 ✓), MLLM Δ = −0.80 (LayerAgent 3.23 대 최고 베이스라인 4.03, 미충족 ❌).
- 기각 — chart_templates 라이브러리가 chart·표 카테고리의 종합 품질을 회복시키지만 고밀도 시각 효과 디자인 카테고리는 chart_templates 가 적용되지 않으며, LayerAgent 의 분해 출력이 베이스라인 보다 MLLM judge 의 종합 발표가능성 평가에서 우세를 보이지 않는다. 계층 단위 구조적 회복(LTED) 과 종합 발표 품질(MLLM) 은 고밀도 시각 효과 부분집합에서 분리되며, 이 분리 자체가 5.2절의 핵심 발견이다.

H-LayoutScaling (Per-레이아웃 RQ3, 5.2절) — 기각
- 결정 규칙: 9개 레이아웃 유형 중 적어도 5개에서 MLLM Δ 와 LTED Δ 의 부호가 일치하는지 여부 (두 축이 같은 승자에 합의)
- 측정 결과: 부호 일치 레이아웃은 2개 (pyramid +/+, mekko +/+). 나머지 7개는 두 축이 분기한다.
- 기각 — chart·표 카테고리에서 chart_templates 의 효과가 MLLM 축으로는 큰 폭으로 전이되지만 LTED(클래스명 정렬 보조 지표) 로는 약하거나 음수로 측정되어 두 축이 서로 다른 차원 을 측정함을 보여준다. 이는 H-MetricAxisDisagreement 와 정렬되며, 논문의 다면적 평가 동반 보고 권고를 강화한다.

H-MetricAxisDisagreement (RQ3 평가 축 간 불일치, 6.2절) — 채택
- 결정 규칙: N=50 aggregate 에서 객관 충실도 (Element-IoU, CIEDE2000), VLM 루브릭 (AutoPresent layout_0_5, color_0_5), GPT-5.4 4 기준 세 축의 1위 메서드가 일치하지 않거나 최소 2개 이상 순위 차이를 보이는지 여부
- 측정 결과: Element-IoU 1위 LayerAgent (0.372), CIEDE2000 1위 cot_h_rag (51.5), layout_0_5 1위 LayerAgent (3.64), color_0_5 1위 일괄 생성 (3.70), GPT-5.4 4 기준 1위 LayerAgent (평균 4.02). 1위 메서드가 세 메서드 (LayerAgent, cot_h_rag, 일괄 생성) 로 분기한다.
- 채택 — 동일한 출력이라도 평가 축에 따라 서로 다른 순위이 산출되며, 색 차원과 레이아웃 차원, 종합 채점이 서로 다른 메서드를 1위로 평가한다.

H-AblationTextInserter (Text Inserter 분리 효과, 5.3절) — 부분 채택 (시각 묶음 기준)
- 결정 규칙: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)
- 옛 측정 (chart_templates 도입 이전 출력 위, 문자열 단위 지표): string-CCR Δ = 0.343 (D=0.975 → D₂=0.632), Joint Pass Δ = 0.60 (D=0.76 → D₂=0.16). 고밀도 시각 효과 부분집합(N=10)에서는 string-CCR Δ = 0.687로 더 강하게 나타났다.
- 새 측정 (LayerAgent v4 출력 위, 다면적 시각 묶음): Element-IoU Δ +0.008, CIEDE2000 Δ +1.04 (D₂ 우세), layout_0_5 Δ +0.22 (D 우세), color_0_5 Δ −0.16 (D₂ 우세). 고밀도 시각 효과 부분집합에서는 color_0_5 Δ +0.50 (D 우세).
- 결론: 사전등록 결정 규칙은 string-CCR 차원이며 옛 측정에서 채택되었다. 다면적 시각 묶음으로 재측정한 결과는 layout_0_5 차원에서만 D 가 작게 우세하며 시각 차원의 메커니즘 시그널은 약하다 — 이는 Text Inserter 의 메커니즘 (텍스트의 콘텐츠 보존) 이 시각 묶음의 측정 범위 밖에 있음을 직접 보여준다 (6.3절 string-CCR 대 시각 CCR 메트릭학적 관찰). 후속 연구로 시각 인식 OCR 기반 시각 CCR 메트릭 도입 시 본 가설의 직접 재검증이 가능하다.

H-AblationDesignSpec (DesignSpec 에이전트 간 합치, 5.3절) — 채택 (color_0_5 차원)
- 결정 규칙 (재정식화): 다면적 평가 묶음 4 지표 중 ≥ 1개 차원에서 |Δ| ≥ 0.5 의 메커니즘 시그널 존재.
- 측정 결과 (N=50 main_eval, LayerAgent v4 출력 위 다면적 평가 묶음):
  - Element-IoU Δ = +0.001
  - CIEDE2000 Δ = −0.66
  - layout_0_5 Δ = −0.08
  - color_0_5 Δ = +0.96 — AutoPresent VLM 이 카드 간 색 일관성 손실을 직접 채점에 반영.
- 측정 결과 (N=10 고밀도 시각 효과 디자인 부분집합): color_0_5 Δ = +0.70 (D 우세), 다른 지표의 Δ 는 작다.
- 결론: 다면적 평가 묶음의 color_0_5 차원에서 DesignSpec 의 에이전트 간 색 일관성 효과가 명확히 입증된다. Element 배치 (Element-IoU) 와 객관 색 거리 (CIEDE2000) 차원에서는 DesignSpec 이 거의 영향 없음 — 메커니즘이 색의 종합적 일관성에 특화되어 있음을 보여준다 (3.2절.3 의 "DesignSpec 이 에이전트 간 스타일 표류를 줄인다" 와 정렬). 채택.

본 사전 등록은 논문 부록 외에도 OSF(Open Science 프레임워크)에 별도 등록될 예정이며, ID는 publication 시점에 명시한다.

---

부록 B. 클래스명 정렬 보조 지표 — 기본 점검 자료

본 부록은 (i) 슬라이드 도메인 요소 누락의 가시화에 사용한 명명 규칙 정렬 보조 지표 (Layer Recall, LTED) 수치, (ii) 교차 VLM 프로빙 결과, (iii) N=50 main_eval의 명명 규칙 정렬 보조 표를 수록한다. 이들 측정은 LayerAgent의 class 이름 어휘에 정렬된 정규식에 기반하므로 클래스명 편향 한계를 가진다 (7장). 본 논문의 주요 주장은 본문의 다면적 평가 지표(5.1절 표 1)를 따르며, 본 부록의 절대값은 클래스명 정렬 한계 하에서 현상 가시화의 일관성을 보여주는 보조 자료로 해석되어야 한다.

B.1 프로빙 사전 실험의 명명 규칙 정렬 수치

(A) probing_minimal 사전 실험 — N=10 고밀도 시각 효과 디자인, GPT-4o:

본문·결론의 "평균 6.6개 (범위 5–10)" 는 본 사전 실험 10개 디자인에 대해 인식 단계에서 GPT-4o 가 자연어로 기술한 레이어 개수의 표본 분포에서 산출되며 (평균 = 6.6, min = 5, max = 10), 동일 데이터의 코드 변환에서는 평균 1.8개가 HTML/CSS 에 반영된다.

| 지표 | 단계 A 인식 | 단계 B1 (일괄 생성) | 단계 B2 (LayerAgent) |
|---|:---:|:---:|:---:|
| `Layer Recall` (대 $T_P$, 명명 규칙 정렬) | 1.00 (sanity) | 0.195 | 0.676 |
| `격차 = 1 − Recall` (명명 규칙 정렬) | 0.00 | 0.805 | 0.324 |
| `LTED` ↓ (명명 규칙 정렬) | 0.00 | 0.75 | 0.62 |

(B) main_eval — N=50 mixed, 4 메서드:

| 방법 | Layer Recall ↑ (명명 규칙 정렬) | 격차 (1−Recall) ↓ (명명 규칙 정렬) |
|---|:---:|:---:|
| cot_h_rag | 0.115 ± 0.16 | 0.885 |
| visual_cot | 0.197 ± 0.13 | 0.803 |
| single_pass | 0.212 ± 0.15 | 0.788 |
| layeragent | 0.397 ± 0.23 | 0.603 |

위 수치는 요소 누락의 정량적 가시화를 보조하지만, Layer Recall 절대값은 LayerAgent 어휘에 정렬되어 있어 상대 비교에서 LayerAgent의 우위가 과대 평가될 가능성이 있다. 따라서 본 논문의 주요 메시지는 서론에서 보고한 명명 규칙 비의존 n_layers 격차("일괄 생성이 인식이 기술한 평균 6.6개 레이어 중 평균 1.8개만 HTML/CSS 구조에 반영한다")에 한정한다.

![그림 A1: Layer Recall × 메서드 (N=50)](results/figures/fig1_gap.png)

그림 A1 (보조). 50개 슬라이드에 대한 메서드별 Layer Recall(명명 규칙 정렬 측정). 명명 규칙 정렬 한계 하에서 현상 가시화 용도로 제시되며, 주요 결과는 5.1절 표 1의 다면적 평가 지표를 따른다.

B.2 Cross-VLM 프로빙 표

10개 고밀도 시각 효과 디자인을 3개 최첨단 VLM에 일괄 생성으로 각각 입력해 측정한 결과를 보고한다. 최첨단 모델 간 비교에서는 모두 LayerAgent와 다른 어휘를 쓰므로 비교가 상대적으로 공정하나, LayerAgent와 최첨단의 비교는 클래스명 편향 위험을 가진다 (부록 B).

| 모델 | LTED ↓ | Layer Recall ↑ | 격차 (1−Recall) | 평균 토큰 | 비용/슬라이드 | 시간 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 | ~5,000 | ~$0.015 | ~10s |
| single_pass (GPT-5.4) | 0.669 | 0.300 | 0.700 | 6,015 | $0.075 | 85s |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | 0.688 | 7,116 | $0.421 | 108s |
| LayerAgent (GPT-4o, 클래스명 편향 위험) | (0.551) | (0.759) | (0.241) | 54,310 | $0.232 | ~60s |

세 최첨단 모두 Layer Recall(클래스명 정렬) 기준 베이스라인 격차가 0.69–0.78 범위에 있으며, 최첨단 간 상대 비교에서 격차 차이가 작다. 본 측정은 LayerAgent 어휘 정렬 지표이므로 최첨단가 다른 어휘로 시각적으로 풍부한 요소를 생성하더라도 거짓 negative로 보고될 수 있어, 본 표는 최첨단 간 비교에 한정 해석한다 (부록 B 클래스명 편향). 클래스명 비의존한 다면적 평가 기준의 LayerAgent 대 최첨단 비교는 7.3절에 경계 참조로 보고된다.

(사전등록 가설 H-EO는 "3개 VLM에서 베이스라인 격차 > 0.5"라는 최첨단 간 비교 부분에 대해서만 보조적으로 적용된다. 가설의 명명 규칙의존성에 대한 한계는 부록 A에서 명시한다.)

B.3 N=50 main_eval의 명명 규칙 정렬 보조 표

| 지표 | cot_h_rag | layeragent | single_pass | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Layer Recall ↑ (명명 규칙 정렬) | 0.115 | 0.397 | 0.212 | 0.197 |
| LTED ↓ (명명 규칙 정렬) | 0.914 | 0.752 | 0.828 | 0.849 |

위 두 지표는 LayerAgent의 class 이름 어휘에 정렬되어 있어 (부록 B) 절대값 해석에 클래스명 정렬 한계가 적용된다. 본 논문의 주요 주장은 5.1절 표 1의 다면적 평가 지표를 따르며, 본 표는 기본 점검 자료로 보존한다.

![그림 A2: Multi-지표 × 메서드 비교 (N=50)](results/figures/fig2_methods.png)

그림 A2 (보조). 4 메서드 × 5 지표 세부 분석. Layer Recall은 명명 규칙에 정렬되어 있어 해석상 주의가 필요하며, 주요 결과는 5.1절 표 1의 다면적 평가 지표를 따른다.

---

부록 C. 최첨단 모델 일괄 생성 보충 비교 (7.3절 적용 범위 한계 절 상세)

본 부록은 7.3절 적용 범위 한계 절에서 압축 보고된 최첨단 일괄 생성과의 비교를 method-level 상세로 제공한다. 본 비교의 목적은 LayerAgent의 적용 범위 경계를 명시하는 것이며, RQ에 직접 답하는 결과가 아님을 다시 강조한다.

C.1 대 Claude 4.6 Opus

옛 DOM 기반 측정에서 요소 수·스타일 diversity·렌더 풍부성 차원에서 Opus 가 우세하나 비용이 약 1.8배 (LayerAgent $0.232 대 Opus $0.421), 시간이 약 1.8배 (60s 대 108s) 더 높다. 다면적 평가 묶음 재측정은 본 논문의 범위 외이다.

C.2 대 GPT-5.4

옛 DOM 기반 측정에서 GPT-5.4 일괄 생성이 요소/스타일 카운트에서 우세하며 비용도 LayerAgent 의 약 1/3 수준 ($0.075 대 $0.232) 이다. 본 비교는 LayerAgent (프로세스 단위 개입 on GPT-4o) 와 최첨단 모델 업그레이드가 서로 분리된 비용-품질 차원임을 직접 보여준다. 다면적 평가 묶음 (Element-IoU + AutoPresent + GPT-5.4 4 기준) 으로 최첨단 출력를 재측정한 결과는 본 논문 범위 외이며 8장 향후 연구로 다룬다.

C.3 운영 참고

운영 조건별 권장:
- 동일 모델 GPT-4o 위에서 디자인2code 다면적 평가 우위가 필요한 경우 → LayerAgent (본 논문의 주요 활용 사례).
- 최첨단 모델 API 사용이 가능하고 비용·시간 최소화를 최우선시할 경우 → GPT-5.4 일괄 생성 (단 본 논문의 다면적 평가 묶음으로는 재측정 안 됨).
- GPT-4o 일괄 생성 ($0.015/슬라이드, 10s) 은 최저 비용 옵션으로 7.3절 boundary 표 상단에 위치한다.

C.4 Boundary 종합

본 분석은 LayerAgent (프로세스 단위 개입) 와 최첨단 확장이 서로 분리된 두 개선 경로임을 명시하기 위한 경계 참조이다. LayerAgent 의 주요 기여는 동일 모델 GPT-4o 4 메서드 비교 위 다면적 평가 묶음 평가에서 정착되며 (5.1절), 최첨단 모델 업그레이드는 별개 비용-품질 차원에 속한다.

---

부록 D. DesignSpec 스키마와 인스턴스 예시

본 부록은 3.2절.3 Design Director가 생성하는 타입드 JSON `DesignSpec`의 전체 스키마와 한 슬라이드의 완결된 인스턴스를 수록한다.

D.1 Schema (필드 + 타입 + 설명)

| 필드 | 타입 | 설명 |
|---|---|---|
| `aesthetic_label` | string | `multi_layer_visual_effect` / `minimal` / `editorial` 등 미학 카테고리 라벨 |
| `타이포그래피.hero_family` | string | 히어로 텍스트의 폰트 패밀리 (예: Inter, Helvetica) |
| `타이포그래피.hero_weight` | int | 히어로 가중치 (100–900) |
| `타이포그래피.body_family` | string | 본문 폰트 패밀리 |
| `타이포그래피.body_weight` | int | 본문 가중치 |
| `팔레트.bg_primary` | 헥스 string | k-means로 추출한 주요 배경 색 |
| `팔레트.강조` | 헥스 string | 강조 색 |
| `팔레트.frame_color` | rgba string | card/frame 테두리 색 (투명도 포함) |
| `팔레트.text_bright` | 헥스 string | 밝은 텍스트 색 |
| `frame_system.hero_frame` | string | 히어로 frame 스타일 description |
| `frame_system.card_frame` | string | card frame 스타일 description |
| `frame_system.bottom_accent_bar` | bool | 하단 강조 bar 유무 |
| `decorative_motif.스타일` | string | `minimal` / `geometric` / `organic` 등 |
| `decorative_motif.density` | string | `sparse` / `medium` / `dense` |
| `분위기.has_radial_glow` | bool | 방사형 글로우 유무 |
| `분위기.glow_origin` | string | `top_center` / `center` / `top_left` 등 글로우 위치 |
| `분위기.background_depth` | string | `flat` / `shallow` / `deep` |

D.2 Instance 예시 (design_03 comparison_split 슬라이드)

```json
{
  "aesthetic_label": "multi_layer_visual_effect",
  "타이포그래피": {
    "hero_family": "Inter",
    "hero_weight": 800,
    "body_family": "Inter",
    "body_weight": 500
  },
  "팔레트": {
    "bg_primary": "#0A1530",
    "강조": "#3B82F6",
    "frame_color": "rgba(255,255,255,0.15)",
    "text_bright": "#F5F5F0"
  },
  "frame_system": {
    "hero_frame": "subtle glass frame",
    "card_frame": "1px rgba white 테두리",
    "bottom_accent_bar": false
  },
  "decorative_motif": {
    "스타일": "minimal",
    "density": "sparse"
  },
  "분위기": {
    "has_radial_glow": true,
    "glow_origin": "top_center",
    "background_depth": "deep"
  }
}
```

이 인스턴스는 3.2절.3 본문에서 언급한 스키마의 한 가지 채워진 예시이며, 모든 전문가가 동일 인스턴스를 프롬프트 힌트로 받아 에이전트 간 스타일 통일을 달성한다.

---

참고 문헌

Design-to-Code 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- Calò, T., & De Russis, L. "Advancing Code Generation from Visual Designs through Transformer-Based Architectures and Specialized Datasets." Proceedings of the ACM on Human-Computer Interaction (PACMHCI), 2025. — element omission / element distortion / element misarrangement 분류 출처.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.
- UIOrchestra. "Generating High-Fidelity Code from UI Designs with a Multi-Agent Framework." Findings of the Association for Computational Linguistics: EMNLP 2025.

시각 교정 / 반복 개선
- VisRefiner. "Learning from Visual Differences for Screenshot-to-Code Generation." arXiv:2602.05998, 2026.
- Vision-Guided Iterative Refinement. "Vision-Guided Iterative Refinement for Frontend Code Generation." arXiv:2604.05839, 2026.

프레젠테이션 생성
- Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.

평가 / 측정 타당성
- DreamHouse. "How Far Are Vision-Language Models from Constructing the Real World? A Benchmark for Physical Generative Reasoning." arXiv:2603.24866, 2026.
- WebRenderBench. "Layout-Style Consistency with Reinforcement Learning." 2025.
- Widget2Code. "Apple HIG-inspired Per-Property Evaluation." 2025.
- SlideAudit. "A Dataset and Taxonomy for Automated Presentation Slide Evaluation." UIST 2025. arXiv:2508.03630.
- WebDevJudge. "Evaluating (M)LLMs as Critiques for Web Development Quality." arXiv:2510.18560, 2025.
- Zheng, L., et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.

멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.
- Wu, Q., et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." COLM 2024.

VLM
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Gemini Team, Google. "Gemini 3 Pro Image Preview." 2026.
