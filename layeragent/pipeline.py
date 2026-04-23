"""LayerAgent 메인 파이프라인.

Usage:
    from layeragent import LayerAgent
    agent = LayerAgent(model="gpt-4o", ablation="none", use_visual_critic=False)
    html = agent.run("design_10_stats_hero")

Ablation-aware LangGraph:
- 각 agent는 state["ablation"] 을 보고 분기 처리
- no_designspec 은 pipeline 구조 자체를 바꾸므로 build 시점에 분기
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .ablations import validate
from .agents.analyzer import analyzer
from .agents.assembler import assembler
from .agents.bg_agents import base_bg_agent, atmosphere_agent, decoration_agent
from .agents.card_detail import card_detail_agents
from .agents.design_director import design_director
from .agents.hero_detail import hero_detail_agents
from .agents.icon_agent import icon_agent
from .agents.style_normalizer import style_normalizer
from .agents.text_inserter import text_inserter
from .agents.visual_critic import visual_critic
from .state import State
from .utils.common import (
    b64_image, extract_html, get_design_by_id, load_meta, save_run,
)


def _noop_director(state) -> dict:
    """no_designspec ablation용 — 빈 DesignSpec."""
    return {"design_spec": {}}


def build_pipeline(ablation: str = "none", use_visual_critic: bool = False):
    """LayerAgent LangGraph compile.

    Args:
        ablation: 플래그 중 하나 ("none", "no_style_norm", ...)
        use_visual_critic: Visual Critic stage 포함 여부
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
    g.add_node("assembler", assembler)
    g.add_node("style_normalizer", style_normalizer)
    g.add_node("text_inserter", text_inserter)
    if use_visual_critic:
        g.add_node("visual_critic", visual_critic)

    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "design_director")

    for node in ("base_bg_agent", "atmosphere_agent", "decoration_agent",
                 "card_detail_agents", "hero_detail_agents", "icon_agent"):
        g.add_edge("design_director", node)
        g.add_edge(node, "assembler")

    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", "text_inserter")
    if use_visual_critic:
        g.add_edge("text_inserter", "visual_critic")
        g.add_edge("visual_critic", END)
    else:
        g.add_edge("text_inserter", END)
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
    ):
        self.model = model
        self.ablation = validate(ablation)
        self.use_visual_critic = use_visual_critic
        self._pipeline = build_pipeline(self.ablation, self.use_visual_critic)

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

    def _default_method_name(self) -> str:
        parts = ["layeragent"]
        if self.ablation != "none":
            parts.append(self.ablation)
        if self.use_visual_critic:
            parts.append("vc")
        return "-".join(parts)
