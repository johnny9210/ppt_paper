LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크

디자인 이미지의 계층 구조 인식을 통한 프레젠테이션 코드 생성

by 정일균 (Ilgyun Jeong)

인공지능융합학과 (Department of Artificial Intelligence Convergence)

지도교수: 김현철 (under the supervision of Professor Hyeoncheol Kim)

---

초록

프레젠테이션 슬라이드는 배경·카드·콘텐츠·아이콘 등 여러 시각 층이 위아래로 겹쳐 구성되는 계층적 시각 구조다. 본 논문은 GPT-4o가 슬라이드 이미지를 자연어로는 평균 6.6개(범위 5–10)의 레이어로 기술하면서 같은 이미지를 HTML로 변환할 때는 평균 1.8개만 코드에 반영하는 인식–생성 격차를 관찰하고, 이를 슬라이드 도메인의 계층적 요소 누락 현상으로 정식화한다. 이를 다루기 위해 단일 VLM 호출을 8개 전문 에이전트의 레이어 단위 분해로 재구성하는 멀티에이전트 프레임워크 LayerAgent를 제안한다.

평가 결과 LayerAgent 는 동일 GPT-4o 조건의 4 메서드 비교에서 객관 디자인 충실도 (Element-IoU 0.372, sp 0.314 대비 +18%) 와 교차 모델 MLLM-as-a-judge (GPT-5.4 4 기준 평균 4.02 대 차순위 3.37) 두 축에서 1위에 위치한다. 다만 효과는 레이아웃 유형에 따라 비균일하다 — chart·표 카테고리에서는 chart_templates 결정적 렌더링으로 큰 폭 우위 (MLLM Δ +0.15 ~ +1.90), 고밀도 시각 효과 카테고리에서는 객관 충실도는 회복되지만 MLLM 종합 judge 는 베이스라인 보다 낮게 평가되는 분기가 관찰된다.

본 논문의 기여는 (a) 슬라이드 도메인 계층적 요소 누락 정식화, (b) DesignSpec blackboard · Text Inserter · chart_templates 결정적 렌더링을 포함한 멀티에이전트 레이어 분해 프레임워크 LayerAgent (DesignSpec 은 카드 간 색 일관성 차원에서 인과 효과 격리 입증, Text Inserter 는 고밀도 시각 효과 부분집합에서 시각 묶음 영향 관찰), (c) 객관 충실도 + VLM 루브릭 + 교차 모델 judge 를 함께 보고하는 Design2Code 다면적 평가 방식이다. LayerAgent 는 동일 GPT-4o 조건의 파이프라인 분해 접근이며, 최첨단 모델 확장과는 분리된 개선 경로로 해석된다.

키워드: 요소 누락 (Element Omission), 계층 분해 (Layer Decomposition), 멀티에이전트 (Multi-Agent), 디자인-투-코드 (Design2Code), 시각 언어 모델 (Vision Language Models)

---

제 1 장. 서론

1.1 슬라이드 도메인의 계층적 요소 누락

본 논문은 프레젠테이션 슬라이드의 디자인-투-코드(Design2Code) 자동 변환 문제를 다룬다. 슬라이드는 배경·카드·차트·텍스트·아이콘 등 여러 시각 층이 정확한 stacking order와 좌표로 겹쳐 구성되는 계층적 시각 객체이며, 이 계층 구조가 HTML/CSS 코드 차원에서 보존되어야 의도된 디자인이 재현된다. 그러나 단일 VLM 호출은 이 계층 구조를 충분히 반영하지 못한 채 HTML을 위에서 아래로 한 번에 생성한다 — `<div>` 태그가 직렬로 나열되고, 층의 명시적 순서 표기(CSS `z-index`)는 거의 사용되지 않으며, 요소 간 공간 관계는 DOM 작성 순서에 암묵적으로 의존한다.

출발점은 다음의 관찰이다. 같은 GPT-4o [25]에게 이미지의 계층 구조를 자연어로 기술하라고 요청하면 평균 6.6개(범위 5–10)의 레이어를 인식하지만, 같은 이미지를 HTML로 변환하라고 요청하면 평균 1.8개만 코드에 반영된다 (부록 B.1). 이 현상을 슬라이드 도메인의 (계층적) 요소 누락이라 부른다 — Design2Code 선행 연구 [3] 에서 개별 요소 단위로 보고된 요소 누락이 슬라이드 도메인에서는 시각 계층(레이어) 단위로 통째 누락되는 형태로 확장되어 나타난다. 이는 메트릭 이름이 아니라 현상의 이름이며, 이를 직접 표적하는 단일 신규 메트릭은 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 측정이 순환적(circular)이 되기 때문이다.

1.2 연구 질문과 접근

기존 Design2Code 연구는 분할 정복(DCGen [4]), 레이아웃 명시화(LaTCoder [5]), 3-stage 에이전트 파이프라인(ScreenCoder [6], DesignCoder [7])으로 이미지-코드 품질을 일반적 문제로 다루어 왔고, 프레젠테이션 생성 연구(PPTAgent [11], PreGenie [12], SlideCoder [13], AutoPresent [14])는 템플릿 수정·코드 리뷰·세그멘테이션 기반 생성에 초점을 두었다. 그러나 슬라이드의 시각 계층이 HTML/CSS 생성 단계에서 레이어 단위로 통째 누락되는 현상 자체를 직접 문제화하고 파이프라인 분해로 다룬 연구는 없다.

이로부터 연구 질문이 도출되며, 다음 세 하위 질문으로 분해된다.

RQ1. GPT-4o 급 VLM 은 슬라이드 이미지를 자연어로는 계층적으로 인식하면서 HTML/CSS 생성에서는 해당 계층을 누락하는가? 그리고 이 격차는 최첨단 VLM (GPT-5.4, Claude 4.6 Opus) 에서도 같은 양식으로 관찰되는가? (5.1절 · 부록 B 상세)

RQ2. LayerAgent 는 동일 GPT-4o 조건에서 일괄 생성 및 프롬프트 수준 변형 (visual_cot, cot_h_rag) 보다 객관 충실도 (Element-IoU, CIEDE2000) 와 MLLM-as-a-judge (AutoPresent 0–5, GPT-5.4 4 기준) 두 축에서 우수한가? (5.2절 · 5.4절)

RQ3. LayerAgent 의 효과는 레이아웃 유형 (chart·표·다이어그램 대 고밀도 시각 효과 대 비차트 일반) 과 평가 축 (객관 매칭 대 VLM 루브릭 대 종합적 judge) 에 따라 어떻게 달라지는가? (5.3절 레이아웃 · 6.3절 평가 축)

이를 위해 LayerAgent를 제안한다. 단일 VLM 호출을 전체 이미지 분석 → 공유 DesignSpec 작성 → 8개 전문 에이전트의 병렬 레이어 생성 → 결정적 z-index 조립 → 카드 간 스타일 통일 → 텍스트 주입의 다단계 파이프라인으로 분해함으로써, 각 호출이 구조·스타일·콘텐츠를 동시에 짊어지지 않고 한 가지 책임만 지도록 설계했다 (3장). 효과는 단일 지표가 레이어 보존의 다면성을 모두 포착하지 못하므로 Design2Code 다면적 평가 묶음 (객관 충실도, VLM 루브릭, 교차 모델 judge — 지표 세부는 4.3절) 으로 함께 측정한다.


---

제 2 장. 관련 연구

2.1 Design2Code 생성

Design2Code [1] 는 484 웹페이지 벤치마크로 GPT-4V의 중간 충실도를 보고했다. WebSight [2] 는 200만 합성 이미지-코드 쌍를 공개했다. Calò & De Russis [3] 는 GPT-4o의 UI 코드 생성 실패를 요소 누락 · 요소 distortion · 요소 misarrangement의 세 유형으로 분류했다 — 본 논문은 이 중 요소 누락을 슬라이드 도메인의 시각 계층 단위로 확장하여 분석한다 (부록 B). DCGen [4] 은 분할 정복으로 페이지를 블록 단위로 분해해 코드를 생성한다. LaTCoder [5] 는 코드 이전에 레이아웃을 chain-of-thought로 명시화한다. ScreenCoder [6] 는 Grounding → Planning → 생성의 3-stage 에이전트 파이프라인을 채택하고 50K 이미지-코드 쌍로 GRPO 미세조정한다. DesignCoder [7] 는 모바일 UI 도메인에서 UI 그룹화 → Hierarchy-Aware 생성 → 사후 렌더 Self-Correcting Refinement의 3-stage를 사용한다. UIOrchestra [8] 는 멀티에이전트 프레임워크로 UI 디자인에서 code로의 변환을 다루며 본 논문과 가장 가까운 선행 연구이다. 다만 LayerAgent의 DesignSpec blackboard, CV 그라운딩, 결정적 chart_templates · FontAwesome 라이브러리 통합 구조와는 차별된다.

LayerAgent와의 차별점. ScreenCoder [6]는 이미지 패치 reuse(Hungarian 매칭)로 요소 간 일관성을 다루고, DesignCoder [7]는 사후 렌더 반복 개선으로 코드 품질을 다룬다. LayerAgent 의 Style Normalizer는 사전 렌더 CSS 정규화에 해당하고, Text Inserter는 시각과 콘텐츠 단계의 분리에 해당하며, DesignSpec blackboard는 생성 시점의 에이전트 간 스타일 통일에 해당한다. 기존 Design2Code 평가는 주로 단일 지표 또는 분류된 지표 그룹을 보고했으며, 본 논문은 슬라이드 도메인에서 객관 디자인 충실도와 VLM 루브릭, 교차 모델 judge 를 결합하여 함께 보고하는 Design2Code 다면적 평가 방식을 적용한다는 점에서 차별화된다 (4.3절). 종합하면, 기존 Design2Code 계열은 이미지-코드 품질을 일반적 문제로 다루는 반면, 슬라이드 도메인 특유의 레이어 단위 요소 누락 자체를 직접 문제화하고 레이어 단위 생성 분해로 다룬다는 점이 핵심 차이다.

