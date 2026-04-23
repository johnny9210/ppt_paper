"""Tool-grounded VLM-as-Judge with position-randomization + swap-debias.

2026 best-practice protocol:
1. **Tool grounding**: judge에게 screenshot + parsed DOM/CSS JSON을 동시 제공 (verdict consistency 71% → 89%)
2. **Position-randomization**: A/B 이미지 순서를 매번 shuffle
3. **Swap-debias**: 동일 pair를 순서 바꿔 2번 평가 후 평균
4. **Cross-model triangulation**: Claude, GPT, Gemini 세 judge로 agreement 측정

사용 예:
    from metrics.vlm_judge import ToolGroundedJudge

    judge = ToolGroundedJudge(model="claude-4.6-opus")
    result = judge.pairwise(
        reference_image_path="ref.png",
        candidate_a_path="layeragent.png",
        candidate_b_path="baseline.png",
        candidate_a_html="<html>...</html>",
        candidate_b_html="<html>...</html>",
        criteria=["Layout", "Material", "Background", "Color", "Overall"],
    )
"""
from __future__ import annotations

import base64
import json
import os
import random
from dataclasses import dataclass
from typing import Literal

from bs4 import BeautifulSoup


Criterion = Literal["Layout", "Material", "Background", "Color", "Overall"]
DEFAULT_CRITERIA: tuple[Criterion, ...] = ("Layout", "Material", "Background", "Color", "Overall")


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def extract_dom_summary(html: str, max_elements: int = 40) -> dict:
    """Judge의 tool grounding을 위한 DOM/CSS 요약을 생성한다.

    inline style, 클래스, 텍스트 내용만 추출 (토큰 절약).
    """
    soup = BeautifulSoup(html, "html.parser")
    elems: list[dict] = []
    for el in soup.find_all(True):
        info = {
            "tag": el.name,
            "class": " ".join(el.get("class", [])),
            "style": el.get("style", "")[:500],
            "text": (el.string or "").strip()[:80],
        }
        if info["style"] or info["text"]:
            elems.append(info)
        if len(elems) >= max_elements:
            break
    return {"elements": elems, "truncated": len(elems) >= max_elements}


@dataclass
class JudgeResult:
    scores_a: dict[str, float]
    scores_b: dict[str, float]
    winner: Literal["A", "B", "TIE"]
    rationale: str
    # debiasing: 2번 평가 (원래 순서 + swap)한 결과
    swap_scores_a: dict[str, float] | None = None
    swap_scores_b: dict[str, float] | None = None


PROMPT_TEMPLATE = """You are an expert visual fidelity evaluator.

You are given:
- A REFERENCE design image (the target).
- Two CANDIDATE renderings A and B (generated HTML/CSS screenshots).
- DOM/CSS summaries for each candidate (for tool-grounded verification).

Score each candidate against the REFERENCE on the following criteria (1-10 scale, higher=better):
{criteria_list}

IMPORTANT PROTOCOL:
- Use the DOM/CSS summary to anchor your judgment in concrete evidence (e.g., presence of backdrop-filter, rgba alpha values, multi-layer box-shadows).
- Do NOT let position (A first vs B first) bias your scoring — treat both candidates symmetrically.
- Cite specific style properties when justifying scores.

Return STRICT JSON:
{{
  "scores_A": {{{criterion_keys}}},
  "scores_B": {{{criterion_keys}}},
  "winner": "A" | "B" | "TIE",
  "rationale": "<=100 words grounded in specific style properties"
}}"""


