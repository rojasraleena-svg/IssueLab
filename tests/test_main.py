"""测试 __main__ 模块功能"""

import os
from unittest.mock import MagicMock, patch

from issuelab.tools.github import MAX_COMMENT_LENGTH, truncate_text


class TestTruncateText:
    """测试文本截断功能"""

    def test_short_text_not_truncated(self):
        """短文本不应被截断"""
        text = "Short text"
        result = truncate_text(text)
        assert result == text
        assert "已截断" not in result

    def test_exact_limit_not_truncated(self):
        """刚好达到限制不截断"""
        text = "a" * MAX_COMMENT_LENGTH
        result = truncate_text(text)
        assert len(result) == MAX_COMMENT_LENGTH
        assert "已截断" not in result

    def test_long_text_truncated(self):
        """超长文本被截断"""
        text = "a" * (MAX_COMMENT_LENGTH + 1000)
        result = truncate_text(text)
        assert len(result) <= MAX_COMMENT_LENGTH
        assert "已截断" in result

    def test_truncate_at_paragraph(self):
        """在段落边界截断"""
        # 创建带多个段落的文本
        paragraphs = ["段落" + str(i) + "\n\n" for i in range(100)]
        text = "".join(paragraphs) * 100  # 确保超出限制

        result = truncate_text(text, max_length=1000)
        assert len(result) <= 1000
        assert "已截断" in result

    def test_custom_max_length(self):
        """自定义最大长度"""
        text = "a" * 1000
        result = truncate_text(text, max_length=100)
        assert len(result) <= 100
        assert "已截断" in result

    def test_truncate_preserves_encoding(self):
        """截断保持中文编码"""
        text = "中文测试" * 5000
        result = truncate_text(text, max_length=1000)
        assert len(result) <= 1000
        # 验证结果仍然是有效的字符串
        assert isinstance(result, str)


class TestMainTriggerComment:
    """测试 trigger comment 环境变量处理"""

    def test_execute_reads_trigger_comment_env(self, monkeypatch):
        """execute 命令应读取 ISSUELAB_TRIGGER_COMMENT"""
        from issuelab import __main__ as main_mod

        monkeypatch.setenv("ISSUELAB_TRIGGER_COMMENT", "@agent please focus on this")
        monkeypatch.setattr(main_mod, "get_issue_info", lambda *a, **k: {"title": "t", "body": "b", "comments": "", "comment_count": 0})

        with patch("issuelab.tools.github.write_issue_context_file", lambda *a, **k: "/tmp/issue_1.md"):
            captured = {}

            async def _fake_run(issue, agents, context, comment_count, available_agents=None, trigger_comment=None):
                captured["trigger_comment"] = trigger_comment
                return {}

            monkeypatch.setattr(main_mod, "run_agents_parallel", _fake_run)
            monkeypatch.setattr(main_mod, "parse_agents_arg", lambda s: ["gqy20"])

            monkeypatch.setenv("PYTHONPATH", "src")
            monkeypatch.setattr(os, "environ", os.environ)
            monkeypatch.setattr(main_mod, "post_comment", lambda *a, **k: True)

            with patch("sys.argv", ["issuelab", "execute", "--issue", "1", "--agents", "gqy20"]):
                main_mod.main()

            assert captured.get("trigger_comment") == "@agent please focus on this"


class TestObserveBatchUsesGetIssueInfo:
    """确保 observe-batch 使用 get_issue_info 而不是直接调用 gh"""

    def test_observe_batch_uses_get_issue_info(self, monkeypatch):
        from issuelab import __main__ as main_mod

        calls = {"count": 0}

        def fake_get_issue_info(issue_number, format_comments=False):
            calls["count"] += 1
            return {
                "title": f"title-{issue_number}",
                "body": f"body-{issue_number}",
                "comments": "comment-1",
                "comment_count": 1,
            }

        async def fake_run_observer_batch(issue_data_list):
            return []

        monkeypatch.setattr(main_mod, "get_issue_info", fake_get_issue_info)
        from issuelab import tools as tools_pkg

        monkeypatch.setattr(
            tools_pkg.github, "write_issue_context_file", lambda *a, **k: f"/tmp/issue_{a[0]}.md"
        )
        monkeypatch.setattr(
            main_mod.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("subprocess.run called"))
        )
        monkeypatch.setattr(
            __import__("issuelab.agents.observer").agents.observer,
            "run_observer_batch",
            fake_run_observer_batch,
        )

        with patch("sys.argv", ["issuelab", "observe-batch", "--issues", "1,2"]):
            main_mod.main()

        assert calls["count"] == 2