2.2 시각 교정 / 반복 개선

VisRefiner [9] 는 렌더링 결과와 참조 디자인 간 시각 차이를 학습하여 GPT-4o 대비 Block-Match +21.5pt를 달성했다. Vision-Guided Iterative Refinement [10] 는 VLM critic 기반 3회 반복으로 17.8% 개선을 보고했다. LayerAgent 의 Visual Critic 단계는 이들의 반복 대 단발 trade-off 를 선택 단계로 구현하며 (3.5절), 주요 결과는 기본 비활성 조건에서 보고한다.

2.3 프레젠테이션 생성

PPTAgent [11] 는 LLM 피드백 기반 템플릿 반복 수정을, PreGenie [12] 는 코드 리뷰와 페이지 리뷰의 이중 루프를, SlideCoder [13] 는 CGSeg 세그멘테이션과 계층적 RAG를, AutoPresent [14] 는 구조화된 시각 설계 원칙을 강조했다. 이들 선행 연구는 주로 템플릿 수정, 코드 리뷰, 세그멘테이션 기반 생성, 구조화된 설계 원칙에 초점을 두었다. 반면 본 논문은 슬라이드의 시각 계층이 HTML/CSS 생성 단계에서 누락되는 현상에 초점을 맞추고, 이를 계층 단위 생성 분해와 Design2Code 다면적 평가의 병행 보고로 분석한다는 점에서 차별화된다 (4.3절). 종합하면, 기존 발표자료 생성 계열은 템플릿·콘텐츠·슬라이드 단위 생성 자체를 다루는 반면, HTML/CSS 단위의 레이어 충실도를 핵심 문제로 직접 다룬다는 점이 핵심 차이다.

2.4 멀티에이전트 코드 생성

MetaGPT [21], ChatDev [22], CAMEL [23], AutoGen [24] 은 소프트웨어 개발 프로세스(설계, 구현, 테스트의 순서) 또는 대화형 멀티에이전트 대화으로 에이전트를 분담한다. LayerAgent는 (a) 개발 프로세스가 아니라 출력의 시각 계층(레이어) 구조(배경, 카드, 텍스트, 아이콘의 순서)에 따라 분담하며, (b) 에이전트 간 통신을 자연어나 코드가 아니라 DesignSpec JSON과 바운딩 박스 JSON으로 구성된 타입드 blackboard로 수행하여 잘림과 해석 오류를 구조적으로 제거한다. 종합하면, 기존 멀티에이전트 code 생성은 역할·개발 프로세스·대화 흐름에 따른 분업이지만, LayerAgent는 출력의 시각 계층(레이어)에 따른 분업이라는 점이 본질적 차이다.

2.5 Design2Code 평가

기존 평가는 전역 유사도, 구조 매칭(Design2Code [1] 의 Block-Match, AutoPresent [14] 의 요소 매칭), 속성 수준(WebRenderBench [16] 의 SDA, Widget2Code [17] 의 속성별) 으로 분류된다. DreamHouse [15] 는 physical generative reasoning(건축 구조물 생성) 도메인에서 구조적 타당성과 시각 충실도가 직교적이며 최첨단 VLM 의 결합 통과율이 7.1% 에 불과함을 보였으며, 이 직교성 발견은 본 논문에서 슬라이드 도메인으로 평행하게 적용된다. SlideAudit [18] 은 슬라이드 품질 분류 체계를 정립하고 자동화된 지표와 종합적 인간 판정 사이의 체계적 불일치를 정량적으로 보였으며, 이는 6.3절 평가 축 간 불일치 관찰과 직접 정렬되는 선행 연구이다. AutoPresent [14] 는 레이아웃·색 두 차원 0–5 루브릭을 정립했으며, 이를 주요 지표의 한 축으로 사용한다. WebDevJudge [19] 는 Design2Code 에서 MLLM-as-a-judge 의 평가 관행 (쌍별 평가와 code·시각 양식 결합) 을 제안했으며, 7장의 단일 judge 한계 논의에서 참조로 인용한다. 본 논문은 (a) DreamHouse [15] 와 SlideAudit [18] 두 도메인의 지표 불일치 발견을 슬라이드 Design2Code 도메인의 다면적 평가로 확장하고, (b) 객관 요소 단위 매칭 (Element-IoU) 과 색 거리 (CIEDE2000), AutoPresent 루브릭, 교차 모델 MLLM-as-a-judge 를 결합하여 클래스명에 의존하지 않고 정렬한 Design2Code 다면적 평가 프로토콜을 구성함으로써 메서드별 클래스명 차이에 따른 평가 편향을 줄인다.

---

제 3 장. LayerAgent 프레임워크

3.1 전체 구조

LayerAgent 의 전체 파이프라인은 그림 1 에 도식화되어 있다 — Chat Parser 의 입력 정규화부터 단계별 전문가 병렬 실행, 결정적 조립까지의 전체 흐름을 한 눈에 보여준다.

![그림 1: LayerAgent architecture](results/figures/layeragent_architecture.png)

3.2 입력 분석과 DesignSpec 구축

3.2.1 Chat Parser — 입력 정규화

사용자는 LayerAgent 에 자유 형식 자연어 메시지와 참조 디자인 이미지를 함께 제공한다. Chat Parser는 두 입력을 받아 타입드 JSON `slide_spec`을 출력한다 — `slide_type` ∈ {19종 어휘}, `콘텐츠` (slide_type별 구조화 필드), `스타일` (4개 헥스 색상). slide_type은 이미지의 시각 형태를 1차 신호로, 사용자 메시지를 2차 신호로 결정한다 — 예컨대 "여러 색의 라인이 있으면 multi-series line_chart", "1 root → N branches → M leaves 트리는 pyramid가 아닌 tree_diagram" 등 형태 기반 분기 규칙이 프롬프트에 명시된다. 이는 후속 에이전트들이 동일한 어휘를 공유하도록 보장하여 분기 모호성으로 인한 레이어 환각·붕괴를 사전 차단한다.

3.2.2 Analyzer

전체 이미지를 입력받아 (a) 레이아웃 유형(`timeline / dashboard / hub_spoke / pyramid / grid / 분할 / vertical_stack / freeform`)과 (b) 각 카드·히어로·장식 요소의 정규화된 바운딩 박스(0–1 비율)를 출력한다. 이 출력은 이후 모든 크롭과 배치의 기준점이 된다. slide_type 이 chart_templates 적용 7종 (bar_chart, line_chart, waterfall, matrix_2x2, mekko, harvey_table_advanced, tree_diagram; 이하 chart_templates 7종) 중 하나인 경우, Analyzer 는 카드·히어로 영역을 비워 반환하여 차트 위에 카드 레이어가 겹쳐지지 않도록 한다.

3.2.3 Design Director — DesignSpec Blackboard

전체 이미지와 CV facts(k-means 팔레트, OCR 텍스트 높이 분포, HSV 채도)를 입력받아 타입드 JSON `DesignSpec`을 출력한다. DesignSpec은 6개의 top-level 필드로 구성된다 — `aesthetic_label` (multi_layer_visual_effect / minimal / editorial 등), `타이포그래피` (hero·본문의 폰트 패밀리와 가중치), `팔레트` (k-means로 추출된 배경·강조·frame·text 색상), `frame_system` (hero·card 테두리 스타일과 bottom 강조 bar 유무), `decorative_motif` (스타일·density), `분위기` (radial 글로우 유무·원점과 배경 깊이).

이후 모든 전문가는 DesignSpec을 프롬프트 힌트로 받는다. 결과적으로 카드 A의 반투명 효과가 카드 B에서 단색으로 변하는 스타일 표류가 사전적으로 차단된다 — 이는 단순한 분해 접근에서 자주 관찰되는 실패 양식이다.

CV 그라운딩 (k-means k=6 팔레트 / OCR 텍스트 높이 / HSV 채도) 은 각각 색 환각, 폰트 크기 결정, 미학 분류를 그라운드하며 `no_cv_facts` 플래그로 격리 측정 가능하다.

3.3 전문 에이전트 병렬 레이어 생성

8개 전문가는 Design Director의 출력 이후 병렬로 실행되며, 두 그룹으로 나뉜다 — 모든 슬라이드에서 활성화되는 레이어 전문가 4개와 slide_type·콘텐츠에 따라 조건부 활성화되는 전문가 4개. 본 8개 는 에이전트 유형 기준이며, 그 중 Card Detail 과 Hero Detail 은 Analyzer 가 검출한 요소 수에 따라 동적으로 여러 인스턴스로 실행된다.

3.3.1 Base BG · Atmosphere · Decoration

전체 이미지와 DesignSpec 을 입력받아 배경 그라디언트, radial 글로우, decoration shape 를 분리된 레이어로 생성한다. 이러한 분리는 분위기와 패턴이 같은 z=0 안에서 충돌하지 않도록 보장한다.

3.3.2 Card Detail (× N)

각 카드의 크롭 이미지 (주변 패딩 포함) 와 DesignSpec 을 입력받아 카드별로 풍부한 CSS 효과 (`backdrop-filter`, 다중 `box-shadow`, rgba 투명도, 테두리 효과) 를 생성한다. 좁은 시각 범위가 선택적 CSS 재질 (반투명, blur, 그라디언트 등) 을 회복시킨다 — 통제 실험에서 같은 GPT-4o 가 전체 이미지에서는 카드당 CSS 효과 2.8개를, 크롭에서는 6–8개를 생성한다.

3.3.3 Hero Detail (× N)

