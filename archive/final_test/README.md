# final_test/ — LayerAgent 최종 실험 세트

본 폴더는 paper_draft_ko.md의 재프레이밍된 thesis (model-agnostic)에 맞춘
4개 실험을 실행하는 코드 일체를 포함한다.

## Thesis

단일 VLM 호출로 슬라이드 디자인을 HTML/CSS로 재현할 때, 모델 능력이 향상되어도
구조적으로 보장되지 않는 두 속성이 존재한다:

1. **Cross-Element Visual Consistency** — 독립 렌더링된 카드 간 색/투명도/테두리/그림자의 통일
2. **Joint Content-Visual Fidelity** — 풍부한 CSS 생성과 정확한 텍스트 배치의 zero-sum 경쟁 해소

LayerAgent는 이 두 속성을 명시적 단계 분리(Style Normalizer + Text Inserter)로 부과하며,
그 효과는 양적/질적 메트릭의 동반 검증으로 확인된다.

## RQs

- **RQ1 Cross-Element Consistency**: 단일 VLM은 카드 간 시각 일관성을 보장하는가?
  Style Normalizer(pre-render 정규화)가 post-hoc iteration(PPTAgent 등) 대비 효과적인가?
  이 현상은 모델 scale에 불변인가?
- **RQ2 Content-Style Isolation**: 시각/텍스트 zero-sum 트레이드오프를 단계 분리로 해소하는가?
- **RQ3 Measurement Validity**: 양적 D2C 메트릭(CSS Richness, Block-Match, element-matching)이
  perceived fidelity를 충실히 반영하는가? tool-grounded cross-model VLM-as-Judge 동반 검증의
  필요성은?

## 폴더 구조

```
final_test/
├── README.md                             # 본 문서
├── data/
│   └── slide_specs.jsonl                 # 10개 디자인 명세
├── methods/
│   ├── single_pass.py                    # 단일 VLM baseline (GPT-4o, GPT-5.4, Claude)
│   ├── layeragent_full.py                # 4단계 LayerAgent full
│   ├── layeragent_no_stylenorm.py        # RQ1 ablation (Style Normalizer 제거)
│   └── layeragent_no_textinserter.py     # RQ2 ablation (Text Inserter 제거, 텍스트를 Card Detail Agent가 처리)
├── metrics/
│   ├── consistency.py                    # ConsistencyScore (RQ1 killer metric)
│   ├── ccr_cssrich.py                    # CCR + CSS Richness (RQ2용)
│   ├── structural.py                     # Block-Match, element-IoU, CLIP, SSIM
│   └── vlm_judge.py                      # tool-grounded + position-randomize + swap-debias
├── experiments/
│   ├── exp1_consistency.py               # RQ1: 3 조건 × 10 슬라이드 × 3 seed
│   ├── exp2_content_isolation.py         # RQ2: ablation
│   ├── exp3_measurement_validity.py      # RQ3: 30 pair × 8 metric × 3 judge τ-heatmap (headline)
│   ├── exp4_scale_invariance.py          # model-agnostic 검증 (GPT-4o vs GPT-5.4 vs Claude)
│   └── stats.py                          # Wilcoxon, Kendall τ, Cohen κ, bootstrap CI
└── results/
    ├── raw/                              # 개별 run JSON
    ├── tables/                           # paper-ready CSV
    └── figures/                          # orthogonality plot, τ-heatmap
```

## 실행 순서

```bash
# 환경변수 세팅 (OPENAI_API_KEY, APIM_AOAI_API_KEY, AWS_*)
cd final_test/

# 1. RQ1 ablation (consistency)
python -m experiments.exp1_consistency --n_seeds 3

# 2. RQ2 ablation (content-style isolation)
python -m experiments.exp2_content_isolation --n_seeds 3

# 3. RQ3 killer experiment (measurement validity)
python -m experiments.exp3_measurement_validity --n_pairs 30 --judges claude,gpt4o,gemini

# 4. model-agnostic 검증
python -m experiments.exp4_scale_invariance --models gpt-4o,gpt-5.4,claude-4.6-opus

# 분석
python -m experiments.stats --expdir results/
```

## 예상 비용 / 시간

| 실험 | LLM 호출 | 비용 | 시간 |
|---|---|---|---|
| exp1 consistency | ~90 | ~$5 | 2h |
| exp2 content isolation | ~60 | ~$3 | 1.5h |
| exp3 measurement validity | ~360 | ~$25 | 4h |
| exp4 scale invariance | ~30 | ~$3 | 1h |
| **Total** | **~540** | **~$36** | **~8h** |

## 리뷰어 피드백 반영 사항

- **Tool-grounded judge** (DOM JSON + screenshot 동시 제공): 2026 VLM-judge 71→89% consistency
- **Position-randomization + swap-debias**: 2026 standard protocol 준수
- **Cross-model triangulation** (Claude + GPT + Gemini): self-eval bias 제거
- **Model-agnostic 검증 포함** (exp4): 본 thesis의 핵심 주장 empirical backing
- **ConsistencyScore 명시 정의**: σ-normalized 변동계수 기반 — RQ1 headline metric으로 정립

## 참고 외부 연구 (2026)

- **DreamHouse** (arXiv:2603.24866): structural/visual fidelity orthogonality (joint pass 7.1%) — RQ3 외부 앵커
- **A2UI Protocol** (Google, 2026): cross-element consistency를 agent-driven UI 핵심 과제로 명시 — RQ1 문제의식 공유
- **Tool-grounded VLM judge** (2026): 71%→89% verdict consistency — 본 프로토콜 채택 근거
- **PPTAgent** (EMNLP 2025 main): iterative editing 접근 — decomposition axis 비교 대상
