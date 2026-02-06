#!/usr/bin/env python3
"""
arXiv Monitor - 获取新论文，智能分析，推荐讨论

Usage:
    # 获取论文并智能分析
    python scripts/monitor_arxiv.py \
        --token "ghp_xxx" \
        --repo "owner/repo" \
        --categories "cs.AI,cs.LG,cs.CL"

    # 仅扫描获取论文列表
    python scripts/monitor_arxiv.py --scan-only --output /tmp/papers.json

Environment:
    LOG_LEVEL: 设置日志级别 (DEBUG, INFO, WARNING, ERROR)
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import feedparser
from github import Github

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_arxiv_date(date_str: str) -> str:
    """解析 arXiv 日期格式"""
    try:
        dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str[:10] if date_str else "Unknown"


def clean_text(text: str) -> str:
    """清理文本中的多余空白"""
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text: str, max_length: int = 1500) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(".", 1)[0] + "..."


def fetch_papers(categories: list[str], last_scan: str, max_papers: int = 10) -> list[dict[str, Any]]:
    """获取 arXiv 新论文"""
    try:
        last_scan_dt = datetime.strptime(last_scan[:19], "%Y-%m-%dT%H:%M:%S")
        last_scan_timestamp = last_scan_dt.timestamp()
    except (ValueError, TypeError):
        last_scan_timestamp = 0

    all_papers = []

    for category in categories:
        print(f"[INFO] 获取 {category} 分类...")

        base_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_papers * 3,
        }
        url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        try:
            response = feedparser.parse(url)

            for entry in response.entries:
                try:
                    published_timestamp = datetime.strptime(
                        entry.get("published", "")[:19], "%Y-%m-%dT%H:%M:%S"
                    ).timestamp()
                except (ValueError, TypeError):
                    continue

                if published_timestamp <= last_scan_timestamp:
                    continue

                authors = ", ".join(a.get("name", "") for a in entry.get("authors", [])[:5])
                if len(entry.get("authors", [])) > 5:
                    authors += f" 等 {len(entry.get('authors', []))} 位作者"

                arxiv_id = entry.get("id", "").split("/abs/")[-1]

                all_papers.append(
                    {
                        "id": arxiv_id,
                        "title": clean_text(entry.get("title", "")),
                        "summary": truncate_text(clean_text(entry.get("summary", ""))),
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        "authors": authors,
                        "published": parse_arxiv_date(entry.get("published", "")),
                        "published_raw": entry.get("published", ""),
                        "category": category,
                    }
                )

        except Exception as e:
            print(f"   [WARNING] 获取失败: {e}")
            continue

    # 去重并排序
    seen_ids = set()
    unique_papers = []
    for p in all_papers:
        if p["id"] not in seen_ids:
            seen_ids.add(p["id"])
            unique_papers.append(p)

    unique_papers.sort(key=lambda x: x.get("published_raw", ""), reverse=True)
    return unique_papers[:max_papers]


def build_papers_for_observer(papers: list[dict]) -> str:
    """构建供 Observer 分析的论文上下文"""
    lines = ["## 可讨论的 arXiv 论文候选\n"]

    for i, paper in enumerate(papers):
        lines.append(f"### 论文 {i}")
        lines.append(f"**标题**: {paper['title']}")
        lines.append(f"**分类**: {paper['category']}")
        lines.append(f"**发布时间**: {paper['published']}")
        lines.append(f"**链接**: [{paper['url']}]({paper['url']})")
        lines.append(f"**作者**: {paper['authors']}")
        lines.append(f"**摘要**: {paper['summary']}")
        lines.append("")

    return "\n".join(lines)


def filter_existing_papers(papers: list[dict], repo_name: str, token: str) -> list[dict]:
    """过滤掉已存在 Issue 的论文

    Args:
        papers: 论文列表
        repo_name: 仓库名 (owner/repo)
        token: GitHub Token

    Returns:
        过滤后的论文列表
    """
    if not papers:
        return []

    g = Github(token)
    repo = g.get_repo(repo_name)

    # 获取已存在的 Issue 标题
    existing_titles = {issue.title for issue in repo.get_issues(state="all")}

    # 过滤
    filtered = []
    for paper in papers:
        title = f"[论文讨论] {paper['title']}"
        if title in existing_titles:
            logger.debug(f"跳过已存在: {title[:50]}...")
        else:
            filtered.append(paper)

    logger.info(f"过滤后剩余 {len(filtered)} 篇新论文（已排除 {len(papers) - len(filtered)} 篇已存在）")
    return filtered


def analyze_with_observer(papers: list[dict], token: str) -> list[dict]:
    """使用 Observer agent 分析论文，返回推荐的论文"""

    import asyncio
    from pathlib import Path

    # 动态导入 SDK
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from issuelab.agents.observer import run_observer_for_papers

    logger.info(f"\n{'=' * 60}")
    logger.info(f"[Observer Agent] 开始智能分析 {len(papers)} 篇论文")
    logger.info(f"{'=' * 60}")

    # 如果论文不足 1 篇，无法推荐
    if len(papers) < 1:
        logger.warning("论文数量不足 1 篇，无法进行智能推荐")
        return []

    # 调用真正的 Observer agent
    try:
        logger.debug("[Observer] 调用 run_observer_for_papers...")
        recommended = asyncio.run(run_observer_for_papers(papers))
        logger.info(f"[Observer] 分析完成，推荐 {len(recommended)} 篇论文")
        logger.debug(f"[Observer] 推荐结果: {recommended}")
        return recommended
    except Exception as e:
        logger.error(f"[Observer] 分析失败: {e}", exc_info=True)
        logger.info("[回退] 使用启发式规则替代...")

        # 回退到启发式规则
        recommended = []
        selected_topics = set()

        for i, paper in enumerate(papers):
            if paper["category"] in selected_topics and len(selected_topics) >= 2:
                continue

            if len(recommended) < 2:
                hot_keywords = ["transformer", "llm", "diffusion", "reinforcement", "gpt", "neural"]
                summary_lower = paper["summary"].lower()
                hot_count = sum(1 for kw in hot_keywords if kw in summary_lower)

                reason = f"最新发布的 {paper['category']} 论文"
                if hot_count > 0:
                    reason = f"{paper['category']} 热门方向论文，包含 {hot_count} 个热点关键词"

                recommended.append(
                    {
                        "index": i,
                        "title": paper["title"],
                        "reason": reason,
                        "summary": paper["summary"][:200] + "...",
                        "category": paper["category"],
                        "url": paper["url"],
                        "pdf_url": paper["pdf_url"],
                        "authors": paper["authors"],
                        "published": paper["published"],
                    }
                )

                selected_topics.add(paper["category"])

        print(f"[OK] 回退分析完成，推荐 {len(recommended)} 篇论文")
        return recommended


def create_issues(recommended: list[dict], repo_name: str, token: str) -> int:
    """根据 Observer 推荐创建 GitHub Issues"""
    if not recommended:
        print("[INFO] 无推荐论文，不创建 Issue")
        return 0

    g = Github(token)
    repo = g.get_repo(repo_name)

    created = 0

    for paper in recommended:
        title = f"[论文讨论] {paper['title']}"

        body = f"""## 论文信息