히어로 블록 (큰 숫자, 메인 메시지, 특수 그래픽) 을 크롭 단위로 별도 처리한다.

3.3.4 Icon Agent

카드별 의미 분석 → FontAwesome 클래스 검색 → 실제 `<i class="fa-...">` 태그 주입의 순서로 동작하며, 환각된 아이콘 URL 을 구조적으로 차단한다.

3.3.5 Chart Agent · Table Agent

슬라이드 타입이 chart_templates 7종 (3.2.2절 정의) 중 하나일 때 `chart_templates` 라이브러리의 7 renderer 가 슬라이드 전체를 결정적으로 렌더링한다 (renderer 별 capability 상세는 부록 C). VLM 호출은 chat_parser 단계의 데이터 추출에 한정되며, 시각 자체는 SVG/HTML 프리미티브로 결정적으로 산출되므로 자기회귀 토큰 예산이 시각·콘텐츠 간 zero-sum 을 일으키지 않는다 (6.1절).

3.4 결정적 조립과 스타일 정규화

3.4.1 Assembler

8개 전문가의 HTML 단편을 z-index band([0, 5, 10, 20, 30, 40])로 결정적으로 쌓는다. 단순 concat이 아니라 절대 좌표(Analyzer의 바운딩 박스 정규화 비율 × 1280×720)와 z-index를 명시적으로 부착한다.

3.4.2 Style Normalizer

조립된 HTML을 텍스트 입력만 받아 카드 간 CSS 속성을 통일한다:

- 배경 rgba alpha — 모든 카드 동일값
- 테두리 색상/두께 — 통일
- border-radius — 통일
- box-shadow — 통일
- backdrop-filter blur — 통일

불변 보장: position, left, 최상위, width, height, z-index은 변경하지 않는다. 이미지 입력 없이 코드만 보는 텍스트 전용 에이전트로, 각 카드의 독립 생성에서 발생한 표류를 사후 동기화한다. 이 효과는 `no_style_norm` 플래그로 격리해 측정할 수 있다.

3.4.3 Text Inserter

완전히 스타일링된 HTML(배경, 카드, 정규화된 스타일)과 콘텐츠 데이터(제목, 설명, 메트릭, 리스트)를 입력받아, 기존 카드 구조 내의 빈 컨테이너를 식별하고 텍스트를 주입한다.

이 단계의 핵심은 시각 디자인을 먼저 확정한 뒤 텍스트를 주입한다는 순서에 있다. 단일 VLM 에서 풍부한 CSS 생성과 정확한 텍스트 배치가 zero-sum 경쟁을 벌이는 현상 (6.2절 H-RAG 역설) 을 단계 분리로 완화하기 위한 설계이다. 이 효과는 `no_text_inserter` 플래그로 격리해 측정할 수 있다.

3.5 선택 단계 (Overflow Repair · Visual Critic)

3.5.1 Overflow Repair

조립된 HTML을 Playwright로 렌더링한 뒤 측정한 바운딩 박스 오버플로를 분석하여 폰트 크기, 패딩, 줄 수를 미세 조정한다. 시각 critic과 달리 결정적 측정에 기반하므로 LLM 호출이 필요 없다.

3.5.2 Visual Critic

Playwright 스크린샷과 원본 이미지를 비교한 뒤 VLM이 diff를 작성하고 CSS 속성 단위로 보정한다. iteration 비용이 크므로 기본값은 비활성화이다.

3.6 구현

전체 파이프라인은 LangGraph StateGraph 로 구현되며 (Chat Parser 가 그래프 진입 노드, 8 전문가는 Design Director 출력 이후 병렬 실행), 모든 실험은 GPT-4o, Playwright 환경에서 수행되었다. LayerAgent 의 두 메커니즘 (DesignSpec blackboard 와 Text Inserter) 의 인과 효과는 5.4절에서 다면적 평가 묶음으로 격리 측정되며, 각 ablation 은 해당 컴포넌트를 noop 으로 대체하는 방식으로 구성된다 (`no_designspec` flag → D₄, `no_text_inserter` flag → D₂).

---

제 4 장. 실험 설정

4.1 데이터 — 계층화된 슬라이드 디자인 평가셋

평가셋은 50개의 계층화된 슬라이드 디자인으로 구성되며, 두 그룹으로 나뉜다.

(a) 고밀도 시각 효과 디자인 그룹 (N=10): 10개의 서로 다른 레이아웃 (timeline, dashboard, comparison_split, pyramid, hub_spoke, before_after, feature_grid, roadmap, layered_stack, stats_hero) 에 글로우, glassmorphism, 반투명 카드, 그림자, 테두리, z-index 중복 등 복합 CSS 효과가 높은 밀도로 포함된 시각 조건의 슬라이드들이다. `dark_glass` 는 해당 N=10 그룹의 내부 생성 라벨이며, 이후 본문에서는 이를 고밀도 시각 효과 디자인 부분집합으로 지칭한다.

(b) 차트·다이어그램 그룹 (N=40): 8개 레이아웃 (mekko, matrix_2x2, waterfall, harvey_table, bar_chart, line_chart, process_flow, pyramid)에 5종 비즈니스 컨설팅 스타일(minimal_white, editorial_warm, bain_red, bcg_green, mckinsey_blue)을 적용한 슬라이드로, 시각 효과 밀도가 상대적으로 낮다.

모든 슬라이드는 Gemini 3 Pro Image Preview [26] 로 생성됐다. 전체 데이터셋에서 LayerAgent의 구조 복원 효과를 평가하며, 레이아웃/theme 그룹에 따른 효과 변화는 5.3절 레이아웃별 세부 분석에서 보고한다.

데이터 중복 명시. 부록 B.1 인식–생성 격차의 motivation을 만든 N=10 사전 실험 슬라이드는 (a) 그룹의 N=10과 동일하다. 따라서 5.3절의 고밀도 시각 효과 디자인 부분집합 결과는 부록 B.1 과 동일한 슬라이드에서 측정되며, motivation 과 검증이 같은 데이터에서 일어난다는 단서 하에 해석되어야 한다 (7장 한계).

4.2 비교 메서드

〈표 1〉 동일 GPT-4o 기반 4 메서드 매핑.

| code | 메서드 (논문 표시) | 접근 |
|---|---|---|
| A | 일괄 생성 (`single_pass`, 이하 sp) | 단일 GPT-4o 호출로 전체 이미지 → HTML |
| B | 시각 분석 생성 (`visual_cot`) | 시각 분석을 자연어로 먼저 수행한 뒤 코드 생성 (2단계) |
| C | 패턴 주입 생성 (`cot_h_rag`) | 시각 분석 + CSS 효과 패턴 레시피(RAG)를 함께 제공해 코드 생성 |
| D | LayerAgent (`layeragent`) | 본 논문 — 계층 단위로 생성 책임을 분해하는 멀티에이전트 전체 파이프라인 |

모든 메서드에 동일한 콘텐츠 데이터, 동일한 모델(GPT-4o), 동일한 시드(시드=0)를 제공한다.

4.3 평가 방식 — Design2Code 다면적 평가

주요 결과는 Design2Code 평가의 다면적 평가 묶음으로 보고한다 — 객관적 시각 매칭 (Element-IoU; 요소 단위 Hungarian 매칭 기반), 색 정확도 (CIEDE2000), MLLM-as-a-judge 루브릭 (AutoPresent 0–5 레이아웃/색, GPT-5.4 4 기준). Layer Recall 과 LTED 는 부록 B 에 정리한 클래스명 편향 위험으로 보조 지표로 분류된다.

축 ① 객관적 디자인 충실도 (Design2Code 계열):

Playwright 로 렌더링한 PNG 와 참조 PNG 사이의 객관적 매칭을 측정한다. Class 이름이나 사전 정의된 레이어 label 에 의존하지 않으며 모든 메서드에 동일하게 적용된다 (메서드 비의존).

- Element-IoU ↑ — Hungarian 매칭 기반 요소 단위 IoU. Generated 요소는 Playwright 로 렌더링한 HTML 의 visible DOM 요소 바운딩 박스와 computed 스타일 색으로 추출하고, 참조 요소는 참조 PNG 에 대해 경계 영역에서 샘플링된 배경 색과의 색 거리 ≥25 픽셀의 connected components (skimage.label, 최소 면적 1500 px², 최대 30 패널 후보) 로 산출한다. 이후 바운딩 박스 IoU 를 cost 로 한 linear sum assignment (Hungarian) 로 1:1 대응을 찾고 matched pairs 의 mean IoU 를 보고한다. Class 이름·DOM 구조에 의존하지 않으며 모든 메서드에 동일하게 적용된다 (메서드 비의존). Design2Code [1] Block-Match 와 유사한 요소 단위 매칭 계열 지표이다. 다만 connected-components 기반 참조 추출은 글로우·blur·그라디언트·그림자 같이 경계가 부드러운 분위기 효과를 개별 요소로 안정적으로 분리하지 못할 수 있어, Element-IoU 는 구조적 요소 정렬에는 적합하지만 고밀도 시각 효과의 분위기적 품질을 완전히 포착하지는 못한다 (5.3절·7.2절의 고밀도 시각 효과 부분집합 MLLM-as-a-judge 하락 패턴과 정렬되는 지표 측정 한계).
- CIEDE2000 ↓ — CIE (국제조명위원회) 가 2000 년 표준화한 인지 균일 (perceptually uniform) 색차 공식 [27]. RGB Euclidean 거리가 색 영역에 따라 사람 눈의 인지 차이와 어긋나는 문제 (예: 파랑 영역과 녹색 영역의 같은 RGB 거리가 다르게 인지됨) 를 보정한다. 측정 절차는 생성·참조 PNG 에서 각각 k-means 로 dominant 색을 추출한 뒤 매칭 색 쌍의 평균 ΔE 를 보고한다. 통상적 인지 스케일은 ΔE < 1 구별 불가 / 2–10 식별 가능 / > 10 명확히 다른 색이며 [27], 본 논문 표의 절댓값 (대략 20–60 범위) 은 슬라이드 전체 팔레트의 평균 거리이므로 단일 픽셀 임계값 해석 대신 메서드 간 상대 비교로 사용한다. 낮을수록 참조와 색이 가깝다.

