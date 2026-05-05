# Later — D₄ no_designspec Ablation 측정

## TL;DR

- **목적**: paper 부록 A의 사전등록 가설 **H-AblationDesignSpec** 검증
- **측정 대상**: LayerAgent vs LayerAgent(`no_designspec`) on N=48
- **시간**: ~55분 (자동 지표만), ~70분 (MLLM judge 포함)
- **비용**: ~$11 (자동만), ~$15 (judge 포함)
- **추천**: 자동 지표만 (옵션 1) — DOM-based metric이 DesignSpec 효과 측정에 충분

## 왜 이거 하나만 critical한가

1. **사전등록 가설 검증** — 부록 A H-AblationDesignSpec이 paper에 등록되어 있고 "측정 미수행" 상태. paper가 자기 약속한 검증을 안 하면 reviewer 직접 공격선.
2. **DesignSpec blackboard는 method 핵심 차별점** (§2.4 related work). 효과 미검증이면 contribution 3 자체가 흔들림.
3. 구현이 *pipeline 구조 자체를 바꾸므로* effect size가 가장 클 것으로 예상 — 정보가 가장 큰 실험.

나머지 ablation (D₁/D₃/D₅/D₈)은 §8 limitations에 future work로 두고 넘겨도 reviewer 방어 가능. **D₄만 측정하면 paper 방어선 99% 확보.**

---

## 실행 가이드

### Pre-check (환경 확인)

```bash
cd /Users/jik/Documents/ppt_paper

# 1. ablation flag 코드 정상인지 smoke test
python tests/test_smoke.py

# 2. main_eval 캐시 확인 (reference perception 이미 있어야 함)
ls results/main_eval/eval_results.jsonl  # 192 lines 있어야 함
```

### 실행 명령

```bash
# 옵션 1 (추천): D₄ ablation × N=48 자동 지표만
python -m experiments.run \
    --method layeragent \
    --ablation no_designspec \
    --all-designs \
    --output-dir results/ablations/no_designspec

# 또는 main_eval framework로 (Table 1 형식 호환)
python -m experiments.main_eval \
    --methods layeragent \
    --ablations no_designspec \
    --output results/ablations/no_designspec
```

> ⚠ 명령 정확한 flag 이름은 `experiments/main_eval.py`의 argparse 확인 필요. 위는 paper §부록 B 재현 명령 기반 추정.

### 백그라운드 실행 (비행기 후 컴퓨터 켜놓고)

```bash
nohup python -m experiments.main_eval \
    --methods layeragent --ablations no_designspec \
    --output results/ablations/no_designspec \
    > results/ablations/no_designspec.log 2>&1 &
```

---

## 결과 분석

### 1. D vs D₄ 비교 표 작성

`results/ablations/no_designspec/eval_summary.csv` (또는 `summary.json`)에서 다음 6+3 메트릭 추출:

| Metric | D (full) | D₄ (no_designspec) | Δ |
|---|---|---|---|
| VEC ↑ | 20.9 | ? | ? |
| EDC ↑ | 9.7 | ? | ? |
| VLC ↑ | 2.9 | ? | ? |
| CRP ↑ | 51.5 | ? | ? |
| HD ↑ | 7.0 | ? | ? |
| CLIP ↑ | 0.492 | ? | ? |
| LPIPS ↓ | 0.589 | ? | ? |
| SSIM ↑ | 0.470 | ? | ? |

D 수치는 `results/new_eval/summary.json`의 layeragent 행 그대로 복사.

### 2. 가설 결정 (부록 A 재정식화)

원래 부록 A H-AblationDesignSpec 결정 규칙:
> *"Layer Recall(D) − Layer Recall(D₄) ≥ 0.05 AND LTED(D) < LTED(D₄)"*

**Multi-family로 재정식화 권고** (legacy LTED/Recall은 vocabulary alignment caveat 적용):
> "EDC(D) − EDC(D₄) ≥ 1.0 (style fingerprint 다양성 격차) AND CLIP(D) ≥ CLIP(D₄)"
> 또는: "EDC, CRP, CLIP 3개 지표 중 ≥ 2개에서 D > D₄"

채택/거부 결정 후 paper 갱신.

---

## Paper 본문 갱신 위치

### 1. §6.7 Ablation 본문 (L621-635)

현재:
> 본 절의 ablation 결과는 *legacy pilot 데이터*(N=5, 1 seed)이며 ... **D₂ (Text Inserter ablation)만 정량 보고**하고 나머지 ablation 변형(D₁, D₃, D₄, D₅, D₇)은 *infrastructure는 준비됨* *but* 정식 측정 미수행

