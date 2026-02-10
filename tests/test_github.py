"""测试 GitHub 工具"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from issuelab.tools.github import MAX_COMMENT_LENGTH, get_issue_info, post_comment, truncate_text, update_label


def test_get_issue_info():
    """测试获取 Issue 信息"""
    # Mock gh 命令返回
    with patch("issuelab.tools.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"number":1,"title":"测试 Issue","body":"内容","labels":[{"name":"bug"}]}'
        )

        result = get_issue_info(1)

        assert result["number"] == 1
        assert result["title"] == "测试 Issue"
        mock_run.assert_called_once()


def test_post_comment():
    """测试发布评论"""
    with patch("issuelab.tools.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = post_comment(1, "测试评论")

        # 新的实现返回 bool
        assert result is True
        mock_run.assert_called_once()


def test_post_comment_limits_mentions(monkeypatch):
    """相关人员区域按配置上限输出"""
    body = "分析正文\n\n---\n相关人员: @arxiv_observer @gqy22 @observer @summarizer @moderator"

    captured = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr("issuelab.tools.github._load_mentions_max_count", lambda: 2)
    monkeypatch.setattr(
        "issuelab.mention_policy.filter_mentions", lambda mentions, policy=None, issue_number=None: (mentions, [])
    )

    result = post_comment(1, body)
    assert result is True

    cmd = captured.get("cmd", [])
    assert "--body-file" in cmd
    body_path = cmd[cmd.index("--body-file") + 1]
    content = Path(body_path).read_text(encoding="utf-8")

    last_line = content.strip().splitlines()[-1]
    assert last_line == "相关人员: @arxiv_observer @gqy22"


def test_post_comment_mentions_limit_from_config(monkeypatch):
    body = "分析正文\n\n---\n相关人员: @a1 @a2 @a3 @a4"

    captured = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr("issuelab.tools.github._load_mentions_max_count", lambda: 3)
    monkeypatch.setattr(
        "issuelab.mention_policy.filter_mentions", lambda mentions, policy=None, issue_number=None: (mentions, [])
    )

    result = post_comment(1, body)
    assert result is True

    cmd = captured.get("cmd", [])
    body_path = cmd[cmd.index("--body-file") + 1]
    content = Path(body_path).read_text(encoding="utf-8")
    assert content.strip().splitlines()[-1] == "相关人员: @a1 @a2 @a3"


def test_post_comment_replaces_existing_controlled_footer(monkeypatch):
    body = "分析正文\n\n---\n相关人员: @legacy1 @legacy2"
    captured = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr(
        "issuelab.mention_policy.filter_mentions", lambda mentions, policy=None, issue_number=None: (mentions, [])
    )

    result = post_comment(1, body, mentions=["alice"])
    assert result is True

    cmd = captured.get("cmd", [])
    body_path = cmd[cmd.index("--body-file") + 1]
    content = Path(body_path).read_text(encoding="utf-8")
    assert content.count("相关人员:") == 1
    assert content.strip().splitlines()[-1] == "相关人员: @alice"


def test_post_comment_keeps_original_body_without_normalize(monkeypatch):
    body = """[Agent: reviewer_a]

## Summary
保留正文

## Structured (YAML)
```yaml
summary: "hello"
mentions:
  - alice
```
"""

    captured = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr(
        "issuelab.mention_policy.filter_mentions", lambda mentions, policy=None, issue_number=None: (mentions, [])
    )

    result = post_comment(1, body)
    assert result is True

    cmd = captured.get("cmd", [])
    body_path = cmd[cmd.index("--body-file") + 1]
    content = Path(body_path).read_text(encoding="utf-8")
    assert "## Structured (YAML)" in content
    assert "```yaml" in content


def test_post_comment_with_explicit_mentions_does_not_parse_body(monkeypatch):
    captured = {"filtered": None}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    def fake_filter_mentions(mentions, policy=None, issue_number=None):
        captured["filtered"] = list(mentions)
        return mentions, []

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr("issuelab.mention_policy.filter_mentions", fake_filter_mentions)
    monkeypatch.setattr(
        "issuelab.utils.mentions.extract_controlled_mentions",
        lambda _body: (_ for _ in ()).throw(AssertionError("should not parse body mentions")),
    )

    result = post_comment(1, "plain body", mentions=["alice", "bob"])
    assert result is True
    assert captured["filtered"] == ["alice", "bob"]


def test_post_comment_does_not_fallback_to_plain_text_mentions(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output, text, env):
        captured["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr("issuelab.tools.github.subprocess.run", fake_run)
    monkeypatch.setattr("issuelab.tools.github.os.unlink", lambda _path: None)
    monkeypatch.setattr("issuelab.utils.mentions.extract_controlled_mentions", lambda _body: [])
    monkeypatch.setattr(
        "issuelab.mention_policy.filter_mentions", lambda mentions, policy=None, issue_number=None: (mentions, [])
    )

    result = post_comment(1, "plain body with @alice")
    assert result is True

    cmd = captured.get("cmd", [])
    body_path = cmd[cmd.index("--body-file") + 1]
    content = Path(body_path).read_text(encoding="utf-8")
    assert "相关人员:" not in content


def test_update_label():
    """测试更新标签"""
    with patch("issuelab.tools.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = update_label(1, "bug", action="add")

        # 新的实现返回 bool
        assert result is True
        mock_run.assert_called_once()


def test_truncate_text_short_text_not_truncated():
    text = "Short text"
    result = truncate_text(text)
    assert result == text
    assert "已截断" not in result


def test_truncate_text_exact_limit_not_truncated():
    text = "a" * MAX_COMMENT_LENGTH
    result = truncate_text(text)
    assert len(result) == MAX_COMMENT_LENGTH
    assert "已截断" not in result


def test_truncate_text_long_text_truncated():
    text = "a" * (MAX_COMMENT_LENGTH + 1000)
    result = truncate_text(text)
    assert len(result) <= MAX_COMMENT_LENGTH
    assert "已截断" in result


def test_truncate_text_at_paragraph_boundary():
    paragraphs = ["段落" + str(i) + "\n\n" for i in range(100)]
    text = "".join(paragraphs) * 100
    result = truncate_text(text, max_length=1000)
    assert len(result) <= 1000
    assert "已截断" in result


def test_truncate_text_custom_max_length():
    text = "a" * 1000
    result = truncate_text(text, max_length=100)
    assert len(result) <= 100
    assert "已截断" in result


def test_truncate_text_preserves_encoding():
    text = "中文测试" * 5000
    result = truncate_text(text, max_length=1000)
    assert len(result) <= 1000
    assert isinstance(result, str)