class ToolGroundedJudge:
    def __init__(self, model: str = "claude-4.6-opus", seed: int | None = 42, tool_grounded: bool = True):
        """
        Args:
            tool_grounded: True면 DOM/CSS JSON 요약을 prompt에 포함 (2026 best practice).
                False면 screenshot만 — exp3 ablation용 (slide-domain에서 71→89% 효과 재확인).
        """
        self.model = model
        self.rng = random.Random(seed)
        self.tool_grounded = tool_grounded

    def _build_prompt(self, criteria: tuple[Criterion, ...]) -> str:
        criteria_list = "\n".join(f"- {c}" for c in criteria)
        criterion_keys = ", ".join(f'"{c}": <int>' for c in criteria)
        return PROMPT_TEMPLATE.format(criteria_list=criteria_list, criterion_keys=criterion_keys)

    def _call(self, messages: list[dict]) -> str:
        """Model routing: OpenAI direct, Azure, or Bedrock.

        실제 호출은 run_multi_model.py의 call_* 함수를 재사용하는 것이 깔끔.
        여기서는 시그니처만 두고 실제 dispatch는 runner에서 주입.
        """
        raise NotImplementedError("Inject via runner; see experiments/exp3_measurement_validity.py")

    def _pair_payload(
        self,
        reference_image_path: str,
        cand1_img: str,
        cand2_img: str,
        cand1_dom: dict,
        cand2_dom: dict,
        prompt: str,
        order_swapped: bool,
    ) -> list[dict]:
        a_img, b_img = (cand2_img, cand1_img) if order_swapped else (cand1_img, cand2_img)
        a_dom, b_dom = (cand2_dom, cand1_dom) if order_swapped else (cand1_dom, cand2_dom)

        content = [
            {"type": "text", "text": prompt},
            {"type": "text", "text": "REFERENCE:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(reference_image_path)}"}},
            {"type": "text", "text": "CANDIDATE A:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(a_img)}"}},
        ]
        if self.tool_grounded:
            content.append({"type": "text", "text": f"CANDIDATE A DOM/CSS summary:\n```json\n{json.dumps(a_dom)[:4000]}\n```"})
        content += [
            {"type": "text", "text": "CANDIDATE B:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(b_img)}"}},
        ]
        if self.tool_grounded:
            content.append({"type": "text", "text": f"CANDIDATE B DOM/CSS summary:\n```json\n{json.dumps(b_dom)[:4000]}\n```"})
        return [{"role": "user", "content": content}]

    def pairwise(
        self,
        reference_image_path: str,
        candidate_a_path: str,
        candidate_b_path: str,
        candidate_a_html: str,
        candidate_b_html: str,
        criteria: tuple[Criterion, ...] = DEFAULT_CRITERIA,
        call_fn=None,
    ) -> JudgeResult:
        """Position-randomized + swap-debiased pairwise comparison.

        Args:
            call_fn: (messages: list) -> str, model 호출 함수 (runner에서 주입)
        """
        if call_fn is None:
            raise ValueError("call_fn must be provided by the runner")

        prompt = self._build_prompt(criteria)
        dom_a = extract_dom_summary(candidate_a_html)
        dom_b = extract_dom_summary(candidate_b_html)

        # 1차 평가 (random order)
        order1_swapped = self.rng.random() < 0.5
        msg1 = self._pair_payload(reference_image_path, candidate_a_path, candidate_b_path,
                                   dom_a, dom_b, prompt, order1_swapped)
        raw1 = call_fn(msg1)
        result1 = _parse_json(raw1, criteria)
        # order1_swapped면 A/B 결과를 다시 뒤집어서 원래 A, B로 정규화
        if order1_swapped:
            result1["scores_A"], result1["scores_B"] = result1["scores_B"], result1["scores_A"]
            result1["winner"] = {"A": "B", "B": "A", "TIE": "TIE"}[result1["winner"]]

        # 2차 평가 (opposite order, swap-debias)
        order2_swapped = not order1_swapped
        msg2 = self._pair_payload(reference_image_path, candidate_a_path, candidate_b_path,
                                   dom_a, dom_b, prompt, order2_swapped)
        raw2 = call_fn(msg2)
        result2 = _parse_json(raw2, criteria)
        if order2_swapped:
            result2["scores_A"], result2["scores_B"] = result2["scores_B"], result2["scores_A"]
            result2["winner"] = {"A": "B", "B": "A", "TIE": "TIE"}[result2["winner"]]

        # 평균
        avg_a = {k: (result1["scores_A"][k] + result2["scores_A"][k]) / 2 for k in criteria}
        avg_b = {k: (result1["scores_B"][k] + result2["scores_B"][k]) / 2 for k in criteria}

        # 최종 winner: overall 점수 차이로 결정
        if abs(avg_a["Overall"] - avg_b["Overall"]) < 0.5:
            winner = "TIE"
        else:
            winner = "A" if avg_a["Overall"] > avg_b["Overall"] else "B"

        return JudgeResult(
            scores_a=avg_a,
            scores_b=avg_b,
            winner=winner,
            rationale=f"{result1.get('rationale', '')} | {result2.get('rationale', '')}",
            swap_scores_a=result2["scores_A"],
            swap_scores_b=result2["scores_B"],
        )


def _parse_json(raw: str, criteria: tuple[Criterion, ...]) -> dict:
    """Best-effort JSON 파싱."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        # fallback: 모두 5점
        return {
            "scores_A": {c: 5 for c in criteria},
            "scores_B": {c: 5 for c in criteria},
            "winner": "TIE",
            "rationale": "parse_failed",
        }
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return {
            "scores_A": {c: 5 for c in criteria},
            "scores_B": {c: 5 for c in criteria},
            "winner": "TIE",
            "rationale": "json_error",
        }
