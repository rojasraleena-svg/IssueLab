"""测试自定义 Agent (agents/ 目录) 加载"""

from issuelab.sdk_executor import discover_agents


def test_discover_agents_finds_gqy22():
    """discover_agents 应该能发现 agents/ 下的 gqy22 代理"""
    agents = discover_agents()

    # 验证 metadata 中的 agent name 被加载
    assert "gqy22-reviewer" in agents
    assert agents["gqy22-reviewer"]["description"] != ""

    # 验证 directory name alias 也被加载
    assert "gqy22" in agents
    assert agents["gqy22"]["description"] != ""

    # 内容应该一致
    assert agents["gqy22"]["prompt"] == agents["gqy22-reviewer"]["prompt"]