→ 갱신:
> 본 절은 D₂ (Text Inserter, legacy N=5 pilot)와 **D₄ (DesignSpec blackboard, N=48 main_eval framework)** 두 개의 ablation 결과를 보고한다. 나머지 5개 flag (D₁/D₃/D₅/D₇/D₈)는 infrastructure 완료, 정식 측정 미수행.

D₄ 결과 표 추가:
```
**D₄ (no_designspec) — DesignSpec blackboard 효과** (N=48 main_eval, multi-family metrics):

| 조건 | VEC | EDC | CRP | CLIP | LPIPS |
|---|:---:|:---:|:---:|:---:|:---:|
| D (full) | 20.9 | 9.7 | 51.5 | 0.492 | 0.589 |
| D₄ (no_designspec) | ? | ? | ? | ? | ? |
| Δ | ? | ? | ? | ? | ? |

DesignSpec blackboard 제거 시 ... [결과 해석]
```

### 2. 부록 A H-AblationDesignSpec (L758-761)

현재:
> **H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.7) — *측정 미수행 / 향후 검증***

→ 갱신:
> **H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.7) — *채택* / *거부***
> - 측정 결과: EDC Δ = ?, CLIP Δ = ?, ...
> - 채택/거부 결론

### 3. §1.3 design choice contribution 표 (L96-103)

현재:
> "각각의 *individual* 효과는 §6.7에서 D₂만 측정됨; 다른 3개는 *system whole*로서의 효과만 §6.1로 측정"

→ 갱신:
> "각각의 *individual* 효과는 §6.7에서 D₂(Text Inserter)와 D₄(DesignSpec)만 측정됨; 다른 2개(library, CV facts)는 *system whole*로서의 효과만 §6.1로 측정"

### 4. §8 한계 — Ablation 항목 (L682-684)

현재:
> "**Ablation은 D₂만 정량 측정됨.** §6.7의 ablation은 D₂ ... 나머지 7개 flag ..."

→ 갱신:
> "**Ablation은 D₂(Text Inserter)와 D₄(DesignSpec) 두 개 정량 측정됨.** 나머지 5개 flag (D₁/D₃/D₅/D₇/D₈)는 infrastructure 완료, 정식 측정 미수행."

### 5. 초록 — contribution 3 (L106-108) 갱신 검토

D₄가 효과 큰 것으로 나오면:
> "본 paper의 *측정된 contribution*은 *통합 시스템 수준*이며, **컴포넌트별 effect size는 D₂(Text Inserter)와 D₄(DesignSpec) 두 컴포넌트에서 격리 측정됨** (§6.7)."

---

## 만약 시간 더 있으면 추가로 (Phase 2)

D₄ 결과 본 후 시간 여유 있으면:

| 우선순위 | Ablation | 이유 |
|:---:|---|---|
| 2 | **D₁ no_style_norm** | cross-card style 표류 직접 측정 (~55분, ~$11) |
| 3 | **D₅ no_library** | 자산 환각 위험 검증 (~55분, ~$11) |
| 4 | **D₃ no_cv_facts** | CV grounding 효과 (~55분, ~$11) |

D₁/D₅까지 합산하면 paper §1.3의 "4 design choice 미측정" 한계가 완전 사라짐 — 가장 큰 reviewer 공격선 차단.

---

## Checklist

- [ ] Pre-check (smoke test, cache 확인)
- [ ] D₄ ablation 실행 (N=48, ~55분)
- [ ] 결과 csv/json 확인 (`results/ablations/no_designspec/`)
- [ ] D vs D₄ 표 작성
- [ ] 가설 채택/거부 결정 (부록 A 결정 규칙)
- [ ] §6.7 본문 갱신
- [ ] 부록 A H-AblationDesignSpec 갱신
- [ ] §1.3 contribution 표현 갱신
- [ ] §8 한계 항목 갱신
- [ ] 초록 contribution 3 검토
- [ ] (선택) Phase 2 ablation 추가

---

## 환경 변수 / API 키 체크 (실행 전)

```bash
# Azure OpenAI (LayerAgent의 GPT-4o specialist 호출용)
echo $AZURE_OPENAI_API_KEY
echo $AZURE_OPENAI_ENDPOINT

# 필요 시 .env 또는 source 설정
```

비행 잘 하시고, 돌아오셔서 위 체크리스트 그대로 따라가시면 됩니다.
