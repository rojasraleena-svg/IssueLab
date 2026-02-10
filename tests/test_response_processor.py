"""测试 Response 后处理逻辑"""

from unittest.mock import patch

import pytest


class TestExtractMentionsFromYaml:
    """测试 YAML mentions 兼容层（已废弃）"""

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
        with pytest.warns(DeprecationWarning):
            assert extract_mentions_from_yaml(text) == ["alice", "bob"]

    def test_no_yaml_mentions(self):
        from issuelab.response_processor import extract_mentions_from_yaml

        with pytest.warns(DeprecationWarning):
            assert extract_mentions_from_yaml("No mentions here") == []


class TestResponseFormatConfig:
    def test_get_mentions_max_count_from_rules(self, monkeypatch):
        from issuelab import response_processor as rp

        monkeypatch.setattr(rp, "_FORMAT_RULES_CACHE", None)
        monkeypatch.setattr(rp, "_load_format_rules", lambda: {"limits": {"mentions_max_count": 7}})
        assert rp.get_mentions_max_count(default=5) == 7

    def test_get_mentions_max_count_invalid_falls_back(self, monkeypatch):
        from issuelab import response_processor as rp

        monkeypatch.setattr(rp, "_FORMAT_RULES_CACHE", None)
        monkeypatch.setattr(rp, "_load_format_rules", lambda: {"limits": {"mentions_max_count": "oops"}})
        assert rp.get_mentions_max_count(default=5) == 5


class TestTriggerMentionedAgents:
    """测试触发被@的agents"""

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_trigger_single_mentioned_agent(self, mock_trigger):
        """触发单个被@的agent"""
        from issuelab.response_processor import trigger_mentioned_agents

        mock_trigger.return_value = True

        response = """[Agent: moderator]

## Summary
Test

---
相关人员: @moderator
"""
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

        response = """[Agent: moderator]

## Summary
Test

---
相关人员: @reviewer_a @reviewer_b
"""
        results, allowed, filtered = trigger_mentioned_agents(response, 2, "Title", "Body")

        assert results == {"reviewer_a": True, "reviewer_b": True}
        assert allowed == ["reviewer_a", "reviewer_b"]
        assert filtered == []
        assert mock_trigger.call_count == 2

    @patch("issuelab.observer_trigger.auto_trigger_agent")
    def test_skip_system_accounts(self, mock_trigger):
        """跳过系统账号"""
        from issuelab.response_processor import trigger_mentioned_agents

        response = """[Agent: moderator]

## Summary
Test

---
相关人员: @github @github-actions
"""
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

        response = """[Agent: moderator]

## Summary
Test

---
相关人员: @github-actions @reviewer_a
"""
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

        response = """[Agent: moderator]

## Summary
Test

---
相关人员: @reviewer_a
"""
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
confidence: "high"
```

---
相关人员: @reviewer_a
""",
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
            agent_name="moderator",
            response={
                "response": """```yaml
summary: "Test"
findings: []
recommendations: []
confidence: "high"
```

---
相关人员: @reviewer_b
""",
                "cost_usd": 0.01,
            },
            issue_number=1,
        )

        assert result["agent_name"] == "moderator"
        assert "## Summary" in result["response"]
        assert result["mentions"] == ["reviewer_b"]

    @patch("issuelab.response_processor.trigger_mentioned_agents")
    def test_auto_dispatch_disabled(self, mock_trigger):
        """禁用自动dispatch"""
        from issuelab.response_processor import process_agent_response

        result = process_agent_response(
            agent_name="moderator",
            response="""```yaml
summary: "Test"
findings: []
recommendations: []
confidence: "high"
```

---
相关人员: @reviewer_a
""",
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

        result = process_agent_response(agent_name="moderator", response="No mentions", issue_number=1)

        assert result["mentions"] == []
        assert result["dispatch_results"] == {}
        mock_trigger.assert_not_called()


class TestNormalizeCommentBody:
    """测试评论正文规范化"""

    def test_normalize_alias_recommendations_confidence(self):
        from issuelab.response_processor import normalize_comment_body

        body = """[Agent: gqy20]

## Summary
Alias format summary.

## Key Findings
- Finding A

## Recommendations
- Action A

## Confidence
```yaml
summary: "Alias format summary."
findings:
  - "Finding A"
recommendations:
  - "Action A"
confidence: "medium"
```
"""
        normalized = normalize_comment_body(body, agent_name="gqy20")

        assert "## Recommended Actions" in normalized
        assert "## Recommendations" not in normalized
        assert "## Confidence" not in normalized
        assert "```yaml" not in normalized

    def test_strip_yaml_without_structured_heading(self):
        from issuelab.response_processor import normalize_comment_body

        body = """[Agent: moderator]

## Summary
Summary line.

## Key Findings
- A

## Recommended Actions
- [ ] Do X

```yaml
summary: "Summary line."
findings:
  - "A"
recommendations:
  - "Do X"
confidence: "high"
```
"""
        normalized = normalize_comment_body(body, agent_name="moderator")
        assert "```yaml" not in normalized
        assert "## Summary" in normalized
        assert "## Key Findings" in normalized
        assert "## Recommended Actions" in normalized

    def test_standard_structured_heading_still_works(self):
        from issuelab.response_processor import normalize_comment_body

        body = """[Agent: reviewer_a]

## Summary
Standard summary.

## Key Findings
- A

## Recommended Actions
- [ ] Do X

## Structured (YAML)
```yaml
summary: "Standard summary."
findings:
  - "A"
recommendations:
  - "Do X"
confidence: "high"
```
"""
        normalized = normalize_comment_body(body, agent_name="reviewer_a")
        assert "## Structured (YAML)" not in normalized
        assert "```yaml" not in normalized
        assert "## Summary" in normalized
        assert "## Key Findings" in normalized
        assert "## Recommended Actions" in normalized

    def test_render_sources_section_from_yaml(self):
        from issuelab.response_processor import normalize_comment_body

        body = """```yaml
summary: "S"
findings:
  - "F1"
recommendations:
  - "R1"
sources:
  - "https://example.com/a"
  - "https://example.com/b"
confidence: "high"
```"""
        normalized = normalize_comment_body(body, agent_name="gqy20")
        assert "## Sources" in normalized
        assert "https://example.com/a" in normalized
        assert "https://example.com/b" in normalized
        assert "```yaml" not in normalized
