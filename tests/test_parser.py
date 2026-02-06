"""测试 @mention 解析器"""

from issuelab.parser import AGENT_NAMES, has_agent_mentions, parse_agent_mentions


def test_parse_single_mention():
    """测试解析单个 @mention"""
    result = parse_agent_mentions("@moderator 请审核")
    assert result == ["moderator"]


def test_parse_multiple_mentions():
    """测试解析多个 @mention"""
    result = parse_agent_mentions("@moderator 审核，@reviewer_a 评审")
    assert result == ["moderator", "reviewer_a"]


def test_parse_name_mappings():
    """测试真名映射仅包含真名"""
    assert AGENT_NAMES["moderator"] == "moderator"
    assert AGENT_NAMES["reviewer_a"] == "reviewer_a"
    assert AGENT_NAMES["reviewer_b"] == "reviewer_b"
    assert AGENT_NAMES["video_manim"] == "video_manim"
    assert "mod" not in AGENT_NAMES
    assert "reva" not in AGENT_NAMES
    assert "revb" not in AGENT_NAMES


def test_parse_uppercase_mention():
    """测试大写 @Mention 也应解析"""
    result = parse_agent_mentions("@MODERATOR 审核")
    assert result == ["moderator"]


def test_has_mentions():
    """测试检测是否有 @mention"""
    assert has_agent_mentions("请 @moderator 处理") is True
    assert has_agent_mentions("这是普通评论") is False
