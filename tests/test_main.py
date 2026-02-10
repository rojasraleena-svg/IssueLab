"""测试 __main__ 模块功能"""

import os
from unittest.mock import patch


class TestMainTriggerComment:
    """测试 trigger comment 环境变量处理"""

    def test_execute_reads_trigger_comment_env(self, monkeypatch):
        """execute 命令应读取 ISSUELAB_TRIGGER_COMMENT"""
        from issuelab import __main__ as main_mod

        monkeypatch.setenv("ISSUELAB_TRIGGER_COMMENT", "@agent please focus on this")
        monkeypatch.setattr(
            main_mod, "get_issue_info", lambda *a, **k: {"title": "t", "body": "b", "comments": "", "comment_count": 0}
        )

        with patch("issuelab.tools.github.write_issue_context_file", lambda *a, **k: "/tmp/issue_1.md"):
            captured = {}

            async def _fake_run(issue, agents, context, comment_count, available_agents=None, trigger_comment=None):
                captured["trigger_comment"] = trigger_comment
                return {}

            monkeypatch.setattr("issuelab.commands.common.run_agents_parallel", _fake_run)
            monkeypatch.setattr(main_mod, "parse_agents_arg", lambda s: ["gqy20"])

            monkeypatch.setenv("PYTHONPATH", "src")
            monkeypatch.setattr(os, "environ", os.environ)
            monkeypatch.setattr("issuelab.commands.common.post_comment", lambda *a, **k: True)

            with patch("sys.argv", ["issuelab", "execute", "--issue", "1", "--agents", "gqy20"]):
                main_mod.main()

            assert captured.get("trigger_comment") == "@agent please focus on this"

    def test_execute_post_uses_guardrail_comment_for_failed_result(self, monkeypatch):
        """execute --post 遇到失败结果，默认不发布失败评论（避免刷屏）"""
        from issuelab import __main__ as main_mod

        monkeypatch.setattr(
            main_mod, "get_issue_info", lambda *a, **k: {"title": "t", "body": "b", "comments": "", "comment_count": 0}
        )
        monkeypatch.setattr(main_mod, "parse_agents_arg", lambda s: ["gqy20"])

        async def _fake_run(*args, **kwargs):
            return {
                "gqy20": {
                    "ok": False,
                    "error_type": "timeout",
                    "error_message": "deadline exceeded",
                    "failed_stage": "Researcher",
                    "response": "[系统护栏] timeout",
                    "cost_usd": 0.0,
                    "num_turns": 0,
                    "tool_calls": [],
                }
            }

        posted = {"called": False}

        def _fake_post(issue, body, agent_name=None, **kwargs):
            posted["called"] = True
            return True

        monkeypatch.setattr("issuelab.commands.common.run_agents_parallel", _fake_run)
        monkeypatch.setattr("issuelab.commands.common.post_comment", _fake_post)

        with (
            patch("issuelab.tools.github.write_issue_context_file", lambda *a, **k: "/tmp/issue_1.md"),
            patch("sys.argv", ["issuelab", "execute", "--issue", "1", "--agents", "gqy20", "--post"]),
        ):
            main_mod.main()

        assert posted["called"] is False

    def test_execute_post_can_publish_failure_summary_when_enabled(self, monkeypatch):
        """开启 ISSUELAB_POST_FAILURE_COMMENT 时应发布失败摘要"""
        from issuelab import __main__ as main_mod

        monkeypatch.setattr(
            main_mod, "get_issue_info", lambda *a, **k: {"title": "t", "body": "b", "comments": "", "comment_count": 0}
        )
        monkeypatch.setattr(main_mod, "parse_agents_arg", lambda s: ["gqy20"])
        monkeypatch.setenv("ISSUELAB_POST_FAILURE_COMMENT", "1")

        async def _fake_run(*args, **kwargs):
            return {
                "gqy20": {
                    "ok": False,
                    "error_type": "timeout",
                    "error_message": "deadline exceeded",
                    "failed_stage": "Researcher",
                    "response": "[系统护栏] timeout",
                    "cost_usd": 0.0,
                    "num_turns": 0,
                    "tool_calls": [],
                }
            }

        posted = {}

        def _fake_post(issue, body, agent_name=None, **kwargs):
            posted["body"] = body
            posted["agent_name"] = agent_name
            return True

        monkeypatch.setattr("issuelab.commands.common.run_agents_parallel", _fake_run)
        monkeypatch.setattr("issuelab.commands.common.post_comment", _fake_post)

        with (
            patch("issuelab.tools.github.write_issue_context_file", lambda *a, **k: "/tmp/issue_1.md"),
            patch("sys.argv", ["issuelab", "execute", "--issue", "1", "--agents", "gqy20", "--post"]),
        ):
            main_mod.main()

        assert posted["agent_name"] == "gqy20"
        assert "[系统护栏]" in posted["body"]
        assert "failed_stage: Researcher" in posted["body"]


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

        async def fake_run_observer_batch(issue_data_list, max_parallel=5):
            return []

        monkeypatch.setattr("issuelab.commands.observer.get_issue_info", fake_get_issue_info)
        from issuelab import tools as tools_pkg

        monkeypatch.setattr(tools_pkg.github, "write_issue_context_file", lambda *a, **k: f"/tmp/issue_{a[0]}.md")
        monkeypatch.setattr(
            __import__("issuelab.agents.observer").agents.observer,
            "run_observer_batch",
            fake_run_observer_batch,
        )

        with patch("sys.argv", ["issuelab", "observe-batch", "--issues", "1,2"]):
            main_mod.main()

        assert calls["count"] == 2
