"""测试代理模块"""

from issuelab.agents import (
    AGENT_NAMES,
    discover_agents,
    get_available_agents,
    load_prompt,
    normalize_agent_name,
    parse_agent_metadata,
)


def test_agent_name_mapping():
    """代理名称映射表仅包含真名"""
    assert AGENT_NAMES["moderator"] == "moderator"
    assert AGENT_NAMES["reviewer_a"] == "reviewer_a"
    assert AGENT_NAMES["reviewer_b"] == "reviewer_b"
    assert AGENT_NAMES["summarizer"] == "summarizer"
    assert AGENT_NAMES["video_manim"] == "video_manim"
    assert "mod" not in AGENT_NAMES
    assert "reviewer" not in AGENT_NAMES
    assert "revb" not in AGENT_NAMES
    assert "summary" not in AGENT_NAMES


def test_discover_agents():
    """测试动态发现功能"""
    agents = discover_agents()

    assert isinstance(agents, dict)
    assert len(agents) >= 4

    # 验证必需的 agent 都存在
    required_agents = ["moderator", "reviewer_a", "reviewer_b", "summarizer"]
    for agent in required_agents:
        assert agent in agents, f"Agent {agent} not found"
        assert "description" in agents[agent]
        assert "prompt" in agents[agent]
        assert len(agents[agent]["prompt"]) > 0


def test_agent_metadata_parsing():
    """测试 YAML 元数据解析"""
    agents = discover_agents()

    # 验证 observer 存在且触发条件为空列表或 None
    if "observer" in agents:
        trigger = agents["observer"]["trigger_conditions"]
        assert trigger == [] or trigger is None or trigger == "", "Observer should have empty trigger conditions"

    # 验证 moderator 有正确的元数据
    assert "moderator" in agents
    assert "审核" in agents["moderator"]["description"] or "调度" in agents["moderator"]["description"]


def test_parse_agent_metadata_valid():
    """测试元数据解析 - 有效输入"""
    content = """---
agent: test_agent
description: Test agent
trigger_conditions:
  - condition 1
  - condition 2
---
# Test Prompt
Some content here
"""
    metadata = parse_agent_metadata(content)
    assert metadata is not None
    assert metadata["agent"] == "test_agent"
    assert metadata["description"] == "Test agent"
    assert metadata["trigger_conditions"] == ["condition 1", "condition 2"]


def test_parse_agent_metadata_no_frontmatter():
    """测试元数据解析 - 无 frontmatter"""
    content = "# Just a plain prompt without frontmatter"
    metadata = parse_agent_metadata(content)
    assert metadata is None


def test_load_prompt_returns_string():
    """load_prompt 应该返回字符串，不含frontmatter"""
    result = load_prompt("moderator")
    assert isinstance(result, str)
    assert len(result) > 0
    # 验证 frontmatter 已被移除
    assert not result.startswith("---")


def test_load_prompt_unknown_agent():
    """load_prompt 对未知代理返回空字符串"""
    result = load_prompt("unknown_agent_xyz_123")
    assert result == ""


def test_normalize_agent_name():
    """normalize_agent_name 应该返回标准化名称"""
    assert normalize_agent_name("MODERATOR") == "moderator"
    assert normalize_agent_name("reviewer_a") == "reviewer_a"
    assert normalize_agent_name("reviewer_b") == "reviewer_b"
    assert normalize_agent_name("summarizer") == "summarizer"
    # 测试不存在的名称
    assert normalize_agent_name("unknown") == "unknown"
    assert normalize_agent_name("mod") == "mod"


def test_get_available_agents():
    """get_available_agents 应该返回所有可用代理"""
    agents = get_available_agents()
    assert "moderator" in agents
    assert "reviewer_a" in agents
    assert "reviewer_b" in agents
    assert "summarizer" in agents
    assert "observer" in agents
    assert "video_manim" in agents
    assert len(agents) >= 5


class TestDiscoverAgentsCache:
    """测试 discover_agents 的缓存行为"""

    def test_discover_agents_cache_reuse_and_invalidate(self, tmp_path, monkeypatch):
        from issuelab.agents import discovery as discovery_mod

        prompts_dir = tmp_path / "prompts"
        agents_dir = tmp_path / "agents"
        prompts_dir.mkdir()
        agents_dir.mkdir()

        prompt_path = prompts_dir / "moderator.md"
        prompt_path.write_text(
            "---\nagent: moderator\ndescription: test\n---\n# Moderator\nv1",
            encoding="utf-8",
        )

        monkeypatch.setattr(discovery_mod, "PROMPTS_DIR", prompts_dir)
        monkeypatch.setattr(discovery_mod, "AGENTS_DIR", agents_dir)

        agents_v1 = discovery_mod.discover_agents()
        agents_v1_again = discovery_mod.discover_agents()

        assert agents_v1 is agents_v1_again
        assert "moderator" in agents_v1
        assert "v1" in agents_v1["moderator"]["prompt"]

        prompt_path.write_text(
            "---\nagent: moderator\ndescription: test\n---\n# Moderator\nv2",
            encoding="utf-8",
        )
        # 确保 mtime 变化（避免文件系统时间粒度导致缓存未失效）
        import os

        new_mtime = prompt_path.stat().st_mtime + 2
        os.utime(prompt_path, (new_mtime, new_mtime))

        agents_v2 = discovery_mod.discover_agents()
        assert agents_v2 is not agents_v1
        assert "v2" in agents_v2["moderator"]["prompt"]


def test_builtin_prompt_can_be_overridden_by_agents_dir(tmp_path, monkeypatch):
    """内置 agent 应支持 agents/<name>/prompt.md 覆盖 prompts/<name>.md"""
    from issuelab.agents import discovery as discovery_mod

    prompts_dir = tmp_path / "prompts"
    agents_dir = tmp_path / "agents"
    prompts_dir.mkdir()
    (agents_dir / "moderator").mkdir(parents=True)

    (prompts_dir / "moderator.md").write_text(
        "---\nagent: moderator\ndescription: from-prompts\n---\n# Moderator\nfrom prompts",
        encoding="utf-8",
    )
    (agents_dir / "moderator" / "prompt.md").write_text(
        "---\nagent: moderator\ndescription: from-agents\n---\n# Moderator\nfrom agents",
        encoding="utf-8",
    )

    monkeypatch.setattr(discovery_mod, "PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr(discovery_mod, "AGENTS_DIR", agents_dir)
    discovery_mod._CACHED_AGENTS = None
    discovery_mod._CACHED_SIGNATURE = None

    agents = discovery_mod.discover_agents()
    assert "moderator" in agents
    assert "from agents" in agents["moderator"]["prompt"]
    assert agents["moderator"]["description"] == "from-agents"