추가로 측정된 검증가능한 규칙 (whitespace_frac, collision_score) 는 본 도메인에 대한 규범적 정의 (여백의 "balanced range" 0.4–0.6, 충돌의 의도적 SVG 프리미티브 인접) 가 모호하여 주요 표에서 제외하고 보조 진단으로만 사용한다.

축 ② MLLM-as-a-judge 루브릭:

- AutoPresent 루브릭 (0–5) — AutoPresent [14] 의 레이아웃 / 색 두 차원 각각 0–5 점. GPT-4o judge.
- GPT-5.4 4 기준 (1–7) — PPTAgent [11] 의 PPTEVAL 계열 4 기준. Generator (GPT-4o) 와 다른 모델 계열로 자기평가 편향을 차단한다 [20, 19]. 참조 이미지, generated PNG, generated HTML 의 처음 3,000자를 함께 제공한다.
  - Visual Fidelity (VF), Layer Structure (LS), Content Completeness (CC), Design Quality (DQ)

축 ③ Content Completeness (보조):
- CCR ↑ — 입력 텍스트가 HTML 에 문자열로 등장하는 비율 (시각 가시성 미반영; MLLM-as-a-judge CC 가 시각 프록시)

Legacy 기본 점검 — 클래스명 기반 (참고용, 주요 주장 외):
- Layer Recall, LTED (Layer Tree Edit Distance) — 본 연구에서 정의한 보조 지표. 두 슬라이드의 레이어 집합을 (z-band, type) multiset 으로 표현하고 (z-band 는 back z<10 / mid 10–19 / front ≥20 의 3 구간으로 정수 z 인코딩 차이를 흡수), Layer Recall = |types(T_P) ∩ types(T_G)| / |types(T_P)| (0–1, ↑, reference 의 (band, type) pair 중 generated 에 등장하는 비율), LTED = Σ_k |m_P(k) − m_G(k)| / (Σ_k m_P(k) + m_G(k)) (0=identical / 1=disjoint, ↓, 두 multiset 의 정규화된 symmetric difference). 명칭은 'tree edit distance' 이나 실 구현은 multiset 단위로 단순화된 형태이며 정통 Zhang-Shasha 트리 편집 거리와는 다르다. type 추출이 LayerAgent 의 slide_type · 전문가 layer class 어휘에 정렬된 정규식에 기반하므로 다른 메서드 (예: Claude Opus 의 `glass-card`·`node-inner` 어휘) 가 정규식에 매칭되지 않아 거짓 negative 로 보고될 수 있는 클래스명 편향 한계를 가진다. 이 한계로 인해 부록 B.1 (현상 가시화), 부록 B (보조 표), 5.4절 단순 베이스라인 점검 (프롬프트 변형이 클래스명 어휘와 무관하므로 방향 해석에 한해 안정적) 에 한정해 사용한다.

4.4 실험 인프라

- 4-stage cacheable 파이프라인: generate → 렌더(Playwright) → 참조 인식(VLM 캐시) → metrics 순서로 구성되며, 각 단계는 독립적으로 재시작이 가능하다.
- 총 4 메서드 × 50 슬라이드 = 200 cell이며, 전체 실행 시간은 82분, 생성 실패는 0건이다.

---

제 5 장. 결과

5.1 RQ1 검증 — 인식–생성 격차의 모델 일반성

RQ1 (슬라이드 도메인의 계층적 요소 누락이 VLM 일반에서 관찰되는가) 의 핵심 증거를 정리해 보고한다. 상세 수치와 보조 지표 전체는 부록 B.1 (GPT-4o 사전 실험) · 부록 B.2 (교차 VLM 프로빙) 에 수록한다.

인식–생성 격차의 정량화 (GPT-4o, N=10 고밀도 시각 효과 디자인). 같은 GPT-4o 에 동일 슬라이드 이미지를 입력하고 자연어로 시각 계층을 기술하라고 요청하면 평균 6.6 개 (범위 5–10) 의 레이어가 인식되지만, 같은 이미지를 HTML 로 변환하라고 요청하면 코드의 평균 레이어 카운트가 1.8 개로 떨어진다. LayerAgent 분해를 적용하면 코드의 평균 레이어 카운트가 8.2 개 (인식 단계 6.6 상회 — 분해 단위가 인식 자연어 기술보다 세분화된 결과) 로 회복된다 (5.4절 단순 베이스라인 점검). 이 6.6 → 1.8 격차는 클래스명 어휘에 의존하지 않는 n_layers 수준에서 측정되며, 1.1절의 슬라이드 도메인 계층적 요소 누락 정식화의 직접 증거이다.

최첨단 VLM 으로의 일반성 (교차 VLM probing, N=10). 같은 슬라이드를 3 개 최첨단 VLM 의 일괄 생성에 각각 입력해 측정한 격차 (1 − Layer Recall) 는 GPT-4o 0.776, GPT-5.4 0.700, Claude 4.6 Opus 0.688 로 모두 0.69 ~ 0.78 범위에 분포한다 (평균 0.721, 교차 VLM 표준편차 0.039, 사전등록 가설 H-EO 채택). 최첨단 모델 업그레이드 단독으로는 계층적 요소 누락이 완전히 해소되지 않으며, 격차가 GPT-4o 의 개별 특성이 아니라 단일 VLM 일괄 호출 양식 자체의 양상임을 보인다. 단 교차 VLM 측정은 LayerAgent 어휘 정렬 정규식 (Layer Recall, 부록 B) 에 기반하므로 클래스명 편향 한계 하에서 최첨단 간 상대 비교에 한정해 해석한다 (7.1절).

5.2 동일 모델 GPT-4o 비교 — 객관 충실도와 교차 모델 MLLM-as-a-judge에서의 우위 (RQ2)

5.1절의 6.6 → 1.8 격차에 대한 파이프라인 분해의 회복을, 동일 기본 모델 GPT-4o 에서 4가지 메서드 (일괄 생성·시각 분석 생성·패턴 주입 생성·LayerAgent) 를 비교하여 정량화한다. 평가는 다면적 평가 묶음으로 함께 보고한다 — 객관 충실도와 AutoPresent VLM 루브릭은 표 2 (전체 N=50) · 표 3 (고밀도 시각 효과 부분집합 N=10), GPT-5.4 4 기준 MLLM-as-a-judge 는 표 4 (main_eval). 레이아웃 의존성은 5.3절에서 다룬다.

〈표 2〉 전체 데이터셋 객관 충실도 + VLM 루브릭 (N=50, 다면적 평가 묶음). 굵은 = 1위.

| 지표 | A. 일괄 생성 | B. 시각 분석 생성 | C. 패턴 주입 생성 | D. LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Element-IoU ↑ | 0.314 | 0.301 | 0.296 | **0.372** |
| CIEDE2000 ↓ | 53.6 | 56.9 | **51.5** | 58.6 |
| AutoPresent layout_0_5 ↑ | 2.90 | 2.70 | 2.56 | **3.64** |
| AutoPresent color_0_5 ↑ | **3.70** | 3.56 | 2.76 | 3.12 |

