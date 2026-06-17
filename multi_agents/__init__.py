"""multi_agents 顶层包：按需导出，避免无关子包把重依赖提前拉起。"""

from __future__ import annotations

from .memory import DraftState, ResearchState

__all__ = [
    "ChiefEditorAgent",
    "EditorAgent",
    "PublisherAgent",
    "ResearchAgent",
    "ReviserAgent",
    "ReviewerAgent",
    "WriterAgent",
    "HumanAgent",
    "DraftState",
    "ResearchState",
]


def __getattr__(name: str):
    if name in {
        "ResearchAgent",
        "WriterAgent",
        "PublisherAgent",
        "ReviserAgent",
        "ReviewerAgent",
        "EditorAgent",
        "HumanAgent",
        "ChiefEditorAgent",
    }:
        from . import agents

        return getattr(agents, name)
    raise AttributeError(f"module 'multi_agents' has no attribute {name!r}")
