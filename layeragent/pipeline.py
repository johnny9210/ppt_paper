"""LayerAgent 메인 파이프라인.

Usage:
    from layeragent import LayerAgent
    agent = LayerAgent(model="gpt-4o", ablation="none", use_visual_critic=False)
    html = agent.run("design_10_stats_hero")              # benchmark mode
    html = agent.run_from_chat("ref.png", "Q4 매출 대시보드. 매출 128억 +23%, ...")  # chat mode

Ablation-aware LangGraph:
- 각 agent는 state["ablation"] 을 보고 분기 처리
- no_designspec 은 pipeline 구조 자체를 바꾸므로 build 시점에 분기
"""
from __future__ import annotations

import base64
from pathlib import Path

from langgraph.graph import StateGraph, START, END

from .ablations import validate
from .agents.analyzer import analyzer
from .agents.assembler import assembler
from .agents.bg_agents import base_bg_agent, atmosphere_agent, decoration_agent
from .agents.card_detail import card_detail_agents
from .agents.chart_agent import chart_agent
from .agents.chat_parser import chat_parser
from .agents.design_director import design_director
from .agents.hero_detail import hero_detail_agents
from .agents.icon_agent import icon_agent
from .agents.overflow_repair import overflow_repair
from .agents.style_normalizer import style_normalizer
from .agents.table_agent import table_agent
from .agents.text_inserter import text_inserter
from .agents.visual_critic import visual_critic
from .state import State
from .utils.common import (
    b64_image, extract_html, get_design_by_id, load_meta, save_run,
)


def _noop_director(state) -> dict:
    """no_designspec ablation용 — 빈 DesignSpec."""
    return {"design_spec": {}}


def _noop_chart(state) -> dict:
    return {"chart_html": ""}


def _noop_overflow(state) -> dict:
    return {"assembled": state.get("assembled", ""), "overflow_report": []}


def build_pipeline(
    ablation: str = "none",
    use_visual_critic: bool = False,
    use_overflow_repair: bool = True,
):
    """LayerAgent v10 LangGraph compile.

    Args:
        ablation: 플래그 중 하나 ("none", "no_style_norm", ...)
        use_visual_critic: Visual Critic stage 포함 여부 (D+VC ablation)
        use_overflow_repair: overflow_repair stage 포함 여부 (기본 on — v10 P1)
    """
    g = StateGraph(State)
    g.add_node("analyzer", analyzer)

    if ablation == "no_designspec":
        g.add_node("design_director", _noop_director)
    else:
        g.add_node("design_director", design_director)

    g.add_node("base_bg_agent", base_bg_agent)
    g.add_node("atmosphere_agent", atmosphere_agent)
    g.add_node("decoration_agent", decoration_agent)
    g.add_node("card_detail_agents", card_detail_agents)
    g.add_node("hero_detail_agents", hero_detail_agents)
    g.add_node("icon_agent", icon_agent)

    # v10 P1: chart_agent
    if ablation == "no_chart_agent":
        g.add_node("chart_agent", _noop_chart)
    else:
        g.add_node("chart_agent", chart_agent)

    g.add_node("table_agent", table_agent)

    g.add_node("assembler", assembler)
    g.add_node("style_normalizer", style_normalizer)
    g.add_node("text_inserter", text_inserter)

    # v10 P1: overflow_repair (optional toggle)
    repair_enabled = use_overflow_repair and ablation != "no_overflow_repair"
    if repair_enabled:
        g.add_node("overflow_repair", overflow_repair)

    if use_visual_critic:
        g.add_node("visual_critic", visual_critic)

    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "design_director")

    for node in ("base_bg_agent", "atmosphere_agent", "decoration_agent",
                 "card_detail_agents", "hero_detail_agents", "icon_agent",
                 "chart_agent", "table_agent"):
        g.add_edge("design_director", node)
        g.add_edge(node, "assembler")

    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", "text_inserter")

    prev = "text_inserter"
    if repair_enabled:
        g.add_edge(prev, "overflow_repair")
        prev = "overflow_repair"
    if use_visual_critic:
        g.add_edge(prev, "visual_critic")
        prev = "visual_critic"
    g.add_edge(prev, END)
    return g.compile()