핵심 발견 1 (주요 결과) — 전체 N=50 에서 LayerAgent 는 객관 시각 매칭 (Element-IoU 0.372, sp 0.314 대비 +18%) 과 VLM-루브릭 레이아웃 차원 (AutoPresent layout_0_5 3.64 대 2.90) 에서 명확히 1위이다. 색 차원 (CIEDE2000, color_0_5) 에서는 일괄 생성·패턴 주입 생성이 우세 — chart_templates 적용 7 레이아웃에서는 결정적 렌더링이 참조 색 팔레트 대신 정제된 SVG 색 시스템을 사용하기 때문이며 (6.1절), chart_templates 미적용 N=10 고밀도 부분집합 (표 3) 의 color_0_5 열세는 별도로 분위기 레이어 단순화에 기인한다 (5.3절 핵심 발견 1' · 7.2절). 한편 프롬프트 수준 변형 (visual_cot 4 지표 모두 sp 열세, cot_h_rag 는 AutoPresent 두 차원 최하위) 은 일괄 생성 대비 일관된 개선이 없어, 동일 모델 우위는 LayerAgent 의 통합 파이프라인에서 비롯됨을 시사한다 (컴포넌트별 인과 효과는 5.4절).

〈표 3〉 고밀도 시각 효과 디자인 부분집합 객관 충실도 + VLM 루브릭 (N=10, design_01–10). 굵은 = 1위.

| 지표 | A. 일괄 생성 | B. 시각 분석 생성 | C. 패턴 주입 생성 | D. LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Element-IoU ↑ | 0.563 | 0.551 | 0.563 | **0.575** |
| CIEDE2000 ↓ | 30.3 | 26.9 | 27.7 | **20.7** |
| AutoPresent layout_0_5 ↑ | **4.20** | 3.80 | 3.70 | 2.90 |
| AutoPresent color_0_5 ↑ | 3.70 | **3.90** | 3.50 | 3.00 |

핵심 발견 1' (부분집합 분기) — 고밀도 시각 효과 디자인 부분집합 (N=10) 에서 LayerAgent 는 객관 충실도 (Element-IoU, CIEDE2000) 에서 1위 (CIEDE2000 20.7 대 차순위 메서드 26.9, 큰 폭 색 정확도 우세) 이지만 VLM 루브릭 (layout_0_5, color_0_5) 에서는 4위이다. 이 분기는 본 평가 프레임워크가 측정하는 두 차원의 분리를 직접 보여준다 — 객관적 시각 매칭은 LayerAgent 의 분해 + DesignSpec blackboard 가 색 표류를 줄여 참조와의 색 거리를 좁히는 효과를 포착하지만, MLLM 종합적 judge 는 고밀도 시각 효과 디자인의 풍부한 분위기 레이어 (radial 글로우, glassmorphism, 장식 모티프) 를 LayerAgent 출력이 단순화하는 경향을 레이아웃 / 색 품질 패널티로 평가한다. 본 분기는 5.3절의 고밀도 시각 효과 MLLM Δ −0.80 과 정렬되며, 7.2절의 후속 연구로 "고밀도 시각 효과 카테고리에서의 표현력 있는 분위기 레이어 생성" 을 다룬다. 데이터 중복 단서는 7.2절을 참조한다.

〈표 4〉 종합적 발표 품질 — MLLM-as-a-judge (GPT-5.4, 1–7 scale, main_eval N=50). 4 기준: Visual Fidelity (VF), Layer Structure (LS), Content Completeness (CC), Design Quality (DQ). 굵은 = 1위.

| Criterion | 일괄 생성 | 시각 분석 생성 | 패턴 주입 생성 | LayerAgent |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 2.24 | 2.08 | 1.74 | **2.94** |
| Layer Structure ↑ | 3.52 | 3.08 | 3.00 | **4.62** |
| Content Completeness ↑ | 3.92 | 3.70 | 3.76 | **4.62** |
| Design Quality ↑ | 3.78 | 3.30 | 3.36 | **3.90** |
| Average ↑ | 3.37 | 3.04 | 2.96 | **4.02** |

MLLM-as-a-judge 4 기준 모두에서 LayerAgent가 1위이며, 평균은 4.02로 차순위 메서드(일괄 생성 3.37) 대비 +0.65 격차이다. chart_templates 가 적용되는 7 레이아웃 (pyramid + chart·표 6종, 5.3절 표 5 캡션 매핑) 에서 결정적 렌더링이 자기회귀 zero-sum을 회피하여 텍스트 오버플로·콘텐츠 누락 패널티가 구조적으로 차단되며, Layer Structure(4.62)·Content Completeness(4.62) 두 축의 큰 격차가 이를 직접 보여준다. 그림 2 는 4개 chart·표 디자인에서 LayerAgent 와 single_pass 의 구조적 충실도 차이를 정성적으로 시각화한다. 단, 본 MLLM-as-a-judge 결과는 GPT-5.4 단일 judge 에 기반하므로 교차 judge (Claude·Gemini) 일반화는 7장의 한계로 남는다.

![그림 2: Qualitative 구조적 충실도 비교](results/figures/fig6_qualitative.png)

5.3 레이아웃 유형별 효과 범위 분석 (RQ3 레이아웃 의존성)

〈표 5〉 9개 레이아웃 유형별 LayerAgent 레이아웃별 효과 비교. 주축은 MLLM-as-a-judge, 보조 진단은 LTED (부록 B). 9개 레이아웃 중 고밀도 시각 효과 디자인과 process_flow 를 제외한 7개 레이아웃이 chart_templates 7종 (3.2.2절) 에 대응하여 단일 VLM 의 자기회귀 zero-sum 이 구조적으로 차단되며, 본문 이하에서 "chart·표 6종" 은 이 중 tree_diagram renderer 가 적용되는 pyramid 를 제외한 6 레이아웃 (bar_chart, line_chart, waterfall, matrix_2x2, mekko, harvey_table_advanced) 을 가리킨다.
- MLLM Δ (주요) = LayerAgent 평균 − (최고 베이스라인 평균), 양수 = LayerAgent 우세.
- LTED Δ (보조) = (최고 베이스라인 LTED) − (LayerAgent LTED), 양수 = LayerAgent 우세.

| 레이아웃 | N | MLLM LayerAgent | MLLM Δ | LTED LayerAgent | LTED Δ |
|---|:---:|:---:|:---:|:---:|:---:|
| 고밀도 시각 효과 디자인 | 10 | 3.23 | −0.80 | 0.551 | +0.27 |
| pyramid | 5 | 3.45 | +0.05 | 0.764 | +0.08 |
| mekko | 5 | 5.00 | +1.35 | 0.753 | +0.08 |
| process_flow | 5 | 3.25 | −0.65 | 0.818 | +0.06 |
| harvey_table | 5 | 4.25 | +0.15 | 0.923 | −0.05 |
| matrix_2x2 | 5 | 4.40 | +1.90 | 0.917 | +0.00 |
| waterfall | 5 | 4.50 | +1.70 | 0.662 | −0.03 |
| line_chart | 5 | 4.40 | +1.80 | 0.845 | −0.03 |
| bar_chart | 5 | 4.50 | +1.50 | 0.733 | −0.09 |

![그림 3: Per-layout 효과 range (N=50)](results/figures/fig3_layouts.png)

표 5 의 레이아웃별 분포는 그림 3 에 두 축 (MLLM Δ 주축, LTED Δ 보조 축) 으로 시각화되어 있다.

핵심 발견 (RQ3).

1. chart·표 6종 카테고리에서 LayerAgent 가 MLLM Δ +0.15 ~ +1.90 의 큰 폭 격차로 우세하다. chart_templates 결정적 렌더링이 chart 영역의 자기회귀 zero-sum을 구조적으로 회피하여 시각 충실도와 콘텐츠 보존을 동시에 보장한다 (3.4절 Text Inserter 설계 의도와 정렬).
2. pyramid (tree_diagram renderer 적용) 에서도 LayerAgent가 MLLM Δ +0.05, LTED Δ +0.08 로 양 축 합의로 우세하다.
3. 고밀도 시각 효과 디자인과 process_flow 에서는 MLLM 축에서 베이스라인이 우세하다 (Δ −0.80, −0.65). 두 카테고리 모두 chart_templates 가 적용되지 않는 레이아웃 그룹이며, LTED 보조 지표는 LayerAgent 우세 — 레이어 구조 회복은 일어나지만 종합적 발표가능성으로 전이되지 않는 카테고리이다. 7.2절 후속 연구에서 다룬다.

5.4 Ablation

(a) 단순 프롬프트 변형의 반증 점검 (z-index 명시 일괄 생성) 과 (b) 두 메커니즘의 정량 격리 측정 (Text Inserter 분리 D₂, DesignSpec blackboard 분리 D₄) 을 보고한다. 두 ablation 모두 LayerAgent v4 (chart_templates 활성화) 출력에 대해 다면적 평가 묶음 (Element-IoU + CIEDE2000 + AutoPresent layout_0_5 / color_0_5) 으로 재측정되었다.

단순 베이스라인 점검 (프롬프트 수준 변형). LayerAgent 의 동일 모델 우세가 분해 효과인지 단순 프롬프트 조정만으로도 가능한지를 점검하기 위해, 일괄 생성 프롬프트에 z-index 6-band 명시 한 줄을 추가한 변형 (`single_pass_zexplicit`) 을 비교한다.

〈표 6〉 단순 베이스라인 점검 — z-index 명시 일괄 생성 변형 비교 (N=10 고밀도 시각 효과 디자인, 보조 지표).

| 방법 (N=10 고밀도 시각 효과 디자인) | LTED ↓ | Layer Recall ↑ | 평균 레이어 카운트 |
|---|:---:|:---:|:---:|
| 일괄 생성 (`single_pass`) | 0.823 ± 0.14 | 0.224 ± 0.13 | 1.8 |
| z-index 명시 일괄 생성 (`single_pass_zexplicit`) | 0.844 ± 0.12 | 0.292 ± 0.17 | 3.8 |
| LayerAgent (`layeragent`) | 0.551 ± 0.13 | 0.759 ± 0.16 | 8.2 |

z-index 명시는 Recall 차원에서 일부 회복 (0.224 → 0.292, 레이어 카운트 1.8 → 3.8) 을 보이나 LTED 는 미세 악화 (0.823 → 0.844; 추가된 레이어가 reference 와 정렬되지 않음을 시사) 하여 두 보조 지표가 분기하며, 양 지표 모두 LayerAgent (0.551, 0.759, 8.2) 와의 큰 격차가 유지된다 — 단순 프롬프트 변형만으로는 LayerAgent 수준의 계층 회복이 나오지 않는다 (LTED·Layer Recall 은 부록 B 보조 지표).

D₂ (no_text_inserter) — Text Inserter 분리 (N=50 main_eval):

〈표 7〉 D₂ Text Inserter ablation (N=50 main_eval, 다면적 평가 묶음).

| 지표 | D (전체) | D₂ (no_text_inserter) | Δ (D − D₂) |
|---|:---:|:---:|:---:|
| Element-IoU ↑ | 0.372 | 0.364 | +0.008 |
| CIEDE2000 ↓ | 58.59 | 57.55 | +1.04 (D₂ 우세) |
| AutoPresent layout_0_5 ↑ | 3.64 | 3.42 | +0.22 |
| AutoPresent color_0_5 ↑ | 3.12 | 3.28 | −0.16 (D₂ 우세) |

Text Inserter 를 제거하면 다면적 평가 묶음 4 지표 중 layout_0_5 만 D 가 우세 (Δ +0.22) 하며 색 차원에서는 D₂ 가 우세이다 — 다면적 시각 묶음이 측정하는 차원이 텍스트의 콘텐츠 보존이 아니라 시각 배치·색 분포이며, Text Inserter 의 핵심 메커니즘 (텍스트 누락 차단) 은 시각 묶음의 측정 범위 밖에 있기 때문이다 (7.1절 string-CCR 한계). 다만 고밀도 시각 효과 부분집합 (N=10) 에서는 효과가 강하게 나타나며 (Element-IoU Δ +0.026, color_0_5 Δ +0.50, D 우세), 시각 효과 밀도가 높은 조건에서 Text Inserter 부재는 시각 생성에도 영향을 미친다는 신호이다 (사전등록 가설 H-AblationTextInserter, 부록 A).

D₄ (no_designspec) — DesignSpec blackboard 효과 (N=50 main_eval):

〈표 8〉 D₄ DesignSpec blackboard ablation (N=50 main_eval, 다면적 평가 묶음).

| 지표 | D (전체) | D₄ (no_designspec) | Δ (D − D₄) |
|---|:---:|:---:|:---:|
| Element-IoU ↑ | 0.372 | 0.371 | +0.001 |
| CIEDE2000 ↓ | 58.59 | 59.25 | −0.66 |
| AutoPresent layout_0_5 ↑ | 3.64 | 3.72 | −0.08 |
| AutoPresent color_0_5 ↑ | 3.12 | 2.16 | **+0.96** |

DesignSpec blackboard 를 제거하면 다면적 평가 묶음 4 지표 중 color_0_5 차원에서 Δ +0.96 의 큰 폭 격차를 보인다 — AutoPresent VLM 이 카드 간 색 일관성 손실을 직접 채점에 반영. Element-IoU 와 CIEDE2000 (객관 시각 매칭) 은 거의 동률로, DesignSpec 이 요소 배치 자체에는 영향 없고 색 일관성에만 강하게 작용함을 보여준다 (사전등록 가설 H-AblationDesignSpec, 부록 A). 고밀도 시각 효과 부분집합 (N=10) 에서도 동일 패턴 (color_0_5 Δ +0.70, D 우세) 이 관찰되어 3.2절의 "DesignSpec 이 에이전트 간 스타일 표류를 줄인다" 는 설계 의도가 직접 검증된다. 그림 4 는 D₂·D₄ 두 ablation 의 다면적 평가 묶음 영향을 좌우 패널로 시각화한다.

![그림 4: D₂ and D₄ ablation impact](results/figures/fig4_ablation.png)


제 6 장. 논의

6.1 LayerAgent 우위의 메커니즘 분해 — 결정적 렌더링 효과와 레이어 분해 효과

5장의 결과는 LayerAgent 파이프라인의 두 설계 결정으로 분리 귀속된다.

- (i) 데이터 추출과 결정적 렌더링의 분리 (Chart Agent · Table Agent · chart_templates) — chart·표 6종 + pyramid 의 큰 폭 우세 (MLLM Δ +0.05 ~ +1.90, 표 5) 의 주된 원인. 본 7 레이아웃에서 VLM 호출은 chat_parser 단계의 데이터 추출에 한정되고 시각은 결정적 SVG/HTML 프리미티브로 산출되므로, 단일 VLM 호출의 자기회귀 zero-sum (구조·시각·콘텐츠 경쟁) 이 구조적으로 회피된다.
- (ii) 레이어 단위 병렬 생성과 사전 동기화 (DesignSpec + Style Normalizer + Text Inserter) — DesignSpec 의 직접 증거는 D₄ ablation 의 color_0_5 Δ +0.96 (5.4절 표 8). Text Inserter 의 v4 증거는 N=50 시각 묶음에서는 약하지만 고밀도 시각 효과 N=10 부분집합에서 Element-IoU Δ +0.026, color_0_5 Δ +0.50 으로 관찰된다 (5.4절 표 7). Style Normalizer 는 단독 ablate 되지 않았다. 카드 간 색 일관성 차원에서 격리 관찰되지만 비차트 레이아웃의 종합 채점으로의 전이는 약하다 (고밀도 시각 효과 MLLM Δ −0.80, process_flow Δ −0.65; 7.2절).

두 설계 결정 모두 단일 VLM 일괄 호출의 한계 (시각·콘텐츠 zero-sum 경쟁, 카드 간 스타일 표류) 를 분해 단위로 회피하는 LayerAgent 파이프라인의 산물이다 — (i) 은 chart·표 카테고리에서 종합 채점 전이까지 성공적이며, (ii) 는 색 일관성 차원에서 격리 관찰되지만 비차트 레이아웃의 종합 채점으로의 전이는 7.2절 후속 연구로 남는다.

6.2 디자인 조건부 trade-off 관찰 — H-RAG 역설

패턴 주입 생성 (`cot_h_rag`, 복합 CSS 효과 레시피 RAG 주입) 에서 시각 표현과 텍스트 보존의 trade-off 는 디자인 조건부로 강도가 달라진다. 텍스트 밀도가 높은 chart·표 계열에서는 입력 텍스트의 절반 이상이 사라진다 — mekko_mckinsey_finance CCR 1.0 → 0.36 (−64%), waterfall_editorial_warm 1.0 → 0.55 (−45%). 고밀도 시각 효과 부분집합 (N=10) 에서도 CSS Richness 10.2 → 17.8 (+75%) 상승과 CCR 0.956 → 0.828 (−13%) 감소가 동반된다. N=50 평균의 −4% 효과는 평면 레이아웃이 평균을 희석한 결과이며, 분포는 trade-off 가 시각/텍스트 밀도가 높은 조건에서 강하게 발현됨을 보여준다.

이 패턴은 단일 VLM 호출에서 시각과 텍스트가 디자인 조건부로 경쟁한다는 해석과 부합한다.

6.3 다면적 평가가 측정하는 서로 다른 차원 (RQ3 평가 축 의존성)

Design2Code 평가는 서로 다른 차원을 측정하는 다축 문제이다. 세 축과 각 축에서의 LayerAgent 위치를 정리한다.

〈표 9〉 메트릭 축 분리.

| 평가 축 | 대표 지표 | 측정 차원 | 동일 모델 GPT-4o 우승 | 답하는 질문 |
|---|---|---|---|---|
| ① 객관 디자인 충실도 | Element-IoU, CIEDE2000 | 요소 단위 IoU, 색 거리 | N=50: LayerAgent (Element-IoU); 색은 베이스라인 우세 | "렌더된 결과가 참조와 요소·색에서 얼마나 정확히 일치하는가?" |
| ② AutoPresent 루브릭 (0–5) | layout_0_5, color_0_5 | GPT-4o judge, 레이아웃·색 적절성 | N=50: LayerAgent (레이아웃); 색은 베이스라인 / N=10 고밀도: 두 차원 모두 베이스라인 우세 | "발표 슬라이드로서 레이아웃 / 색이 적절한가? (0–5)" |
| ③ GPT-5.4 4 기준 (1–7) | VF·LS·CC·DQ | 교차 모델 MLLM-as-a-judge | LayerAgent (4 기준 모두) | "출력이 발표가능한 슬라이드인가? (1–7)" |

보조 진단 지표 (1차 축 제외). 클래스명 기반 보조 지표 (LTED, Layer Recall) 는 LayerAgent 의 class 이름 어휘에 정렬된 정규식에 기반하여 편향을 도입하고, 텍스트 문자열 보존 (string-CCR) 은 시각 가시성을 측정하지 못한다 (7.1절). 두 지표는 5.4절 ablation 과 5.1절 교차 VLM probing 의 보조 측정에서만 사용된다.

LayerAgent 는 동일 GPT-4o 4 메서드 비교에서 축 ① (Element-IoU 0.372 대 0.314) 과 축 ③ (GPT-5.4 4 기준 평균 4.02 대 3.37) 에서 1위, 축 ② 의 레이아웃 차원에서 N=50 기준 1위 (3.64 대 2.90) 이나, 색 차원과 N=10 고밀도 부분집합에서는 베이스라인이 우세하다 — 분위기 레이어 단순화가 종합 채점에 패널티를 유발한다 (5.3절·7.2절). 객관 충실도 축의 우세는 chart·표 카테고리의 요소 배치는 chart_templates 결정적 렌더링이, 카드 간 색 일관성은 DesignSpec blackboard 가 각각 책임진다 (6.1절).

동일한 출력이 평가 축에 따라 다른 메서드를 1위로 평가한다는 발견 (사전등록 H-MetricAxisDisagreement, 부록 A) 은 SlideAudit [18] 의 자동 지표-인간 판정 불일치를 Design2Code 다축 환경으로 평행 적용한 것이다. Design2Code [1] Block-Match 는 축 ①, AutoPresent [14] 0–5 루브릭은 축 ②, WebDevJudge [19] MLLM-as-a-judge 는 축 ③ 에 해당한다. 현 데이터로는 세 축 중 인간 발표가능성 판단에 가장 가까운 축을 결정할 수 없으며, 인간 앵커 (n≥80 쌍, 7.1절) 가 결정적 후속이다.

6.4 분해 접근의 적용 경계 — 모델 세대 진보와의 관계

LayerAgent 의 두 설계 결정 (6.1 절) 은 모델 세대 진보와 직교적인 차원에서 작동한다. 결정적 chart_templates 렌더링은 데이터 추출만 VLM 에 맡기므로 백본 모델 성능과 독립적으로 chart·표 카테고리 우세를 유지할 것으로 예상되며, 레이어 분해의 색 일관성 효과는 단일 호출의 카드 간 스타일 표류가 지속되는 한 유효하다 — 교차 VLM probing 에서 격차 (1 − Layer Recall) 가 GPT-4o 0.776 / GPT-5.4 0.700 / Claude 4.6 Opus 0.688 로 모델 세대가 진보해도 0.69 근방을 유지하므로 (5.1절), 본 조건은 최첨단에서도 충족된다.

다만 본 직교성 주장은 GPT-4o 백본에 한정해 측정되었으며, 두 메커니즘을 GPT-5.4·Claude 4.6 Opus 백본에 적용한 결합 효과는 8장 향후 연구 (e) 에서 다룬다. 모델 업그레이드와 분해 접근은 별개 차원이며, 비용·품질 참조 비교는 7.3절을 참조한다.

---

제 7 장. 한계

본 장은 방법론·데이터 한계 (7.1·7.2) 와 적용 범위 보조 비교 (7.3) 를 정리한다.

7.1 평가 방법론과 지표의 타당성

(a) String-CCR 은 텍스트의 시각 가시성을 과소결정한다 — HTML 에 문자열로 존재하는지만 측정하므로 오버플로·폐색 같은 시각 차원이 빠진다. MLLM-as-a-judge Content Completeness 가 시각 프록시로 보완하나, 시각 인식 OCR (mPLUG-DocOwl, Florence-2 등) 기반 시각 CCR 메트릭의 도입 (Playwright 렌더링 후 가시 텍스트 추출과 입력 콘텐츠 매칭) 이 지표 수준의 근본적 해결책이다. 다만 현재 OCR 이 본 도메인 (다크 배경, 한국어, blur 조합) 에서 무력화되어 있어 시각 인식 OCR 채택이 선결 조건이다. (b) 종합 평가가 GPT-5.4 단일 MLLM-as-a-judge에 의존한다. Claude·Gemini 등 교차 judge 일반화와 인간 앵커 직접 검증(n≥80 쌍 × 5 평가자, MT-Bench [20] 쌍별 프로토콜)은 수행되지 않았다. WebDevJudge [19] 가 제안한 평가 관행의 적용이 필요하다.

7.2 통계 검증력과 데이터 구성

(a) multi-seed × N=100+ 디자인 확장으로 통계 검증력을 보강할 필요가 있다. 현재 N=50 main_eval 은 단일 시드 기반이다. (b) 부록 B.1 사전 실험 N=10 과 5.3절 고밀도 시각 효과 디자인 부분집합 N=10 은 동일한 슬라이드이며 (4.1절 명시), 본 카테고리의 결과는 동기와 검증이 동일 데이터에서 일어났다는 한계를 가진다. 차트·표 카테고리 및 8개 다른 레이아웃 그룹은 별개의 N=40 에서 측정된 독립 결과이므로 본 한계의 영향을 받지 않는다. 향후 사전 stratified sampling 기반 데이터셋 재구성과 독립 표본 수집·재측정이 필요하다.

7.3 적용 범위 경계 — 최첨단 모델 참고 비교

LayerAgent 의 주요 결과는 GPT-4o 동일 모델 4 메서드 비교 (5.2절) 에서 Design2Code 다면적 평가 묶음으로 보고된다. 적용 범위 경계를 명시하기 위해 GPT-5.4 및 Claude 4.6 Opus 기반 일괄 생성을 별개 비용-품질 차원의 참조로 보고한다 (N=10 샘플, 가격은 2026 Q1 list price 기준 — GPT-4o $2.5/$10, GPT-5.4 $5/$15, Claude 4.6 Opus $15/$75 per M input/output). 표 10 은 주요 프레임워크 적용 이전의 DOM 기반 측정값이며, 최첨단 출력에 대한 다면적 평가 묶음 재측정은 8장 향후 연구 (e) 에서 다룬다.

〈표 10〉 최첨단 모델 일괄 생성과의 참고 비교 (N=10, DOM 기반 보조 측정).

| 방법 | 요소 수 | 스타일 diversity | 렌더 풍부성 | Approx. API cost/슬라이드 | Time |
|---|:---:|:---:|:---:|:---:|:---:|
| LayerAgent (GPT-4o + 분해, N=10 고밀도 시각 효과) | 17.0 | 10.3 | 32.0 | $0.232 | 60s |
| 일괄 생성 (GPT-5.4, N=10) | 37.1 | 16.4 | 135.6 | $0.075 | 85s |
| 일괄 생성 (Claude 4.6 Opus, N=10) | 27.2 | 14.0 | 68.0 | $0.421 | 108s |

표 10 은 참고용 비교이다 — 동일 모델 파이프라인 분해 (LayerAgent) 와 최첨단 모델 확장이 서로 다른 비용-품질 경로임을 보이는 것이 목적이며, 두 경로의 우열 판정이 아니다.

DOM 기반 측정에서 최첨단 모델의 요소·스타일·풍부성 수치는 LayerAgent 보다 높으나, 본 측정 protocol 은 주요 다면적 평가 묶음 (4.3절) 과 다른 차원이다.

LayerAgent 의 주요 기여는 동일 모델에서의 파이프라인 분해 효과이며, 최첨단 확장과 분해 접근은 직교적 비용·품질 차원이다 (6.4절). 두 경로는 스택 가능하며 (최첨단 백본 + 분해 파이프라인), 결합 효과의 다면적 평가는 8장 향후 연구 (e) 로 다룬다.

---

제 8 장. 결론

본 논문은 슬라이드 도메인의 계층적 요소 누락 — 선행 Design2Code 요소 누락이 시각 계층 단위로 확장된 형태 — 을 정의하고, LayerAgent 프레임워크 (3장) 와 다면적 평가 방식 (4.3절) 을 제안했다. 두 메커니즘은 격리 측정되었다 — DesignSpec blackboard 의 카드 간 색 일관성 color_0_5 Δ=+0.96 (N=50, 5.4절 표 8), Text Inserter 는 고밀도 시각 효과 N=10 부분집합에서 시각 묶음 영향 color_0_5 Δ=+0.50 (5.4절 표 7).

세 연구 질문의 답은 다음과 같다.

(i) RQ1. GPT-4o 의 6.6 → 1.8 인식–생성 격차는 GPT-5.4 0.700, Claude 4.6 Opus 0.688 일괄 생성에서도 0.69–0.78 범위로 관찰된다 — 최첨단 업그레이드 단독으로 해소되지 않으며 파이프라인 분해를 정당화한다 (5.1절, H-EO 채택).

(ii) RQ2. 동일 GPT-4o 4 메서드 비교에서 LayerAgent 가 Element-IoU 0.372 (sp 0.314 대비 +18%) 와 GPT-5.4 4 기준 평균 4.02 대 3.37 두 축 모두 1 위이며, 우위는 chart_templates 7 레이아웃에서 결정적 렌더링이 자기회귀 zero-sum 을 회피하는 효과에 주로 귀속된다 (6.1절).

(iii) RQ3. 고밀도 시각 효과 N=10 에서 LayerAgent 는 객관 충실도 Element-IoU 0.575 · CIEDE2000 20.7 로 1 위이나 AutoPresent 루브릭 4 위, MLLM 종합 Δ = −0.80 (표 5) — 구조 정렬과 종합 발표 품질의 분리가 다면적 평가 병행 보고 권고를 강화한다.

향후 연구: (a) Claude·Gemini 교차 judge 추가, (b) 인간 앵커 n≥80 쌍 × 5 평가자, (c) multi-seed 3×4×50 통계 검정, (d) 시각 OCR 기반 CCR 도입, (e) 두 설계 결정의 GPT-5.4·Claude 4.6 Opus 백본 결합 효과 (6.4절 cross-backbone).

---

부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

핵심 가설들은 post-hoc 임의 임계값이 아닌 사전 명시된 결정 규칙으로 검증된다.

전제. 사전등록은 Layer Recall · LTED 를 주요 지표로 사용하던 초기 프레임워크에서 작성되었다. 주요 주장이 다면적 평가 지표로 전환된 이후, LTED · Layer Recall 에 의존하는 가설 (H-EO, H-SweetSpot, H-LayoutScaling) 은 부록 B 의 보조 지표 기준 보조 가설로 위치한다. 다면적 평가 기반 가설은 본문에서 효과 크기로 직접 보고되며, H-AblationTextInserter 는 두 평가 프로토콜에 걸쳐 있어 재정식화 단서가 명시된다.

H-EO (요소 누락의 모델-일반성, 5.1절·부록 B.2) — 채택. 사전등록 결정 규칙은 3 VLM 베이스라인 일괄 생성의 (1 − Layer Recall) 평균이 0.50 이상이고 교차 VLM 표준편차가 0.10 이하인 경우 채택으로 정의되었다. 측정 결과 세 VLM 의 격차는 {0.776, 0.700, 0.688} 으로 평균 0.721, 표준편차 0.039 를 보여 두 임계값을 모두 충족한다. 최첨단 모델의 업그레이드만으로 격차가 닫히지 않으며, 이는 파이프라인 분해의 motivation 을 보강한다 (해석 범위는 최첨단 간 상대 비교에 한정).

H-SweetSpot (고밀도 시각 효과 디자인에서의 양 축 합의, 5.3절) — 기각. 사전등록 결정 규칙은 N=10 고밀도 시각 효과 부분집합에서 LTED Δ 가 +0.20 을 상회하고 동시에 MLLM Δ 가 양수일 것을 요구하였다. 측정 결과 LTED Δ = +0.27 로 LTED 조건은 충족되나 MLLM Δ = −0.80 으로 MLLM 조건이 미충족되어 기각된다. 두 축의 분기 자체는 5.3절의 핵심 발견과 일치한다.

H-LayoutScaling (레이아웃별 양 축 부호 합의, 5.3절) — 기각. 사전등록 결정 규칙은 9 개 레이아웃 중 5 개 이상에서 MLLM Δ 와 LTED Δ 의 부호가 합의될 것을 요구하였다. 측정 결과 부호가 합의된 레이아웃은 pyramid 와 mekko 의 2 개에 그쳐 기각된다. chart · 표 카테고리에서 chart_templates 의 효과가 MLLM 축으로는 큰 폭으로 전이되나 LTED 로는 약하거나 음의 방향으로 측정되어, 두 축이 서로 다른 차원을 측정함을 보여준다 (H-MetricAxisDisagreement 와 정렬).

H-MetricAxisDisagreement (평가 축 간 불일치, 6.3절) — 채택. 사전등록 결정 규칙은 N=50 의 객관 충실도, AutoPresent 루브릭, GPT-5.4 4 기준 세 평가 축에서 1 위 메서드가 일치하지 않거나 두 단계 이상의 순위 차이를 보일 것을 요구하였다. 측정 결과 1 위 메서드는 Element-IoU · layout_0_5 · GPT-5.4 4 기준에서 LayerAgent, CIEDE2000 에서 cot_h_rag, color_0_5 에서 일괄 생성으로 분기하여 채택 조건을 충족한다. 동일한 출력이 평가 축에 따라 서로 다른 메서드를 1 위로 평가한다는 발견은 다면적 평가의 병행 보고 권고를 강화한다.

H-AblationTextInserter (Text Inserter 분리 효과, 5.4절) — 부분 채택. 사전등록 결정 규칙은 string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂) 로 정의되었으나, chart_templates 도입 (LayerAgent v4) 이후 평가 프로토콜이 다면적 시각 묶음으로 전환됨에 따라 v4 출력에 대해 재측정되었다. N=50 main_eval 에서 Element-IoU Δ = +0.008, CIEDE2000 Δ = +1.04 (D₂ 우세), layout_0_5 Δ = +0.22 (D 우세), color_0_5 Δ = −0.16 (D₂ 우세) 의 혼합 시그널이 관찰되며, N=10 고밀도 부분집합에서는 Element-IoU Δ = +0.026 및 color_0_5 Δ = +0.50 으로 D 가 우세하다. 고밀도 조건에서 Text Inserter 부재가 시각 생성에 영향을 미친다는 신호로 부분 채택하며, N=50 평균 시그널이 약한 것은 Text Inserter 의 핵심 메커니즘인 텍스트 누락 차단이 시각 묶음의 측정 범위 밖에 있기 때문이다 (7.1절 string-CCR 한계; 8장 향후 연구 (d) 의 시각 인식 OCR 도입 후 재검증 예정).

