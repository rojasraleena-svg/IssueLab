"""测试自定义 Agent (agents/ 目录) 加载"""

from issuelab.agents.discovery import discover_agents


def test_discover_agents_finds_gqy22():
    """discover_agents 应该能发现 agents/ 下的 gqy22 代理（使用目录名）"""
    agents = discover_agents()

    # 验证使用目录名作为 agent_id
    assert "gqy22" in agents
    assert agents["gqy22"]["description"] != ""
    assert len(agents["gqy22"]["prompt"]) > 0
    # Prompt 应该是纯正文
    assert not agents["gqy22"]["prompt"].startswith("---")