**标题**: [{paper["title"]}]({paper["url"]})
**作者**: {paper["authors"]}
**发布时间**: {paper["published"]}
**分类**: {paper["category"]}
**PDF**: [Download]({paper["pdf_url"]})

## 简介

{paper["summary"]}

## 推荐理由

{paper["reason"]}

## 讨论

请对这篇论文发表您的见解：
- 论文的创新点是什么？
- 方法是否合理？
- 实验结果是否可信？
- 有哪些可以改进的地方？

---
_由 arXiv Monitor 自动创建_"""

        # 创建 Issue
        issue = repo.create_issue(title=title, body=body)
        print(f"[OK] 创建 Issue: {title[:50]}...")

        # 创建评论触发 @moderator（评论中的 @ 会触发 orchestrator.yml）
        trigger_comment = "@moderator 请审核"
        issue.create_comment(trigger_comment)
        print(f"[INFO] 触发评论: {trigger_comment}")

        created += 1
        time.sleep(2)

    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="arXiv Monitor - 智能获取并分析论文")
    parser.add_argument("--token", type=str, help="GitHub Token")
    parser.add_argument("--repo", type=str, help="Repository (owner/repo)")
    parser.add_argument("--categories", type=str, default="cs.AI,cs.LG,cs.CL")
    parser.add_argument("--max-papers", type=int, default=10, help="获取论文数量（分析前）")
    parser.add_argument("--max-recommended", type=int, default=2, help="最多推荐论文数量")
    parser.add_argument("--output", type=str, help="Output JSON file (optional)")
    parser.add_argument("--last-scan", type=str, help="Last scan time (ISO format)")
    parser.add_argument("--scan-only", action="store_true", help="Only scan, don't analyze")

    args = parser.parse_args(argv)

    # 根据环境变量设置日志级别
    log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)

    # 默认 7 天前
    last_scan = args.last_scan or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    logger.info(f"{'=' * 60}")
    logger.info("[arXiv Monitor] 开始扫描新论文")
    logger.info(f"{'=' * 60}")
    logger.info(f"分类: {', '.join(categories)}")
    logger.info(f"上次扫描: {last_scan}")

    # 获取论文
    papers = fetch_papers(categories, last_scan, args.max_papers)
    logger.info(f"发现 {len(papers)} 篇新论文")

    if not papers:
        logger.info("未发现新论文")
        return 0

    # 保存 JSON（如果指定）
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        logger.info(f"保存到: {args.output}")

    # 仅扫描模式
    if args.scan_only:
        for i, p in enumerate(papers, 1):
            logger.info(f"   {i}. [{p['category']}] {p['title'][:50]}...")
        return 0

    # 分析并创建 Issues
    if args.token and args.repo:
        # 先过滤已存在的论文
        new_papers = filter_existing_papers(papers, args.repo, args.token)

        # Observer 分析（只分析新论文）
        recommended = analyze_with_observer(new_papers, args.token)

        if args.max_recommended > 0:
            recommended = recommended[: args.max_recommended]

        if len(recommended) == 0:
            if len(new_papers) == 0:
                logger.info("所有论文已存在，无需推荐")
            elif len(new_papers) < 1:
                logger.info("新论文数量不足 1 篇，无法智能推荐")
            else:
                logger.info("智能分析未返回有效结果")
            return 0

        # 创建 Issues
        logger.info("开始创建 Issues...")
        created = create_issues(recommended, args.repo, args.token)
        logger.info(f"{'=' * 60}")
        logger.info(f"[完成] 创建 {created} 个 Issues")
        logger.info(f"{'=' * 60}")
    else:
        logger.info("提供 --token 和 --repo 参数可自动分析并创建 Issues")
        for i, p in enumerate(papers, 1):
            logger.info(f"   {i}. [{p['category']}] {p['title'][:50]}...")

    return 0


if __name__ == "__main__":
    import os

    sys.exit(main())