H-AblationDesignSpec (DesignSpec 에이전트 간 합치, 5.4절) — 채택 (color_0_5 차원). 결정 규칙은 다면적 평가 묶음 4 지표 중 1 개 이상에서 |Δ| ≥ 0.5 의 메커니즘 시그널이 존재할 것을 요구하도록 재정식화되었다. N=50 main_eval 에서 Element-IoU Δ = +0.001, CIEDE2000 Δ = −0.66, layout_0_5 Δ = −0.08, color_0_5 Δ = +0.96 (D 우세) 으로 color_0_5 차원에서 임계값을 큰 폭으로 충족하며, N=10 고밀도 부분집합에서도 color_0_5 Δ = +0.70 (D 우세) 으로 동일 패턴이 재현된다. AutoPresent VLM 이 카드 간 색 일관성 손실을 채점에 직접 반영한 결과로 해석되며, DesignSpec 메커니즘이 카드 간 색 일관성에 특화되어 작동함을 보여준다 (3.2.3절 의 설계 의도와 정렬).

---

부록 B. 클래스명 기반 보조 지표 — 기본 점검 자료

본 부록은 클래스명 기반 보조 지표 (Layer Recall, LTED) 수치를 수록한다. 측정은 LayerAgent class 어휘에 정렬된 정규식에 기반하므로 클래스명 편향 한계를 가지며 (7장), 주요 주장은 본문의 다면적 평가 지표 (5.2절 표 2) 를 따른다.

