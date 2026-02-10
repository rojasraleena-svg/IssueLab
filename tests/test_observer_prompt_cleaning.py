"""Tests to ensure observer prompts keep non-header '---' separators intact."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_observer_prompt_preserves_hr(monkeypatch):
    from issuelab.agents import observer as observer_module

    captured = {}

    async def fake_run_single_agent(prompt: str, agent_name: str):
        captured["prompt"] = prompt
        return {"response": ""}

    def fake_discover_agents():
        return {
            "observer": {
                "description": "Observer",
                "prompt": "Intro\n---\nBody section line\n__TASK_SECTION__\nFooter",
                "trigger_conditions": [],
            }
        }

    monkeypatch.setattr(observer_module, "run_single_agent", fake_run_single_agent)
    monkeypatch.setattr(observer_module, "discover_agents", fake_discover_agents)

    await observer_module.run_observer(1, "Title", "Body", "Comments")

    prompt = captured.get("prompt", "")
    assert "Body section line" in prompt
    assert "__TASK_SECTION__" not in prompt  # should be replaced
    assert "Issue 编号" in prompt  # task section injected


@pytest.mark.asyncio
async def test_arxiv_observer_prompt_preserves_hr(monkeypatch):
    from issuelab.agents import observer as observer_module

    captured = {}

    async def fake_run_single_agent(prompt: str, agent_name: str):
        captured["prompt"] = prompt
        return {"response": ""}

    def fake_discover_agents():
        return {
            "arxiv_observer": {
                "description": "Arxiv Observer",
                "prompt": "Intro\n---\nBody section line\n__PAPERS_CONTEXT__\nFooter",
                "trigger_conditions": [],
            }
        }

    def fake_build_collaboration_guidelines(*args, **kwargs):
        return ""

    monkeypatch.setattr(observer_module, "run_single_agent", fake_run_single_agent)
    monkeypatch.setattr(observer_module, "discover_agents", fake_discover_agents)
    monkeypatch.setattr(observer_module, "build_collaboration_guidelines", fake_build_collaboration_guidelines)

    papers = [
        {
            "id": "1",
            "title": "Test Paper",
            "summary": "Summary",
            "url": "https://arxiv.org/abs/1234",
            "pdf_url": "https://arxiv.org/pdf/1234.pdf",
            "authors": "A",
            "published": "2024-01-01",
            "category": "cs.AI",
        }
    ]

    await observer_module.run_observer_for_papers(papers)

    prompt = captured.get("prompt", "")
    assert "Body section line" in prompt
    assert "__PAPERS_CONTEXT__" not in prompt
    assert "## 可讨论的 arXiv 论文候选" in prompt
