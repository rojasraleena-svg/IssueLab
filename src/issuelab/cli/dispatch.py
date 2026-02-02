"""
向用户 fork 仓库分发 repository_dispatch 事件

读取注册信息，向匹配的用户仓库发送 repository_dispatch 事件。
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any

import jwt
import requests
import yaml


def load_registry(registry_dir: Path) -> dict[str, dict[str, Any]]:
    """
    加载所有注册文件

    Args:
        registry_dir: 注册目录路径

    Returns:
        用户名 -> 注册信息的字典
    """
    registry = {}

    if not registry_dir.exists():
        print(f"Warning: Registry directory not found: {registry_dir}", file=sys.stderr)
        return registry

    for yml_file in registry_dir.glob("*.yml"):
        if yml_file.name == "README.md":
            continue

        try:
            with open(yml_file) as f:
                config = yaml.safe_load(f)

            if not config:
                print(f"Warning: Empty config in {yml_file.name}", file=sys.stderr)
                continue

            username = config.get("username")
            if not username:
                print(f"Warning: {yml_file.name} missing username", file=sys.stderr)
                continue

            # 检查是否启用
            if not config.get("enabled", True):
                print(f"Info: {username} is disabled", file=sys.stderr)
                continue

            registry[username] = config

        except yaml.YAMLError as e:
            print(f"Error parsing {yml_file.name}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error loading {yml_file.name}: {e}", file=sys.stderr)
            continue

    return registry


def match_triggers(mentions: list[str], registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """
    匹配 mentions 到注册的用户

    Args:
        mentions: @mention 列表（不含 @）
        registry: 用户注册信息

    Returns:
        匹配的用户配置列表
    """
    matched = []
    matched_users = set()

    for mention in mentions:
        # 直接匹配用户名
        if mention in registry:
            config = registry[mention]
            triggers = config.get("triggers", [])

            # 检查是否在触发列表中
            if f"@{mention}" in triggers and mention not in matched_users:
                matched.append(config)
                matched_users.add(mention)
                continue

        # 检查所有用户的触发条件
        for username, config in registry.items():
            if username in matched_users:
                continue

            triggers = config.get("triggers", [])
            if f"@{mention}" in triggers:
                matched.append(config)
                matched_users.add(username)
                break

    return matched


def retry_on_failure(max_attempts: int = 3, delay: float = 2, backoff: float = 2):
    """
    重试装饰器，用于网络请求失败时自动重试

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍增系数
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        # 最后一次尝试也失败了
                        raise

                    print(
                        f"⚠️ Attempt {attempt + 1}/{max_attempts} failed: {e}",
                        file=sys.stderr,
                    )
                    print(f"   Retrying in {current_delay:.1f}s...", file=sys.stderr)
                    time.sleep(current_delay)
                    current_delay *= backoff

            # 如果所有尝试都失败了
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def generate_github_app_jwt(app_id: str, private_key: str) -> str:
    """
    生成 GitHub App JWT token

    Args:
        app_id: GitHub App ID
        private_key: GitHub App Private Key (PEM format)

    Returns:
        JWT token string
    """
    now = datetime.now(UTC)
    payload = {
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "iss": app_id,
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_id(owner: str, repo: str, app_jwt: str) -> int | None:
    """
    获取指定仓库的 Installation ID

    Args:
        owner: 仓库 owner
        repo: 仓库名称
        app_jwt: GitHub App JWT token

    Returns:
        Installation ID，如果未找到则返回 None
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/installation"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("id")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            print(f"⚠️ No installation found for {owner}/{repo}", file=sys.stderr)
        else:
            print(f"⚠️ Failed to get installation: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"⚠️ Error getting installation: {e}", file=sys.stderr)
        return None


def generate_installation_token(installation_id: int, app_jwt: str) -> str | None:
    """
    为指定 Installation 生成 Access Token

    Args:
        installation_id: Installation ID
        app_jwt: GitHub App JWT token

    Returns:
        Installation Access Token，失败返回 None
    """
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("token")
    except Exception as e:
        print(f"⚠️ Failed to generate installation token: {e}", file=sys.stderr)
        return None


def get_token_for_repository(repository: str, app_id: str, private_key: str) -> str | None:
    """
    为指定仓库获取 GitHub App Installation Token

    Args:
        repository: 仓库全名 (owner/repo)
        app_id: GitHub App ID
        private_key: GitHub App Private Key

    Returns:
        Installation Access Token，失败返回 None
    """
    owner, repo = repository.split("/")

    # 1. 生成 App JWT
    app_jwt = generate_github_app_jwt(app_id, private_key)

    # 2. 获取 Installation ID
    installation_id = get_installation_id(owner, repo, app_jwt)
    if not installation_id:
        return None

    # 3. 生成 Installation Token
    return generate_installation_token(installation_id, app_jwt)


@retry_on_failure(max_attempts=3, delay=2)
def dispatch_event(
    repository: str, event_type: str, client_payload: dict[str, Any], token: str, timeout: int = 10
) -> tuple[bool, str]:
    """
    发送 repository_dispatch 事件

    Args:
        repository: 目标仓库（owner/repo）
        event_type: 事件类型
        client_payload: 事件数据
        token: GitHub Token
        timeout: 超时时间（秒）

    Returns:
        (是否成功, 错误代码)
    """
    url = f"https://api.github.com/repos/{repository}/dispatches"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    data = {"event_type": event_type, "client_payload": client_payload}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
        response.raise_for_status()
        print(f"✓ Dispatched to {repository} (repository_dispatch)")
        return True, ""

    except requests.exceptions.HTTPError as e:
        status_code = response.status_code
        error_msg = response.text if response.text else str(e)

        # 403 错误特殊处理（fork 仓库限制）
        if status_code == 403:
            print(f"✗ 403 Forbidden: Cannot dispatch to {repository}", file=sys.stderr)
            if "fork" in repository.lower() or "personal access token" in error_msg.lower():
                print("  💡 Suggestion: This may be a fork repository.", file=sys.stderr)
                print(f"     Ask {repository.split('/')[0]} to configure workflow_dispatch mode.", file=sys.stderr)
            return False, "FORK_DISPATCH_NOT_ALLOWED"

        # 404 错误（仓库不存在或 workflow 未启用）
        elif status_code == 404:
            print(f"✗ 404 Not Found: {repository}", file=sys.stderr)
            print("  Repository not found or workflow not enabled", file=sys.stderr)
            return False, "REPOSITORY_NOT_FOUND"

        # 其他 HTTP 错误
        else:
            print(f"✗ HTTP {status_code} error: {error_msg}", file=sys.stderr)
            return False, f"HTTP_{status_code}"

    except requests.exceptions.Timeout:
        print(f"✗ Timeout dispatching to {repository}", file=sys.stderr)
        return False, "TIMEOUT"
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to dispatch to {repository}: {e}", file=sys.stderr)
        return False, "UNKNOWN_ERROR"


@retry_on_failure(max_attempts=3, delay=2)
def dispatch_workflow(
    repository: str, workflow_file: str, ref: str, inputs: dict[str, Any], token: str, timeout: int = 10
) -> tuple[bool, str]:
    """
    发送 workflow_dispatch 事件（推荐用于 fork 仓库）

    Args:
        repository: 目标仓库（owner/repo）
        workflow_file: workflow 文件名（如 "user_agent.yml"）
        ref: 分支名
        inputs: workflow 输入参数
        token: GitHub Token
        timeout: 超时时间（秒）

    Returns:
        (是否成功, 错误代码)
    """
    url = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow_file}/dispatches"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # workflow_dispatch 需要 ref 和 inputs
    # 所有 inputs 必须是字符串类型
    data = {
        "ref": ref,
        "inputs": {
            "source_repo": str(inputs.get("source_repo", "")),
            "issue_number": str(inputs.get("issue_number", "")),
            "issue_title": str(inputs.get("issue_title", "")),
            "issue_body": str(inputs.get("issue_body", "")),
            "comment_id": str(inputs.get("comment_id", "")) if inputs.get("comment_id") else "",
            "comment_body": str(inputs.get("comment_body", "")),
            "labels": json.dumps(inputs.get("labels", [])),
            "target_username": str(inputs.get("target_username", "")),
        },
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
        response.raise_for_status()
        print(f"✓ Dispatched workflow to {repository} (workflow_dispatch)")
        return True, ""

    except requests.exceptions.HTTPError as e:
        status_code = response.status_code
        error_msg = response.text if response.text else str(e)

        # 404 错误（workflow 文件不存在或未配置 workflow_dispatch）
        if status_code == 404:
            print(f"✗ 404 Not Found: {repository}/actions/workflows/{workflow_file}", file=sys.stderr)
            print("  Workflow file may not exist or workflow_dispatch not configured", file=sys.stderr)
            return False, "WORKFLOW_NOT_FOUND"

        # 403 错误（权限不足）
        elif status_code == 403:
            print(f"✗ 403 Forbidden: Cannot trigger workflow in {repository}", file=sys.stderr)
            print("  Token may lack 'workflow' permission", file=sys.stderr)
            return False, "WORKFLOW_PERMISSION_DENIED"

        # 其他 HTTP 错误
        else:
            print(f"✗ HTTP {status_code} error: {error_msg}", file=sys.stderr)
            return False, f"HTTP_{status_code}"

    except requests.exceptions.Timeout:
        print(f"✗ Timeout dispatching workflow to {repository}", file=sys.stderr)
        return False, "TIMEOUT"
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to dispatch workflow to {repository}: {e}", file=sys.stderr)
        return False, "UNKNOWN_ERROR"


def write_github_output(dispatched: int, total: int) -> None:
    """
    写入 GitHub Actions 输出变量

    Args:
        dispatched: 成功分发的数量
        total: 总匹配数量
    """
    if "GITHUB_OUTPUT" not in os.environ:
        return

    try:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"dispatched_count={dispatched}\n")
            f.write(f"total_count={total}\n")
    except OSError as e:
        print(f"Warning: Failed to write GitHub output: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """
    CLI 入口点

    Args:
        argv: 命令行参数，None 则使用 sys.argv

    Returns:
        退出码，0 表示成功
    """
    parser = argparse.ArgumentParser(description="Dispatch events to user repositories")
    parser.add_argument("--mentions", required=True, help="Mentions list (JSON array or comma-separated)")
    parser.add_argument(
        "--registry-dir", default="agents/_registry", help="Registry directory (default: agents/_registry)"
    )
    parser.add_argument("--source-repo", required=True, help="Source repository (owner/repo)")
    parser.add_argument("--issue-number", required=True, type=int, help="Issue number")
    parser.add_argument("--issue-title", help="Issue title")
    parser.add_argument("--issue-body", help="Issue body")
    parser.add_argument("--comment-id", type=int, help="Comment ID (if triggered by comment)")
    parser.add_argument("--comment-body", help="Comment body")
    parser.add_argument("--labels", help="Issue labels (JSON array)")
    parser.add_argument("--event-type", default="issue_mention", help="Dispatch event type (default: issue_mention)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - validate configuration without actually dispatching",
    )
    parser.add_argument("--use-github-app", action="store_true", help="Use GitHub App authentication")
    parser.add_argument("--app-id", help="GitHub App ID (required if --use-github-app)")
    parser.add_argument("--app-private-key", help="GitHub App Private Key (required if --use-github-app)")

    args = parser.parse_args(argv)

    # 检查认证方式
    use_github_app = args.use_github_app or os.environ.get("GITHUB_APP_AUTH") == "true"

    if use_github_app:
        # GitHub App 认证模式
        app_id = args.app_id or os.environ.get("GITHUB_APP_ID")
        app_private_key = args.app_private_key or os.environ.get("GITHUB_APP_PRIVATE_KEY")

        if not app_id or not app_private_key:
            print("Error: GitHub App authentication requires GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY", file=sys.stderr)
            return 1

        print("🔑 Using GitHub App authentication")
        github_app_credentials = (app_id, app_private_key)
        default_token = None
    else:
        # Token 认证模式（向后兼容）
        default_token = os.environ.get("GITHUB_TOKEN")
        if not default_token:
            print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
            return 1
        github_app_credentials = None

    # 解析 mentions（支持 JSON 和 CSV 格式）
    mentions_str = args.mentions.strip()
    if mentions_str.startswith("[") and mentions_str.endswith("]"):
        # JSON 数组格式
        try:
            mentions = json.loads(mentions_str)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in mentions: {args.mentions}", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            return 1
    else:
        # CSV 格式（逗号分隔）
        mentions = [m.strip() for m in mentions_str.split(",") if m.strip()]

    if not mentions:
        print("Info: No mentions found, nothing to dispatch")
        return 0

    print(f"Found mentions: {', '.join(mentions)}")

    # 加载注册信息
    registry_dir = Path(args.registry_dir)
    registry = load_registry(registry_dir)
    print(f"Loaded {len(registry)} registered agents")

    if not registry:
        print("Warning: No agents registered")
        return 0

    # 匹配用户
    matched_configs = match_triggers(mentions, registry)

    if not matched_configs:
        print("Info: No matching agents found")
        return 0

    print(f"Matched {len(matched_configs)} agents")

    # 构建 client_payload
    client_payload = {
        "source_repo": args.source_repo,
        "issue_number": args.issue_number,
        "issue_title": args.issue_title,
        "issue_body": args.issue_body,
    }

    if args.comment_id:
        client_payload["comment_id"] = args.comment_id
        client_payload["comment_body"] = args.comment_body

    if args.labels:
        try:
            client_payload["labels"] = json.loads(args.labels)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in labels: {args.labels}", file=sys.stderr)

    # 分发事件
    success_count = 0
    failed_agents = []

    for config in matched_configs:
        repository = config.get("repository")
        branch = config.get("branch", "main")
        username = config.get("username")
        dispatch_mode = config.get("dispatch_mode", "repository_dispatch")
        workflow_file = config.get("workflow_file", "user_agent.yml")

        if not repository:
            print(f"⚠️ {username} has no repository configured", file=sys.stderr)
            failed_agents.append({"username": username, "reason": "No repository configured"})
            continue

        # 添加用户特定信息
        payload = client_payload.copy()
        payload["target_username"] = username
        payload["target_branch"] = branch

        # Dry-run 模式
        if args.dry_run:
            print(f"[DRY RUN] Would dispatch to {repository}")
            print(f"  Mode: {dispatch_mode}")
            print(f"  Branch: {branch}")
            if dispatch_mode == "workflow_dispatch":
                print(f"  Workflow file: {workflow_file}")
            print(f"  Payload keys: {', '.join(payload.keys())}")
            success_count += 1
            continue

        # 根据模式选择 dispatch 方式
        success = False
        error_code = ""

        # 获取目标仓库的 token
        if github_app_credentials:
            # GitHub App 模式：为每个目标仓库动态生成 token
            app_id, private_key = github_app_credentials
            token = get_token_for_repository(repository, app_id, private_key)
            if not token:
                print(f"⚠️ Failed to get token for {repository}", file=sys.stderr)
                failed_agents.append(
                    {"username": username, "repository": repository, "error": "TOKEN_GENERATION_FAILED"}
                )
                continue
        else:
            # 传统 token 模式
            token = default_token

        if dispatch_mode == "workflow_dispatch":
            # 使用 workflow_dispatch（推荐用于 fork 仓库）
            success, error_code = dispatch_workflow(repository, workflow_file, branch, payload, token)
        else:
            # 使用 repository_dispatch（默认，用于非 fork 仓库）
            success, error_code = dispatch_event(repository, args.event_type, payload, token)

        if success:
            success_count += 1
        else:
            failed_agents.append({"username": username, "repository": repository, "error": error_code})

    # 输出详细结果
    print(f"\n{'=' * 60}")
    print(f"✅ Successfully dispatched to {success_count}/{len(matched_configs)} agents")

    if failed_agents:
        print(f"❌ Failed agents ({len(failed_agents)}):")
        for agent in failed_agents:
            username = agent["username"]
            error = agent.get("error", agent.get("reason", "Unknown"))
            print(f"   - {username}: {error}")

    print(f"{'=' * 60}")

    # 写入 GitHub Actions 输出
    write_github_output(success_count, len(matched_configs))

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