B.1 프로빙 사전 실험 — N=10 고밀도 시각 효과 디자인, GPT-4o

본문·결론의 "평균 6.6개 (범위 5–10)" 는 본 사전 실험 10개 디자인에서 GPT-4o 가 인식 단계에 자연어로 기술한 레이어 개수의 표본 분포 (평균 6.6, min 5, max 10) 에서 산출되며, 동일 데이터의 코드 변환에서 평균 1.8개가 HTML/CSS 에 반영된다.

B.2 Cross-VLM 프로빙 (N=10 고밀도 시각 효과 디자인)

10개 고밀도 시각 효과 디자인을 3 개 최첨단 VLM 의 일괄 생성에 각각 입력하여 측정한 결과를 보고한다. 최첨단 모델 간 비교는 모두 LayerAgent 와 다른 어휘를 사용하므로 상대적으로 공정하나, LayerAgent 와 최첨단의 비교는 클래스명 편향 위험을 가진다.

〈표 11〉 Cross-VLM 프로빙 — 3 최첨단 일괄 생성 (LayerAgent 행은 클래스명 편향 위험).

| 모델 | LTED ↓ | Layer Recall ↑ | 격차 (1−Recall) | 평균 토큰 | 비용/슬라이드 | 시간 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 | ~5,000 | ~$0.015 | ~10s |
| single_pass (GPT-5.4) | 0.669 | 0.300 | 0.700 | 6,015 | $0.075 | 85s |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | 0.688 | 7,116 | $0.421 | 108s |
| LayerAgent (GPT-4o) | (0.551) | (0.759) | (0.241) | 54,310 | $0.232 | ~60s |

