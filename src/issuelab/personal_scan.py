"""
个人Agent扫描模块

用于fork仓库的用户，让他们的个人agent分析主仓库的issues，
选择感兴趣的话题进行参与
"""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_issue_content(issue_number: int, repo: str) -> dict[str, Any] | None:
    """
    获取issue内容（从主仓库）

    Args:
        issue_number: Issue编号
        repo: 仓库名称 (owner/repo)

    Returns:
        Issue数据或None
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "title,body,labels,comments"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"[ERROR] 获取Issue #{issue_number}失败: {e}")
        return None


def check_already_commented(issue_number: int, repo: str, username: str) -> bool:
    """
    检查用户是否已经评论过这个issue

    Args:
        issue_number: Issue编号
        repo: 仓库名称
        username: 用户名

    Returns:
        True: 已评论, False: 未评论
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"/repos/{repo}/issues/{issue_number}/comments", "--jq", f".[] | select(.user.login==\"{username}\") | .id"],
            capture_output=True,
            text=True,
            check=True,
        )
        # 如果有输出，说明已经评论过
        return bool(result.stdout.strip())
    except Exception as e:
        logger.warning(f"[WARNING] 检查评论状态失败: {e}")
        return False  # 默认未评论


def analyze_issue_interest(
    agent_name: str, issue_number: int, issue_title: str, issue_body: str, agent_config: dict[str, Any]
) -> dict[str, Any]:
    """
    让agent分析是否对这个issue感兴趣

    Args:
        agent_name: Agent名称
        issue_number: Issue编号
        issue_title: Issue标题
        issue_body: Issue内容
        agent_config: Agent配置

    Returns:
        {
            "interested": bool,
            "reason": str,
            "priority": int (1-10)
        }
    """
    # 获取agent的兴趣关键词
    interests = agent_config.get("interests", [])
    if isinstance(interests, str):
        interests = [interests]

    # 简单的关键词匹配（可以后续升级为LLM判断）
    text = f"{issue_title}\n{issue_body}".lower()

    interest_score = 0
    matched_keywords = []

    for keyword in interests:
        if keyword.lower() in text:
            interest_score += 1
            matched_keywords.append(keyword)

    # 判断是否感兴趣
    interested = interest_score > 0

    reason = ""
    if interested:
        reason = f"匹配到关键词: {', '.join(matched_keywords)}"
    else:
        reason = "未匹配到感兴趣的关键词"

    return {"interested": interested, "reason": reason, "priority": min(interest_score, 10)}


def select_top_issues(
    candidates: list[dict[str, Any]], max_count: int = 3
) -> list[dict[str, Any]]:
    """
    从候选issues中选择top N个

    Args:
        candidates: 候选issue列表
        max_count: 最大数量

    Returns:
        选中的issues
    """
    # 按priority排序
    sorted_candidates = sorted(candidates, key=lambda x: x.get("priority", 0), reverse=True)

    # 只选择interested=True的
    interested = [c for c in sorted_candidates if c.get("interested", False)]

    # 限制数量
    return interested[:max_count]


def scan_issues_for_personal_agent(
    agent_name: str,
    agent_config: dict[str, Any],
    issue_numbers: list[int],
    repo: str,
    max_replies: int = 3,
    username: str = "",
) -> dict[str, Any]:
    """
    使用个人agent扫描issues

    Args:
        agent_name: Agent名称
        agent_config: Agent配置
        issue_numbers: 候选issue编号列表
        repo: 主仓库名称
        max_replies: 最多回复数量
        username: 用户名（用于检查是否已评论）

    Returns:
        {
            "agent_name": str,
            "total_scanned": int,
            "candidates": list[dict],
            "selected_issues": list[int]
        }
    """
    logger.info(f"🔍 开始扫描 {len(issue_numbers)} 个issues...")

    candidates = []

    for issue_num in issue_numbers:
        # 获取issue内容
        issue_data = get_issue_content(issue_num, repo)
        if not issue_data:
            continue

        # 检查是否已经评论过
        if username and check_already_commented(issue_num, repo, username):
            logger.info(f"[SKIP] Issue #{issue_num} 已评论过，跳过")
            continue

        # 分析兴趣度
        analysis = analyze_issue_interest(
            agent_name=agent_name,
            issue_number=issue_num,
            issue_title=issue_data.get("title", ""),
            issue_body=issue_data.get("body", ""),
            agent_config=agent_config,
        )

        candidates.append(
            {
                "issue_number": issue_num,
                "title": issue_data.get("title", ""),
                "interested": analysis["interested"],
                "reason": analysis["reason"],
                "priority": analysis["priority"],
            }
        )

        if analysis["interested"]:
            logger.info(
                f"[OK] Issue #{issue_num}: {issue_data.get('title', '')} (优先级: {analysis['priority']})"
            )
        else:
            logger.info(f"[SKIP] Issue #{issue_num}: 不感兴趣 - {analysis['reason']}")

    # 选择top N
    selected = select_top_issues(candidates, max_replies)
    selected_numbers = [s["issue_number"] for s in selected]

    logger.info(f"[INFO] 总扫描: {len(candidates)}, 感兴趣: {len(selected)}")

    return {
        "agent_name": agent_name,
        "total_scanned": len(candidates),
        "candidates": candidates,
        "selected_issues": selected_numbers,
        "selected_details": selected,
    }
