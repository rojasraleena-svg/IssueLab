"""@mention 解析器：从评论中提取代理名称"""
import re


# 代理名称映射表
AGENT_ALIASES = {
    # Moderator 变体
    "moderator": "moderator",
    "mod": "moderator",
    # ReviewerA 变体
    "reviewer": "reviewer_a",
    "reviewera": "reviewer_a",
    "reviewer_a": "reviewer_a",
    "reva": "reviewer_a",
    # ReviewerB 变体
    "reviewerb": "reviewer_b",
    "reviewer_b": "reviewer_b",
    "revb": "reviewer_b",
    # Summarizer 变体
    "summarizer": "summarizer",
    "summary": "summarizer",
}


def parse_mentions(comment_body: str) -> list[str]:
    """从评论中解析 @mention"""
    pattern = r'@([a-zA-Z_]+)'
    raw_mentions = re.findall(pattern, comment_body, re.IGNORECASE)

    # 映射到标准名称
    agents = []
    for m in raw_mentions:
        normalized = m.lower()
        if normalized in AGENT_ALIASES:
            agents.append(AGENT_ALIASES[normalized])

    # 去重，保持顺序
    seen = set()
    unique_agents = []
    for a in agents:
        if a not in seen:
            seen.add(a)
            unique_agents.append(a)

    return unique_agents


def has_mentions(comment_body: str) -> bool:
    """检查评论是否包含 @mention"""
    return bool(re.search(r'@[a-zA-Z_]+', comment_body))
