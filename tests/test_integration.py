"""集成测试 - 验证模块间协作"""

from issuelab.agents import discover_agents, load_prompt, normalize_agent_name
from issuelab.parser import parse_agent_mentions


def test_parser_agent_integration():
    """测试 parser 和 agents 模块的集成"""
    # 解析 @mention
    comment = "@moderator please review @reviewer_a @reviewer_b"
    agents = parse_agent_mentions(comment)

    # 验证所有解析的 agent 都存在
    discovered = discover_agents()
    for agent in agents:
        assert agent in discovered, f"Agent {agent} not found in discovered agents"


def test_name_mapping_consistency():
    """测试名称映射在不同模块中的一致性"""
    from issuelab.agents import AGENT_NAMES as AGENTS_NAMES
    from issuelab.parser import AGENT_NAMES as PARSER_NAMES

    # 两个模块应该引用相同的对象
    assert AGENTS_NAMES is PARSER_NAMES


def test_end_to_end_agent_loading():
    """端到端测试：从名称到加载 prompt"""
    # 使用真名
    name = "moderator"

    # 1. 标准化
    normalized = normalize_agent_name(name)
    assert normalized == "moderator"

    # 2. 加载 prompt
    prompt = load_prompt(normalized)
    assert len(prompt) > 0
    assert "Moderator" in prompt or "审核" in prompt


def test_all_prompts_loadable():
    """验证所有发现的 agent 都能正确加载 prompt"""
    agents = discover_agents()

    for agent_name in agents:
        prompt = load_prompt(agent_name)
        assert len(prompt) > 0, f"Agent {agent_name} has empty prompt"
        assert not prompt.startswith("---"), f"Agent {agent_name} prompt should be plain markdown"


def test_agent_descriptions_present():
    """验证所有 agent 都有描述信息"""
    agents = discover_agents()

    for agent_name, config in agents.items():
        assert "description" in config, f"Agent {agent_name} missing description"
        assert len(config["description"]) > 0, f"Agent {agent_name} has empty description"


def test_trigger_conditions_format():
    """验证触发条件格式正确"""
    agents = discover_agents()

    for agent_name, config in agents.items():
        assert "trigger_conditions" in config, f"Agent {agent_name} missing trigger_conditions"
        trigger = config["trigger_conditions"]
        # 触发条件可以是列表、空列表、None 或空字符串
        assert isinstance(
            trigger, list | type(None) | str
        ), f"Agent {agent_name} trigger_conditions has invalid type: {type(trigger)}"
