"""Tests for the LLM factory and the scripted fake model."""
import pytest
from langchain_core.messages import HumanMessage

from research_assistant.models import (
    ScriptedChatModel,
    get_chat_model,
    get_llm_mode,
)


def test_default_mode_is_fake(monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    assert get_llm_mode() == "fake"


def test_invalid_mode_raises(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "gpt-please")
    with pytest.raises(ValueError):
        get_llm_mode()


def test_disabled_mode_returns_none():
    assert get_chat_model("disabled") is None


def test_scripted_model_matches_first_rule():
    model = ScriptedChatModel(
        rules=[
            {"match": "(?i)revenue", "response": "Answer A"},
            {"match": ".*", "response": "Answer B"},
        ]
    )
    reply = model.invoke([HumanMessage(content="What was the revenue?")])
    assert reply.content == "Answer A"
    assert model.invoke([HumanMessage(content="something else")]).content == "Answer B"


def test_scripted_model_is_deterministic():
    model = ScriptedChatModel(rules=[{"match": ".*", "response": "always the same"}])
    runs = {model.invoke([HumanMessage(content="x")]).content for _ in range(3)}
    assert runs == {"always the same"}


def test_unmatched_prompt_fails_loud():
    model = ScriptedChatModel(rules=[{"match": "^nur-das$", "response": "ok"}])
    with pytest.raises(ValueError, match="no fixture rule"):
        model.invoke([HumanMessage(content="something else")])


def test_fixture_file_loads():
    model = get_chat_model("fake")
    assert model.invoke([HumanMessage(content="ping")]).content == "pong (scripted)"
