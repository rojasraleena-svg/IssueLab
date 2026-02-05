"""
Agent Response 后处理：解析 @mentions 并触发 dispatch

解决bot评论无法触发workflow的问题：
- agent执行完成后主动解析response中的@mentions
- 自动触发被@的用户agent
"""

import logging
import os
import subprocess
from typing import Any, Literal, overload

from issuelab.mention_policy import (
    build_mention_section,
    clean_mentions_in_text,
    extract_mentions,
    filter_mentions,
)

logger = logging.getLogger(__name__)


@overload
def trigger_mentioned_agents(
    response: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    policy: dict | None = None,
    *,
    return_details: Literal[False] = False,
) -> dict[str, bool]: ...


@overload
def trigger_mentioned_agents(
    response: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    policy: dict | None = None,
    *,
    return_details: Literal[True],
) -> tuple[dict[str, bool], list[str], list[str]]: ...


def trigger_mentioned_agents(
    response: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    policy: dict | None = None,
    *,
    return_details: bool = False,
) -> dict[str, bool] | tuple[dict[str, bool], list[str], list[str]]:
    """
    解析agent response中的@mentions，应用策略过滤，并触发允许的agent

    Args:
        response: Agent的response内容
        issue_number: Issue编号
        issue_title: Issue标题
        issue_body: Issue内容
        policy: @ 策略配置（None 则自动加载）

    Returns:
        默认返回触发结果字典 {username: success}，以保持向后兼容。
        当 return_details=True 时返回 (results, allowed_mentions, filtered_mentions) 元组。
    """
    mentions = extract_mentions(response)

    if not mentions:
        logger.info("[INFO] Response中没有@mentions")
        return ({}, [], []) if return_details else {}

    logger.info(f"[INFO] 发现 {len(mentions)} 个@mentions: {mentions}")

    # 应用策略过滤
    allowed_mentions, filtered_mentions = filter_mentions(mentions, policy)

    if filtered_mentions:
        logger.info(f"[FILTER] 过滤了 {len(filtered_mentions)} 个@mentions: {filtered_mentions}")

    if not allowed_mentions:
        logger.info("[INFO] 没有允许的@mentions")
        return ({}, [], filtered_mentions) if return_details else {}

    logger.info(f"[INFO] 允许触发 {len(allowed_mentions)} 个@mentions: {allowed_mentions}")

    from issuelab.observer_trigger import auto_trigger_agent

    results = {}
    for username in allowed_mentions:
        logger.info(f"[INFO] 触发被@的agent: {username}")
        success = auto_trigger_agent(
            agent_name=username,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
        )
        results[username] = success

        if success:
            logger.info(f"[OK] 成功触发 {username}")
        else:
            logger.error(f"[ERROR] 触发 {username} 失败")

    return (results, allowed_mentions, filtered_mentions) if return_details else results


def process_agent_response(
    agent_name: str,
    response: str | dict[str, Any],
    issue_number: int,
    issue_title: str = "",
    issue_body: str = "",
    auto_dispatch: bool = True,
) -> dict[str, Any]:
    """
    处理agent response的后处理逻辑

    新增功能：
    1. 清理主体内容中的所有 @mentions（替换为"用户 xxx"）
    2. 应用策略过滤，区分允许和被过滤的 mentions
    3. 触发允许的 agents
    4. 返回清理后的主体内容和 mentions 信息

    Args:
        agent_name: Agent名称
        response: Agent的response（字符串或dict）
        issue_number: Issue编号
        issue_title: Issue标题
        issue_body: Issue内容
        auto_dispatch: 是否自动触发@mentions

    Returns:
        处理结果 {
            "agent_name": str,
            "response": str,  # 原始回复
            "clean_response": str,  # 清理后的回复（所有 @ 替换为"用户 xxx"）
            "mentions": list[str],  # 所有提取的 mentions
            "allowed_mentions": list[str],  # 允许的 mentions
            "filtered_mentions": list[str],  # 被过滤的 mentions
            "dispatch_results": dict[str, bool]  # 触发结果
        }
    """
    # 提取response文本
    response_text = response.get("response", str(response)) if isinstance(response, dict) else str(response)

    # 提取所有 @mentions
    mentions = extract_mentions(response_text)

    # 清理主体内容（将所有 @username 替换为 "用户 username"）
    clean_response = clean_mentions_in_text(response_text)

    result = {
        "agent_name": agent_name,
        "response": response_text,
        "clean_response": clean_response,
        "mentions": mentions,
        "allowed_mentions": [],
        "filtered_mentions": [],
        "dispatch_results": {},
    }

    # 自动触发被@的agents
    if auto_dispatch and mentions:
        logger.info(f"🔗 {agent_name} 的response中@了 {len(mentions)} 个用户")
        trigger_result = trigger_mentioned_agents(
            response_text, issue_number, issue_title, issue_body, return_details=True
        )

        if isinstance(trigger_result, tuple) and len(trigger_result) == 3:
            dispatch_results, allowed_mentions, filtered_mentions = trigger_result
        else:
            dispatch_results = trigger_result
            allowed_mentions = list(dispatch_results.keys())
            filtered_mentions = []
        result["dispatch_results"] = dispatch_results
        result["allowed_mentions"] = allowed_mentions
        result["filtered_mentions"] = filtered_mentions

    return result


def should_auto_close(response_text: str, agent_name: str) -> bool:
    """
    检查是否应该自动关闭Issue

    规则：
    - 仅限 summarizer 可触发自动关闭
    - 响应中必须包含 [CLOSE] 标记

    Args:
        response_text: Agent的response内容
        agent_name: Agent名称

    Returns:
        是否应该关闭
    """
    if agent_name != "summarizer":
        return False

    if not response_text:
        return False

    # 检测 [CLOSE] 标记
    return "[CLOSE]" in response_text


def close_issue(issue_number: int) -> bool:
    """
    关闭 Issue

    Args:
        issue_number: Issue编号

    Returns:
        是否成功关闭
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "close",
                str(issue_number),
                "--repo",
                os.environ.get("GITHUB_REPOSITORY", ""),
                "--reason",
                "completed",
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        if result.returncode == 0:
            logger.info(f"[OK] Issue #{issue_number} 已自动关闭")
            return True
        else:
            logger.error(f"[ERROR] 关闭 Issue #{issue_number} 失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[ERROR] 关闭 Issue #{issue_number} 异常: {e}")
        return False
