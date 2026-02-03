"""测试代理模块"""

from issuelab.agents import (
    AGENT_ALIASES,
    discover_agents,
    get_available_agents,
    load_prompt,
    normalize_agent_name,
    parse_agent_metadata,
)


def test_agent_aliases_mapping():
    """代理别名映射表必须正确"""
    # Moderator 别名
    assert AGENT_ALIASES["moderator"] == "moderator"
    assert AGENT_ALIASES["mod"] == "moderator"

    # ReviewerA 别名
    assert AGENT_ALIASES["reviewer"] == "reviewer_a"
    assert AGENT_ALIASES["reviewera"] == "reviewer_a"
    assert AGENT_ALIASES["reva"] == "reviewer_a"

    # ReviewerB 别名
    assert AGENT_ALIASES["reviewerb"] == "reviewer_b"
    assert AGENT_ALIASES["revb"] == "reviewer_b"

    # Summarizer 别名
    assert AGENT_ALIASES["summarizer"] == "summarizer"
    assert AGENT_ALIASES["summary"] == "summarizer"


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
    assert normalize_agent_name("mod") == "moderator"
    assert normalize_agent_name("MODERATOR") == "moderator"
    assert normalize_agent_name("reviewer") == "reviewer_a"
    assert normalize_agent_name("revb") == "reviewer_b"
    assert normalize_agent_name("summary") == "summarizer"
    # 测试不存在的别名
    assert normalize_agent_name("unknown") == "unknown"


def test_get_available_agents():
    """get_available_agents 应该返回所有可用代理"""
    agents = get_available_agents()
    assert "moderator" in agents
    assert "reviewer_a" in agents
    assert "reviewer_b" in agents
    assert "summarizer" in agents
    assert "observer" in agents
    assert len(agents) >= 5
