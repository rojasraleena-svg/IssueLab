"""主入口：支持多种子命令"""
import asyncio
import argparse
import os
import subprocess
import tempfile
from issuelab.sdk_executor import run_agents_parallel, run_observer, get_agent_matrix_markdown, discover_agents
from issuelab.parser import parse_mentions

# 评论最大长度 (GitHub 限制 65536，实际使用 10000 留余量)
MAX_COMMENT_LENGTH = 10000


def truncate_text(text: str, max_length: int = MAX_COMMENT_LENGTH) -> str:
    """截断文本到指定长度，保留完整段落"""
    suffix = "\n\n_(内容已截断)_"
    suffix_len = len(suffix)

    if len(text) <= max_length:
        return text

    # 预留后缀空间，截断内容部分
    available = max_length - suffix_len
    truncated = text[:available]

    # 尝试在最后一个完整段落后截断
    last_newline = truncated.rfind('\n\n')

    if last_newline > available * 0.5:  # 保留至少 50% 的内容
        return truncated[:last_newline].strip() + suffix

    # 否则直接在字符边界截断
    return truncated.strip() + suffix


def post_comment(issue_number: int, body: str) -> bool:
    """发布评论到 Issue，自动截断过长内容"""
    # 截断内容
    truncated_body = truncate_text(body, MAX_COMMENT_LENGTH)

    # 使用临时文件避免命令行长度限制
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(truncated_body)
        f.flush()
        # 优先使用 GH_TOKEN，fallback 到 GITHUB_TOKEN
        env = os.environ.copy()
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            env["GH_TOKEN"] = token
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--body-file", f.name],
            capture_output=True,
            text=True,
            env=env
        )
        os.unlink(f.name)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Issue Lab Agent")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # @mention 并行执行
    execute_parser = subparsers.add_parser("execute", help="并行执行代理")
    execute_parser.add_argument("--issue", type=int, required=True)
    execute_parser.add_argument("--agents", type=str, required=True, help="空格分隔的代理名称")
    execute_parser.add_argument("--post", action="store_true", help="自动发布结果到 Issue")
    execute_parser.add_argument("--context", type=str, default="", help="Issue 内容上下文")
    execute_parser.add_argument("--title", type=str, default="", help="Issue 标题")
    execute_parser.add_argument("--comments", type=str, default="", help="Issue 所有评论内容")
    execute_parser.add_argument("--comment-count", type=int, default=0, help="评论数量")

    # 顺序评审流程
    review_parser = subparsers.add_parser("review", help="运行顺序评审流程")
    review_parser.add_argument("--issue", type=int, required=True)
    review_parser.add_argument("--post", action="store_true", help="自动发布结果到 Issue")
    review_parser.add_argument("--context", type=str, default="", help="Issue 内容上下文")
    review_parser.add_argument("--title", type=str, default="", help="Issue 标题")
    review_parser.add_argument("--comments", type=str, default="", help="Issue 所有评论内容")
    review_parser.add_argument("--comment-count", type=int, default=0, help="评论数量")

    # Observer 监控命令
    observe_parser = subparsers.add_parser("observe", help="运行 Observer Agent 分析 Issue")
    observe_parser.add_argument("--issue", type=int, required=True, help="Issue 编号")
    observe_parser.add_argument("--context", type=str, default="", help="Issue 内容上下文")
    observe_parser.add_argument("--title", type=str, default="", help="Issue 标题")
    observe_parser.add_argument("--comments", type=str, default="", help="Issue 所有评论内容")
    observe_parser.add_argument("--comment-count", type=int, default=0, help="评论数量")
    observe_parser.add_argument("--post", action="store_true", help="自动发布触发评论到 Issue")

    # 列出所有可用 Agent
    list_parser = subparsers.add_parser("list-agents", help="列出所有可用的 Agent")

    args = parser.parse_args()

    # 根据命令类型处理
    if args.command == "execute" or args.command == "review" or args.command == "observe":
        # 构建上下文
        context = ""
        if getattr(args, "context", ""):
            title = getattr(args, "title", "") or ""
            context = f"**Issue 标题**: {title}\n\n**Issue 内容**:\n{args.context}"

        # 如果有评论，添加到上下文
        comment_count = getattr(args, "comment_count", 0) or 0
        comments = getattr(args, "comments", "") or ""
        if comment_count > 0 and comments:
            context += f"\n\n**本 Issue 共有 {comment_count} 条历史评论，请仔细阅读并分析：**\n\n{comments}"
    else:
        context = ""
        comment_count = 0
        comments = ""

    if args.command == "execute":
        agents = args.agents.split()
        results = asyncio.run(run_agents_parallel(args.issue, agents, context, comment_count))

        # 输出结果
        for agent_name, response in results.items():
            print(f"\n=== {agent_name} result ===")
            print(response)

            # 如果需要，自动发布到 Issue
            if getattr(args, "post", False):
                if post_comment(args.issue, response):
                    print(f"✅ {agent_name} response posted to issue #{args.issue}")
                else:
                    print(f"❌ Failed to post {agent_name} response")

    elif args.command == "review":
        # 顺序执行：moderator -> reviewer_a -> reviewer_b -> summarizer
        agents = ["moderator", "reviewer_a", "reviewer_b", "summarizer"]
        results = asyncio.run(run_agents_parallel(args.issue, agents, context, comment_count))

        for agent_name, response in results.items():
            print(f"\n=== {agent_name} result ===")
            print(response)

            # 如果需要，自动发布到 Issue
            if getattr(args, "post", False):
                if post_comment(args.issue, response):
                    print(f"✅ {agent_name} response posted to issue #{args.issue}")
                else:
                    print(f"❌ Failed to post {agent_name} response")

    elif args.command == "observe":
        # 运行 Observer Agent 分析 Issue
        result = asyncio.run(run_observer(
            args.issue,
            getattr(args, "title", "") or "",
            args.context or "",
            comments or ""
        ))

        print(f"\n=== Observer Analysis for Issue #{args.issue} ===")
        print(f"\nAnalysis:\n{result.get('analysis', 'N/A')}")
        print(f"\nShould Trigger: {result.get('should_trigger', False)}")
        if result.get('should_trigger'):
            print(f"Agent: {result.get('agent', 'N/A')}")
            print(f"Trigger Comment: {result.get('comment', 'N/A')}")
            print(f"Reason: {result.get('reason', 'N/A')}")

            # 如果需要，自动发布触发评论
            if getattr(args, "post", False):
                if result.get('comment') and post_comment(args.issue, result['comment']):
                    print(f"\n✅ Trigger comment posted to issue #{args.issue}")
                else:
                    print(f"\n❌ Failed to post trigger comment")
        else:
            print(f"Skip Reason: {result.get('reason', 'N/A')}")

    elif args.command == "list-agents":
        # 列出所有可用的 Agent
        agents = discover_agents()
        print("\n=== Available Agents ===\n")
        print(f"{'Agent':<15} {'Description':<50} {'Trigger Conditions'}")
        print("-" * 100)
        for name, config in agents.items():
            conditions = config.get('trigger_conditions', [])
            if conditions and all(isinstance(c, str) for c in conditions):
                conditions_str = ", ".join(conditions)
            else:
                conditions_str = "auto-detect"
            desc = config.get('description', '')[:48]
            print(f"{name:<15} {desc:<50} {conditions_str[:40]}")

        print("\n\n=== Agent Matrix (for Observer) ===\n")
        print(get_agent_matrix_markdown())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
