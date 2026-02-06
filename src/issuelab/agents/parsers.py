"""响应解析工具

解析 Agent 响应（YAML 格式）。
"""

import re

from issuelab.logging_config import get_logger

logger = get_logger(__name__)


def parse_observer_response(response: str, issue_number: int | None = None) -> dict[str, object]:
    """解析 Observer Agent 的响应

    Args:
        response: Agent 响应文本（YAML 格式）
        issue_number: Issue 编号（可选，用于日志记录）

    Returns:
        解析后的决策结果 {
            "should_trigger": bool,
            "agent": str,
            "comment": str,
            "reason": str,
            "analysis": str,
        }
    """
    # 如果提供了 issue_number，记录日志
    if issue_number is not None:
        logger.debug(f"解析 Issue #{issue_number} 的 Observer 响应")

    result = {
        "should_trigger": False,
        "agent": "",
        "comment": "",
        "reason": "",
        "analysis": "",
    }

    yaml_data = _try_parse_yaml(response)
    if yaml_data is None:
        return result

    result["should_trigger"] = yaml_data.get("should_trigger", False)
    result["agent"] = yaml_data.get("agent", "") or yaml_data.get("trigger_agent", "")
    result["comment"] = yaml_data.get("comment", "") or yaml_data.get("trigger_comment", "")
    result["reason"] = yaml_data.get("reason", "") or yaml_data.get("skip_reason", "")
    result["analysis"] = yaml_data.get("analysis", "")

    # 如果没有解析到触发评论，使用默认格式
    agent_name = str(result["agent"]) if result["agent"] is not None else ""
    if result["should_trigger"] and agent_name and not result["comment"]:
        result["comment"] = _get_default_trigger_comment(agent_name)
        result["agent"] = agent_name

    return result


def _try_parse_yaml(response: str) -> dict | None:
    """尝试解析 YAML 格式的响应

    Args:
        response: Agent 响应文本

    Returns:
        解析后的字典，失败返回 None
    """
    import yaml

    # 清理响应文本
    text = response.strip()

    # 检查是否包含 YAML 代码块标记
    if "```yaml" in text:
        # 提取 ```yaml 和 ``` 之间的内容
        start = text.find("```yaml")
        if start == -1:
            start = text.find("```")
        end = text.rfind("```")
        if start != -1 and end != -1 and end > start:
            # 找到代码块内容（跳过 ```yaml 行和 ``` 行）
            lines = text[start:end].split("\n")
            if len(lines) >= 2:
                yaml_content = "\n".join(lines[1:])
                try:
                    return yaml.safe_load(yaml_content)
                except yaml.YAMLError:
                    pass
    elif text.startswith("---"):
        # 可能直接是 YAML 文档
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            pass

    # 检查是否是简单的键值对格式（每行一个）
    lines = text.split("\n")
    yaml_like = True
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            yaml_like = False
            break

    if yaml_like:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            pass

    return None


def parse_papers_recommendation(response: str, paper_count: int) -> list[dict[str, object]]:
    """解析 Observer 对论文推荐的响应

    Args:
        response: Agent 响应文本（YAML 格式）
        paper_count: 原始论文数量（用于验证 index）

    Returns:
        推荐论文列表 [{
            "index": int,
            "title": str,
            "reason": str,
            "summary": str,
            "category": str,
            "url": str,
            "pdf_url": str,
            "authors": str,
            "published": str,
        }]
    """
    structured = _parse_structured_recommendations(response, paper_count)
    if structured:
        logger.info(f"解析到 {len(structured)} 篇推荐论文")
        return structured

    fallback = _parse_fallback_recommendations(response, paper_count)
    if fallback:
        logger.info(f"使用后备解析得到 {len(fallback)} 篇推荐论文")
        return fallback

    logger.warning("响应中未找到可解析的推荐论文")
    return []


def _extract_paper_indices(text: str) -> list[int]:
    """从文本中提取论文索引（例如：论文0 / paper 2）。"""
    if not text:
        return []
    pattern = re.compile(r"(?:论文|paper)\s*#?\s*(\d+)", re.IGNORECASE)
    matches = pattern.findall(text)
    indices: list[int] = []
    for match in matches:
        try:
            idx = int(match)
        except ValueError:
            continue
        if idx not in indices:
            indices.append(idx)
    return indices


def _parse_structured_recommendations(response: str, paper_count: int) -> list[dict[str, object]]:
    """优先解析结构化 YAML recommended / recommendations。"""
    recommended: list[dict[str, object]] = []

    yaml_data = _try_parse_yaml(response)
    if yaml_data is None:
        logger.warning("无法解析论文推荐结果")
        return recommended

    rec_list = yaml_data.get("recommended", [])
    if not rec_list:
        rec_list = yaml_data.get("recommendations", [])

    if not rec_list:
        logger.warning("响应中未找到 recommended / recommendations 字段")
        return recommended

    for item in rec_list:
        if not isinstance(item, dict):
            if isinstance(item, str):
                indices = _extract_paper_indices(item)
                for idx in indices:
                    if 0 <= idx < paper_count:
                        recommended.append(
                            {
                                "index": idx,
                                "title": "",
                                "reason": item,
                                "summary": "",
                                "category": "",
                                "url": "",
                                "pdf_url": "",
                                "authors": "",
                                "published": "",
                            }
                        )
            continue

        index = item.get("index", -1)
        if isinstance(index, str) and index.isdigit():
            index = int(index)
        if not isinstance(index, int) or index < 0 or index >= paper_count:
            text = " ".join(str(item.get(key, "")) for key in ("title", "reason", "summary"))
            indices = _extract_paper_indices(text)
            if not indices:
                continue
            index = indices[0]
            if index < 0 or index >= paper_count:
                continue

        recommended.append(
            {
                "index": index,
                "title": item.get("title", ""),
                "reason": item.get("reason", ""),
                "summary": item.get("summary", ""),
                "category": "",
                "url": "",
                "pdf_url": "",
                "authors": "",
                "published": "",
            }
        )

    return recommended


def _parse_fallback_recommendations(response: str, paper_count: int) -> list[dict[str, object]]:
    """从全文中回退解析推荐索引（论文X / paper X）。"""
    indices = _extract_paper_indices(response)
    if not indices:
        return []

    recommended: list[dict[str, object]] = []
    for idx in indices:
        if 0 <= idx < paper_count:
            recommended.append(
                {
                    "index": idx,
                    "title": "",
                    "reason": f"匹配到文本推荐: 论文{idx}",
                    "summary": "",
                    "category": "",
                    "url": "",
                    "pdf_url": "",
                    "authors": "",
                    "published": "",
                }
            )
    return recommended


def _get_default_trigger_comment(agent: str) -> str:
    """获取默认的触发评论

    Args:
        agent: Agent 名称

    Returns:
        默认的触发评论
    """
    agent_map = {
        "moderator": "@moderator 请审核",
        "reviewer_a": "@reviewer_a 评审",
        "reviewer_b": "@reviewer_b 找问题",
        "summarizer": "@summarizer 汇总",
        "observer": "@observer",
    }
    return agent_map.get(agent, f"@{agent}")
