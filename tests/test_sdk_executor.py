"""测试 SDK 执行器"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from issuelab.sdk_executor import (
    create_agent_options,
    discover_agents,
    load_prompt,
    parse_observer_response,
)


def test_discover_agents_returns_dict():
    """discover_agents 应该返回字典"""
    agents = discover_agents()
    assert isinstance(agents, dict)
    assert len(agents) > 0


def test_create_agent_options_has_agents():
    """create_agent_options 应该包含所有定义的代理（observer除外）"""
    options = create_agent_options()
    assert hasattr(options, "agents")
    assert "moderator" in options.agents
    assert "reviewer_a" in options.agents
    assert "reviewer_b" in options.agents
    assert "summarizer" in options.agents
    # observer 不在此列表中（单独处理）
    assert "observer" not in options.agents


def test_create_agent_options_has_setting_sources():
    """create_agent_options 应该设置 setting_sources"""
    options = create_agent_options()
    assert hasattr(options, "setting_sources")
    assert "user" in options.setting_sources
    assert "project" in options.setting_sources


def test_load_prompt_moderator():
    """load_prompt 应该加载 moderator 提示词"""
    result = load_prompt("moderator")
    assert "Moderator" in result or "分诊" in result
    assert len(result) > 0


def test_load_prompt_unknown_agent():
    """load_prompt 对未知代理返回空"""
    result = load_prompt("unknown_agent_that_does_not_exist")
    assert result == ""


class TestParseObserverResponse:
    """测试 Observer 响应解析"""

    def test_parse_yaml_block_scalar_trigger(self):
        """测试 YAML 块标量格式 - 触发场景"""
        response = """```yaml
analysis: |
  Issue #123 是一个新论文讨论，包含 arXiv 链接和论文模板

should_trigger: true

agent: moderator

comment: |
  @Moderator 请分诊这篇论文，它包含 arXiv 链接和模板

reason: |
  Issue #123 包含论文模板和 arXiv 链接，需要分诊决定后续评审流程
```"""
        result = parse_observer_response(response, 123)
        assert result["should_trigger"] is True
        assert result["agent"] == "moderator"
        assert "@Moderator" in result["comment"]
        assert "分诊" in result["reason"]
        assert "arXiv" in result["analysis"]

    def test_parse_yaml_block_scalar_skip(self):
        """测试 YAML 块标量格式 - 跳过场景"""
        response = """```yaml
analysis: |
  Issue #456 是一个技术问题，已有 @ReviewerA 进行分析

should_trigger: false

reason: |
  该 Issue 已有合适的 Agent 参与，无需重复触发
```"""
        result = parse_observer_response(response, 456)
        assert result["should_trigger"] is False
        assert "已有" in result["reason"]

    def test_parse_yaml_simple_key_value(self):
        """测试 YAML 简单键值对格式（无代码块）"""
        # 注意：YAML 值包含 @ 时需要用引号包裹
        response = """analysis: 测试分析
