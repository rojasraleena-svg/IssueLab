"""测试 @mention 解析器"""
from issuelab.parser import parse_mentions, has_mentions, AGENT_ALIASES


def test_parse_single_mention():
    """测试解析单个 @mention"""
    result = parse_mentions("@moderator 请分诊")
    assert result == ["moderator"]


def test_parse_multiple_mentions():
    """测试解析多个 @mention"""
    result = parse_mentions("@Moderator 分诊，@ReviewerA 评审")
    assert result == ["moderator", "reviewer_a"]


def test_parse_alias_mappings():
    """测试别名映射"""
    assert AGENT_ALIASES["mod"] == "moderator"
    assert AGENT_ALIASES["reva"] == "reviewer_a"
    assert AGENT_ALIASES["revb"] == "reviewer_b"


def test_parse_uppercase_mention():
    """测试大写 @Mention 也应解析"""
    result = parse_mentions("@MODERATOR 分诊")
    assert result == ["moderator"]


def test_has_mentions():
    """测试检测是否有 @mention"""
    assert has_mentions("请 @moderator 处理") is True
    assert has_mentions("这是普通评论") is False
