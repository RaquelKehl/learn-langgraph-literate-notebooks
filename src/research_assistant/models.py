"""LLM factory: one switch, three modes.

    LLM_MODE=fake      deterministic scripted model (mandatory in CI)
    LLM_MODE=ollama    local live model for demos (default: qwen3:8b)
    LLM_MODE=disabled  no model at all - pure graph logic

No notebook talks to a concrete model class directly; everything goes
through get_chat_model() so the live model stays swappable.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "fake_llm"

VALID_MODES = ("fake", "ollama", "disabled")


def get_llm_mode() -> str:
    mode = os.environ.get("LLM_MODE", "fake").lower()
    if mode not in VALID_MODES:
        raise ValueError(f"LLM_MODE must be one of {VALID_MODES}, got {mode!r}")
    return mode


def get_chat_model(mode: str | None = None, fixture: str | tuple[str, ...] = "default.yaml"):
    """Return a chat model for the given mode, or None when disabled.

    `fixture` may name several fixture files; their rules are tried in order.
    """
    mode = mode or get_llm_mode()
    if mode == "disabled":
        return None
    if mode == "ollama":
        from langchain_ollama import ChatOllama

        # qwen3 "thinks" before answering by default: about 60 s instead of
        # 5 s per answer here, with no better result for document questions.
        return ChatOllama(
            model=os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            temperature=0,
            reasoning=os.environ.get("OLLAMA_REASONING", "false").lower() == "true",
        )
    return ScriptedChatModel.from_fixture(fixture)


class ScriptedChatModel(BaseChatModel):
    """Deterministic chat model driven by versioned fixture rules.

    Each rule is {"match": <regex>, "response": <text>}; the first rule
    whose regex matches the latest message content wins. An unmatched
    prompt raises instead of improvising - a silent generic reply would
    hide missing fixture coverage.
    """

    rules: list[dict]
    fallback: str | None = None

    @classmethod
    def from_fixture(cls, names: str | tuple[str, ...]) -> "ScriptedChatModel":
        rules: list[dict] = []
        fallback = None
        for name in (names,) if isinstance(names, str) else names:
            data = yaml.safe_load((FIXTURES_DIR / name).read_text(encoding="utf-8"))
            rules.extend(data.get("rules") or [])
            fallback = data.get("fallback") if data.get("fallback") is not None else fallback
        return cls(rules=rules, fallback=fallback)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = str(messages[-1].content)
        for rule in self.rules:
            if re.search(rule["match"], prompt, re.IGNORECASE | re.DOTALL):
                return self._result(rule["response"])
        if self.fallback is not None:
            return self._result(self.fallback)
        raise ValueError(
            "ScriptedChatModel: no fixture rule matches prompt "
            f"{prompt[:120]!r} - add a rule to the fixture file"
        )

    @staticmethod
    def _result(text: str) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=text))]
        )

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"