should_trigger: true
agent: reviewer_a
comment: "@ReviewerA 评审"
reason: 测试原因"""
        result = parse_observer_response(response, 1)
        assert result["should_trigger"] is True
        assert result["agent"] == "reviewer_a"
        assert "@ReviewerA" in result["comment"]

    def test_parse_empty_response(self):
        """测试空响应"""
        result = parse_observer_response("", 1)
        assert result["should_trigger"] is False
        assert result["agent"] == ""
        assert result["comment"] == ""

    def test_parse_invalid_yaml(self):
        """测试无效 YAML（应返回默认值）"""
        result = parse_observer_response("这不是 YAML 格式", 1)
        assert result["should_trigger"] is False
        assert result["agent"] == ""

    def test_parse_default_comment(self):
        """测试默认触发评论"""
        response = """```yaml
analysis: 测试

should_trigger: true

agent: summarizer
```"""
        result = parse_observer_response(response, 1)
        assert result["should_trigger"] is True
        assert result["agent"] == "summarizer"
        assert "@Summarizer" in result["comment"]


class TestStreamingOutput:
    """测试流式输出功能"""

    @pytest.mark.asyncio
    async def test_text_block_outputs_to_console_and_log(self):
        """TextBlock 应该输出到终端和日志"""
        from issuelab.sdk_executor import run_single_agent
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import TextBlock

        text_responses = ["Hello ", "World"]

        async def mock_query(*args, **kwargs):
            # 模拟 TextBlock
            for text in text_responses:
                msg = MagicMock(spec=AssistantMessage)
                msg.content = [TextBlock(text=text)]
                yield msg

            # 模拟 ResultMessage
            result = MagicMock(spec=ResultMessage)
            result.total_cost_usd = 0.01
            result.num_turns = 1
            result.session_id = "test-session"
            yield result

        with patch("issuelab.sdk_executor.query", mock_query):
            with patch("builtins.print") as mock_print:
                result = await run_single_agent("test prompt", "test_agent")
                # 验证 print 被调用（流式输出）
                assert mock_print.call_count >= len(text_responses)

    @pytest.mark.asyncio
    async def test_tool_use_block_outputs_to_console_and_log(self):
        """ToolUseBlock 应该输出到终端和日志"""
        from issuelab.sdk_executor import run_single_agent
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import ToolUseBlock

        async def mock_query(*args, **kwargs):
            # 模拟 ToolUseBlock
            tool_block = MagicMock(spec=ToolUseBlock)
            tool_block.name = "Read"
            tool_block.input = {"file_path": "/test/file.txt"}
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [tool_block]
            yield msg

            # 模拟 ResultMessage
            result = MagicMock(spec=ResultMessage)
            result.total_cost_usd = 0.01
            result.num_turns = 1
            result.session_id = "test-session"
            yield result

        with patch("issuelab.sdk_executor.query", mock_query):
            with patch("builtins.print") as mock_print:
                result = await run_single_agent("test prompt", "test_agent")
                # 验证工具名被输出
                assert any("Read" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.asyncio
    async def test_thinking_block_is_skipped(self):
        """ThinkingBlock 应该被跳过，不输出"""
        from issuelab.sdk_executor import run_single_agent
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import ThinkingBlock

        async def mock_query(*args, **kwargs):
            # 模拟 ThinkingBlock
            thinking_block = MagicMock(spec=ThinkingBlock)
            thinking_block.thinking = "This is private thinking"
            thinking_block.signature = "sig123"
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [thinking_block]
            yield msg

            # 模拟 ResultMessage
            result = MagicMock(spec=ResultMessage)
            result.total_cost_usd = 0.01
            result.num_turns = 1
            result.session_id = "test-session"
            yield result

        with patch("issuelab.sdk_executor.query", mock_query):
            with patch("builtins.print") as mock_print:
                result = await run_single_agent("test prompt", "test_agent")
                # 验证 Thinking 内容没有被输出
                assert not any("This is private thinking" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.asyncio
    async def test_tool_result_block_logs_only(self):
        """ToolResultBlock 应该只记录日志，不输出到终端"""
        from issuelab.sdk_executor import run_single_agent
        from claude_agent_sdk import AssistantMessage, ResultMessage
        from claude_agent_sdk.types import ToolResultBlock

        async def mock_query(*args, **kwargs):
            # 模拟 ToolResultBlock
            result_block = MagicMock(spec=ToolResultBlock)
            result_block.tool_use_id = "tool-123"
            result_block.content = "Very long result content..." * 100
            result_block.is_error = False
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [result_block]
            yield msg

            # 模拟 ResultMessage
            result = MagicMock(spec=ResultMessage)
            result.total_cost_usd = 0.01
            result.num_turns = 1
            result.session_id = "test-session"
            yield result

        with patch("issuelab.sdk_executor.query", mock_query):
            with patch("builtins.print") as mock_print:
                result = await run_single_agent("test prompt", "test_agent")
                # 验证工具结果内容没有被完整输出（避免刷屏）
                assert not any("Very long result" in str(call) for call in mock_print.call_args_list)