세 최첨단 모두 격차가 0.69–0.78 범위로 분포하여 최첨단 간 상대 비교에서 격차 차이가 작으며, H-EO 의 적용 범위는 최첨단 모델 간 비교에 한정된다.

B.3 N=50 main_eval 4 메서드 보조 표

〈표 12〉 main_eval 4 메서드 — 클래스명 기반 보조 지표 (N=50 mixed).

| 방법 | Layer Recall ↑ | 격차 (1−Recall) ↓ | LTED ↓ |
|---|:---:|:---:|:---:|
| cot_h_rag | 0.115 ± 0.16 | 0.885 | 0.914 |
| visual_cot | 0.197 ± 0.13 | 0.803 | 0.849 |
| single_pass | 0.212 ± 0.15 | 0.788 | 0.828 |
| layeragent | 0.397 ± 0.23 | 0.603 | 0.752 |

4 메서드별 Layer Recall 분포는 그림 5 에, 다지표 분포는 그림 6 에 시각화되어 있다.

![그림 5: Layer Recall × 메서드 (N=50)](results/figures/fig1_gap.png)

![그림 6: Multi-지표 × 메서드 비교 (N=50)](results/figures/fig2_methods.png)

---

부록 C. chart_templates 라이브러리 — 7 renderer 명세 (3.3절에서 위임)

〈표 13〉 chart_templates 라이브러리 — 7 renderer 명세.

| Renderer | 입력 데이터 구조 | 시각 capability |
|---|---|---|
| `bar_chart` | categories + values | 막대 + 하이라이트 강조 / 플랜 점선 막대 지원 |
| `line_chart` | x-axis + multi-series | multi-series 추세선, 시리즈별 색·하이라이트 마커·주석 |
| `waterfall` | start + delta sequence | start / positive / negative / total 4-type 막대, 누적 연결선 |
| `matrix_2x2` | quadrant items + 축 라벨 | 4-사분면 격자 + x/y 축 라벨 + 하이라이트 quadrant |
| `mekko` | 가변폭 컬럼 + stacked 세그먼트 | 컬럼 폭이 한 차원, 세그먼트 비율이 두 번째 차원을 인코딩 |
| `harvey_table_advanced` | option × 기준 매트릭스 | 0 / 25 / 50 / 75 / 100 Harvey ball 5단계 + 그리드 |
| `tree_diagram` | 1 root → N branches → M leaves | 계층적 트리 레이아웃, branch 색 분리 |

VLM 호출은 chat_parser 단계의 데이터 추출에만 사용되며, 시각 자체는 SVG/HTML 프리미티브로 결정적으로 산출된다 (3.3절 Chart Agent · Table Agent · 6.1절 자기회귀 zero-sum 회피).

---

참고 문헌

- [1] Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- [2] Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- [3] Calò, T., & De Russis, L. "Advancing Code Generation from Visual Designs through Transformer-Based Architectures and Specialized Datasets." Proceedings of the ACM on Human-Computer Interaction (PACMHCI), 2025. — element omission / element distortion / element misarrangement 분류 출처.
- [4] DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- [5] LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- [6] ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- [7] DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.
- [8] UIOrchestra. "Generating High-Fidelity Code from UI Designs with a Multi-Agent Framework." Findings of the Association for Computational Linguistics: EMNLP 2025.

- [9] VisRefiner. "Learning from Visual Differences for Screenshot-to-Code Generation." arXiv:2602.05998, 2026.
- [10] Vision-Guided Iterative Refinement. "Vision-Guided Iterative Refinement for Frontend Code Generation." arXiv:2604.05839, 2026.

- [11] Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- [12] Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- [13] Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- [14] Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.

- [15] DreamHouse. "How Far Are Vision-Language Models from Constructing the Real World? A Benchmark for Physical Generative Reasoning." arXiv:2603.24866, 2026.
- [16] WebRenderBench. "Layout-Style Consistency with Reinforcement Learning." 2025.
- [17] Widget2Code. "Apple HIG-inspired Per-Property Evaluation." 2025.
- [18] SlideAudit. "A Dataset and Taxonomy for Automated Presentation Slide Evaluation." UIST 2025. arXiv:2508.03630.
- [19] WebDevJudge. "Evaluating (M)LLMs as Critiques for Web Development Quality." arXiv:2510.18560, 2025.
- [20] Zheng, L., et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.

- [21] Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- [22] Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- [23] Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.
- [24] Wu, Q., et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." COLM 2024.

VLM
- [25] Hurst, A., et al. "GPT-4o System Card." 2024.
- [26] Gemini Team, Google. "Gemini 3 Pro Image Preview." 2026.
- [27] Sharma, G., Wu, W., & Dalal, E. N. "The CIEDE2000 color-difference formula: Implementation notes, supplementary test data, and mathematical observations." Color Research & Application, 30(1), 21–30, 2005.
