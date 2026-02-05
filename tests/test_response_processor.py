"""测试 Response 后处理逻辑"""

from unittest.mock import patch


class TestExtractMentionsFromYaml:
    """测试从 YAML 提取 mentions"""

    def test_extract_mentions_list(self):
        from issuelab.response_processor import extract_mentions_from_yaml

        text = """```yaml
summary: "Test"
findings:
  - "A"
recommendations:
  - "B"
mentions:
  - alice
  - bob
confidence: "high"
```"""
        assert extract_mentions_from_yaml(text) == ["alice", "bob"]

    def test_extract_mentions_with_at_prefix(self):
        from issuelab.response_processor import extract_mentions_from_yaml

        text = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - "@charlie"
  - "@delta"
confidence: "medium"
```"""
        assert extract_mentions_from_yaml(text) == ["charlie", "delta"]

    def test_extract_mentions_invalid_items_filtered(self):
        from issuelab.response_processor import extract_mentions_from_yaml

        text = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - "not valid!"
  - ""
  - "ok_user"
confidence: "low"
```"""
        assert extract_mentions_from_yaml(text) == ["ok_user"]

    def test_no_yaml_mentions(self):
        from issuelab.response_processor import extract_mentions_from_yaml

        assert extract_mentions_from_yaml("No mentions here") == []


class TestTriggerMentionedAgents:
    """测试触发被@的agents"""

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_single_mentioned_agent(self, mock_trigger):
        """触发单个被@的agent"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - moderator
confidence: "high"
```"""
        results, allowed, filtered = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"moderator": True}
        assert allowed == ["moderator"]
        assert filtered == []
        mock_trigger.assert_called_once_with(
            agent_name="moderator", issue_number=1, issue_title="Title", issue_body="Body"
        )

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_multiple_mentioned_agents(self, mock_trigger):
        """触发多个被@的agents"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - reviewer_a
  - reviewer_b
confidence: "high"
```"""
        results, allowed, filtered = trigger_mentioned_agents(response, 2, "Title", "Body")

        assert results == {"reviewer_a": True, "reviewer_b": True}
        assert allowed == ["reviewer_a", "reviewer_b"]
        assert filtered == []
        assert mock_trigger.call_count == 2

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_skip_system_accounts(self, mock_trigger):
        """跳过系统账号"""
        from issuelab.response_processor import trigger_mentioned_agents

        response = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - github
  - github-actions
confidence: "high"
```"""
        results, allowed, filtered = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {}
        assert allowed == []
        assert filtered == ["github", "github-actions"]
        mock_trigger.assert_not_called()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_with_system_and_real_users(self, mock_trigger):
        """混合系统账号和真实用户"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - github-actions
  - reviewer_a
confidence: "high"
```"""
        results, allowed, filtered = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"reviewer_a": True}
        assert allowed == ["reviewer_a"]
        assert filtered == ["github-actions"]
        mock_trigger.assert_called_once()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_no_mentions_returns_empty(self, mock_trigger):
        """没有@mentions返回空字典"""
        from issuelab.response_processor import trigger_mentioned_agents

        response = "No mentions here"
        results, allowed, filtered = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {}
        assert allowed == []
        assert filtered == []
        mock_trigger.assert_not_called()

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_handle_trigger_failure(self, mock_trigger):
        """处理触发失败的情况"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = False

        response = """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - reviewer_a
confidence: "high"
```"""
        results, allowed, filtered = trigger_mentioned_agents(response, 1, "Title", "Body")

        assert results == {"reviewer_a": False}
        assert allowed == ["reviewer_a"]
        assert filtered == []


class TestProcessAgentResponse:
    """测试agent response处理"""

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_process_string_response(self, mock_trigger):
        """处理字符串response"""
        from issuelab.response_processor import process_agent_response

        mock_trigger.return_value = ({"reviewer_a": True}, ["reviewer_a"], [])

        result = process_agent_response(
            agent_name="moderator",
            response="""```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - reviewer_a
confidence: "high"
```""",
            issue_number=1,
            issue_title="Title",
            issue_body="Body",
        )

        assert result["agent_name"] == "moderator"
        assert "## Summary" in result["response"]
        assert result["mentions"] == ["reviewer_a"]
        assert result["dispatch_results"] == {"reviewer_a": True}

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_process_dict_response(self, mock_trigger):
        """处理字典response"""
        from issuelab.response_processor import process_agent_response

        mock_trigger.return_value = ({}, [], [])

        result = process_agent_response(
            agent_name="echo",
            response={
                "response": """```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - reviewer_b
confidence: "high"
```""",
                "cost_usd": 0.01,
            },
            issue_number=1,
        )

        assert result["agent_name"] == "echo"
        assert "## Summary" in result["response"]
        assert result["mentions"] == ["reviewer_b"]

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_auto_dispatch_disabled(self, mock_trigger):
        """禁用自动dispatch"""
        from issuelab.response_processor import process_agent_response

        result = process_agent_response(
            agent_name="test",
            response="""```yaml
summary: "Test"
findings: []
recommendations: []
mentions:
  - reviewer_a
confidence: "high"
```""",
            issue_number=1,
            auto_dispatch=False,
        )

        assert result["mentions"] == ["reviewer_a"]
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