class LayerAgent:
    """LayerAgent 프레임워크 — 슬라이드 디자인 이미지 → HTML/CSS.

    Attributes:
        model: VLM 모델 이름 (gpt-4o, gpt-5.4, claude-4.6-opus)
        ablation: ablation flag (기본 "none")
        use_visual_critic: Visual Critic stage 여부
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        ablation: str = "none",
        use_visual_critic: bool = False,
        use_overflow_repair: bool = True,
    ):
        self.model = model
        self.ablation = validate(ablation)
        self.use_visual_critic = use_visual_critic
        self.use_overflow_repair = use_overflow_repair
        self._pipeline = build_pipeline(
            self.ablation, self.use_visual_critic, self.use_overflow_repair
        )

    def run(self, slide_id: str, seed: int = 0) -> str:
        """슬라이드 ID 받아 HTML 생성."""
        meta = load_meta()
        design = get_design_by_id(meta, slide_id)
        result = self._pipeline.invoke({
            "image_b64": b64_image(slide_id),
            "slide_id": slide_id,
            "slide_type": design["type"],
            "content": design["content"],
            "style": meta["style"],
            "model": self.model,
            "ablation": self.ablation,
        })
        return extract_html(result.get("assembled", ""))

    def run_and_save(self, slide_id: str, seed: int = 0, method_name: str | None = None):
        """run + save_run 한 방에."""
        html = self.run(slide_id, seed)
        method = method_name or self._default_method_name()
        return save_run(method, slide_id, seed, html)

    def run_from_chat(
        self,
        image_path: str | Path,
        user_message: str,
        slide_id: str = "chat_slide",
    ) -> tuple[str, dict]:
        """자유 텍스트(채팅) + 디자인 이미지 → HTML 1장.

        meta.json 의 사전 정의 콘텐츠 대신, chat_parser 가 사용자 메시지를
        구조화된 spec({slide_type, content, style})으로 변환한 뒤 기존
        파이프라인에 그대로 흘려보낸다.

        Args:
            image_path: 참조 디자인 이미지 경로 (PNG/JPG).
            user_message: 사용자 자연어 브리프.
            slide_id: 결과 식별용 라벨 (저장 파일명에 쓰임).

        Returns:
            (html, spec) — 생성된 HTML 본문, chat_parser 가 추출한 spec.
        """
        path = Path(image_path)
        image_b64 = base64.b64encode(path.read_bytes()).decode()
        spec = chat_parser(image_b64, user_message, model=self.model)

        result = self._pipeline.invoke({
            "image_b64": image_b64,
            "slide_id": slide_id,
            "slide_type": spec["slide_type"],
            "content": spec["content"],
            "style": spec["style"],
            "model": self.model,
            "ablation": self.ablation,
        })
        return extract_html(result.get("assembled", "")), spec

    def run_from_chat_and_save(
        self,
        image_path: str | Path,
        user_message: str,
        slide_id: str = "chat_slide",
        seed: int = 0,
        method_name: str | None = None,
    ):
        """run_from_chat + save_run. spec 도 .meta.json 으로 함께 기록."""
        html, spec = self.run_from_chat(image_path, user_message, slide_id)
        method = method_name or (self._default_method_name() + "-chat")
        meta = {"user_message": user_message, "parsed_spec": spec,
                "image_path": str(image_path)}
        return save_run(method, slide_id, seed, html, meta=meta)

    def _default_method_name(self) -> str:
        parts = ["layeragent"]
        if self.ablation != "none":
            parts.append(self.ablation)
        if self.use_visual_critic:
            parts.append("vc")
        return "-".join(parts)
