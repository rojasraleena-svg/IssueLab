"""测试 Response 后处理逻辑"""

from unittest.mock import patch


class TestExtractMentions:
    """测试 @mention 提取"""

    def test_extract_single_mention(self):
        """提取单个@mention"""
        from issuelab.response_processor import extract_mentions

        text = "Hi @alice, please review this"
        assert extract_mentions(text) == ["alice"]

    def test_extract_multiple_mentions(self):
        """提取多个@mentions"""
        from issuelab.response_processor import extract_mentions

        text = "CC @bob and @charlie for review"
        assert extract_mentions(text) == ["bob", "charlie"]

    def test_extract_mentions_with_duplicates(self):
        """去重重复的@mentions"""
        from issuelab.response_processor import extract_mentions

        text = "@alice please check this. Thanks @alice!"
        assert extract_mentions(text) == ["alice"]

    def test_extract_mentions_with_numbers(self):
        """支持数字和下划线的用户名"""
        from issuelab.response_processor import extract_mentions

        text = "@user123 and @test_user and @gqy22"
        assert extract_mentions(text) == ["user123", "test_user", "gqy22"]

    def test_extract_mentions_with_hyphen(self):
        """支持连字符的用户名"""
        from issuelab.response_processor import extract_mentions

        text = "@github-actions and @my-agent"
        assert extract_mentions(text) == ["github-actions", "my-agent"]

    def test_no_mentions(self):
        """没有@mentions"""
        from issuelab.response_processor import extract_mentions

        text = "No mentions here"
        assert extract_mentions(text) == []

    def test_empty_string(self):
        """空字符串"""
        from issuelab.response_processor import extract_mentions

        assert extract_mentions("") == []

    def test_mentions_at_start(self):
        """@mention在开头"""
        from issuelab.response_processor import extract_mentions

        text = "@alice please review"
        assert extract_mentions(text) == ["alice"]

    def test_mentions_at_end(self):
        """@mention在结尾"""
        from issuelab.response_processor import extract_mentions

        text = "Please review @bob"
        assert extract_mentions(text) == ["bob"]

    def test_mentions_in_code_block(self):
        """代码块中的@mentions也会被提取"""
        from issuelab.response_processor import extract_mentions

        text = "```\n@alice test\n```"
        assert extract_mentions(text) == ["alice"]


class TestTriggerMentionedAgents:
    """测试触发被@的agents"""

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_single_mentioned_agent(self, mock_trigger):
        """触发单个被@的agent"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = "Hi @alice, please review"
        results = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"alice": True}
        mock_trigger.assert_called_once_with(
            agent_name="alice", issue_number=1, issue_title="Title", issue_body="Body"
        )

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_multiple_mentioned_agents(self, mock_trigger):
        """触发多个被@的agents"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = "CC @bob and @charlie"
        results = trigger_mentioned_agents(response, 2, "Title", "Body")

        assert results == {"bob": True, "charlie": True}
        assert mock_trigger.call_count == 2

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_skip_system_accounts(self, mock_trigger):
        """跳过系统账号"""
        from issuelab.response_processor import trigger_mentioned_agents

        response = "@github and @github-actions please check"
        results = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {}
        mock_trigger.assert_not_called()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_with_system_and_real_users(self, mock_trigger):
        """混合系统账号和真实用户"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = "@github-actions deployed by @alice"
        results = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"alice": True}
        mock_trigger.assert_called_once()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_no_mentions_returns_empty(self, mock_trigger):
        """没有@mentions返回空字典"""
        from issuelab.response_processor import trigger_mentioned_agents

        response = "No mentions here"
        results = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {}
        mock_trigger.assert_not_called()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_handle_trigger_failure(self, mock_trigger):
        """处理触发失败的情况"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = False

        response = "@alice please check"
        results = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"alice": False}


class TestProcessAgentResponse:
    """测试agent response处理"""

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_process_string_response(self, mock_trigger):
        """处理字符串response"""
        from issuelab.response_processor import process_agent_response

        mock_trigger.return_value = {"alice": True}

        result = process_agent_response(
            agent_name="moderator",
            response="Hi @alice",
            issue_number=1,
            issue_title="Title",
            issue_body="Body",
        )

        assert result["agent_name"] == "moderator"
        assert result["response"] == "Hi @alice"
        assert result["mentions"] == ["alice"]
        assert result["dispatch_results"] == {"alice": True}

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_process_dict_response(self, mock_trigger):
        """处理字典response"""
        from issuelab.response_processor import process_agent_response

        mock_trigger.return_value = {}

        result = process_agent_response(
            agent_name="echo",
            response={"response": "Hi @bob", "cost_usd": 0.01},
            issue_number=1,
        )

        assert result["agent_name"] == "echo"
        assert result["response"] == "Hi @bob"
        assert result["mentions"] == ["bob"]

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_auto_dispatch_disabled(self, mock_trigger):
        """禁用自动dispatch"""
        from issuelab.response_processor import process_agent_response

        result = process_agent_response(
            agent_name="test", response="Hi @alice", issue_number=1, auto_dispatch=False
        )

        assert result["mentions"] == ["alice"]
        assert result["dispatch_results"] == {}
        mock_trigger.assert_not_called()

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_no_mentions_no_dispatch(self, mock_trigger):
        """没有mentions不触发dispatch"""
        from issuelab.response_processor import process_agent_response

        result = process_agent_response(agent_name="test", response="No mentions", issue_number=1)

        assert result["mentions"] == []
        assert result["dispatch_results"] == {}
        mock_trigger.assert_not_called()
