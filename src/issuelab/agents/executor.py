"""Agent 执行器核心

处理 Agent 的执行、消息流和日志记录。
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

from issuelab.agents.options import create_agent_options
from issuelab.logging_config import get_logger
from issuelab.retry import retry_async

logger = get_logger(__name__)


async def run_single_agent(prompt: str, agent_name: str) -> dict:
    """运行单个代理（带完善的中间日志监听）

    Args:
        prompt: 用户提示词
        agent_name: 代理名称

    Returns:
        {
            "response": str,  # 代理响应文本
            "cost_usd": float,  # 成本（美元）
            "num_turns": int,  # 对话轮数
            "tool_calls": list[str],  # 工具调用列表
            "local_id": str,  # 会话 ID
        }
    """
    logger.info(f"[{agent_name}] 开始运行 Agent")
    logger.debug(f"[{agent_name}] Prompt 长度: {len(prompt)} 字符")

    # 执行信息收集
    execution_info = {
        "response": "",
        "cost_usd": 0.0,
        "num_turns": 0,
        "tool_calls": [],
        "local_id": "",
        "text_blocks": [],
    }

    async def _query_agent():
        options = create_agent_options()
        response_text = []
        turn_count = 0
        tool_calls = []
        first_result = True

        async for message in query(prompt=prompt, options=options):
            # AssistantMessage: AI 响应（文本或工具调用）
            if isinstance(message, AssistantMessage):
                turn_count += 1
                logger.debug(f"[{agent_name}] 收到消息 (第 {turn_count} 轮)")

                for block in message.content:
                    # 文本块 → 终端流式输出 + INFO 日志
                    if isinstance(block, TextBlock):
                        text = block.text
                        response_text.append(text)
                        execution_info["text_blocks"].append(text)

                        # 终端流式输出
                        print(text, end="", flush=True)
                        # 日志记录（INFO 级别）
                        logger.info(f"[{agent_name}] [Text] {text[:100]}...")

                    # 思考块 → 输出思考过程
                    elif isinstance(block, ThinkingBlock):
                        thinking = getattr(block, "thinking", "")
                        if thinking:
                            thinking_preview = thinking[:200] + "..." if len(thinking) > 200 else thinking
                            logger.debug(f"[{agent_name}] [Thinking] {thinking_preview}")

                    # 工具调用块 → 终端显示 + INFO 日志
                    elif isinstance(block, ToolUseBlock):
                        tool_name = block.name
                        tool_use_id = getattr(block, "tool_use_id", "")
                        tool_input = getattr(block, "input", {})
                        tool_calls.append(tool_name)
                        execution_info["tool_calls"].append(tool_name)

                        # 终端输出
                        print(f"\n[{tool_name}] id={tool_use_id}", end="", flush=True)
                        # 详细日志输出
                        if isinstance(tool_input, dict):
                            import json

                            input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
                            logger.info(f"[{agent_name}] [Tool] {tool_name}(id={tool_use_id})")
                            logger.debug(f"[{agent_name}] [ToolInput] {input_str}")
                        else:
                            logger.info(f"[{agent_name}] [Tool] {tool_name}(id={tool_use_id})")

                    # 工具结果块 → 只日志，不终端输出
                    elif isinstance(block, ToolResultBlock):
                        tool_use_id = getattr(block, "tool_use_id", "")
                        is_error = getattr(block, "is_error", False)
                        result = getattr(block, "result", "")
                        # 限制结果长度，避免日志过多
                        if isinstance(result, str) and len(result) > 500:
                            logger.info(f"[{agent_name}] [ToolResult] id={tool_use_id} error={is_error} (truncated)")
                            logger.debug(f"[{agent_name}] [ToolResult] id={tool_use_id}:\n{result[:500]}...")
                        else:
                            logger.info(f"[{agent_name}] [ToolResult] id={tool_use_id} error={is_error}")
                            if result:
                                logger.debug(f"[{agent_name}] [ToolResult] id={tool_use_id}: {result}")

            # ResultMessage: 执行结果（成本、统计信息）
            elif isinstance(message, ResultMessage):
                # 打印统计信息
                print("\n")
                session_id = message.session_id or ""
                cost_usd = message.total_cost_usd or 0.0
                result_turns = message.num_turns or turn_count

                execution_info["session_id"] = session_id
                execution_info["cost_usd"] = cost_usd
                execution_info["num_turns"] = result_turns

                # 只在第一次收到 ResultMessage 时记录
                if first_result:
                    logger.info(f"[{agent_name}] [Result] session_id={session_id}")
                    first_result = False

                # 日志记录成本和统计
                logger.info(
                    f"[{agent_name}] [Stats] 成本: ${cost_usd:.4f}, "
                    f"轮数: {result_turns}, 工具调用: {len(tool_calls)}"
                )

        result = "\n".join(response_text)
        return result

    try:
        response = await retry_async(_query_agent, max_retries=3, initial_delay=2.0, backoff_factor=2.0)
        execution_info["response"] = response

        # 最终日志
        logger.info(
            f"[{agent_name}] 完成 - "
            f"响应长度: {len(response)} 字符, "
            f"成本: ${execution_info['cost_usd']:.4f}, "
            f"轮数: {execution_info['num_turns']}, "
            f"工具调用: {len(execution_info['tool_calls'])}"
        )

        return execution_info
    except Exception as e:
        logger.error(f"[{agent_name}] 运行失败: {e}", exc_info=True)
        return {
            "response": f"[错误] Agent {agent_name} 执行失败: {e}",
            "cost_usd": 0.0,
            "num_turns": 0,
            "tool_calls": [],
            "session_id": "",
            "text_blocks": [],
        }


async def run_agents_parallel(
    issue_number: int,
    agents: list[str],
    context: str = "",
    comment_count: int = 0,
    available_agents: list[dict] | None = None,
) -> dict:
    """并行运行多个代理

    Args:
        issue_number: Issue 编号
        agents: 代理名称列表
        context: 上下文信息
        comment_count: 评论数量（用于增强上下文）
        available_agents: 系统中可用的智能体列表

    Returns:
        {
            agent_name: {
                "response": str,
                "cost_usd": float,
                "num_turns": int,
                "tool_calls": list[str],
                "session_id": str,
            }
        }
    """
    # 构建增强的上下文
    full_context = context
    if comment_count > 0:
        full_context += f"\n\n**重要提示**: 本 Issue 已有 {comment_count} 条历史评论。Summarizer 代理应读取并分析这些评论，提取共识、分歧和行动项。"

    # 添加可用智能体上下文
    agents_context = ""
    if available_agents:
        agents_context = "\n\n## 系统中的其他智能体\n\n"
        agents_context += "当你需要协作时，可以@以下智能体（**每次最多@2个**）：\n\n"

        for agent in available_agents:
            name = agent.get("name", "")
            desc = agent.get("description", "")
            agents_context += f"- **{name}** - {desc}\n"

        agents_context += "\n**协作规则：**\n"
        agents_context += "- 每次回复中最多@2个智能体\n"
        agents_context += "- 仅在确实需要协作时才@，不要无脑@\n"
        agents_context += "- 示例场景：需要分诊→@gqy20；需要评审→@gqy22\n"

        full_context += agents_context

    base_prompt = f"""请对 GitHub Issue #{issue_number} 执行以下任务：

{full_context}

请以 [Agent: {{agent_name}}] 为前缀发布你的回复。"""

    results: dict[str, dict] = {}
    total_cost = 0.0

    async def run_agent_task(agent_name: str, prompt: str, results: dict[str, dict]) -> None:
        """并行任务：运行单个 agent"""
        logger.info(f"[Issue#{issue_number}] [并行] 开始执行 {agent_name}")
        result = await run_single_agent(prompt, agent_name)
        results[agent_name] = result
        total_cost_local = result.get("cost_usd", 0.0)
        logger.info(
            f"[Issue#{issue_number}] {agent_name} 完成 - "
            f"成本: ${total_cost_local:.4f}, "
            f"轮数: {result.get('num_turns', 0)}, "
            f"工具: {len(result.get('tool_calls', []))}"
        )

    # 使用 anyio.create_task_group 实现真正的并行执行
    async with anyio.create_task_group() as tg:
        for agent in agents:
            prompt = base_prompt.format(agent_name=agent)
            tg.start_soon(run_agent_task, agent, prompt, results)

    # 汇总总成本
    total_cost = sum(r.get("cost_usd", 0.0) for r in results.values())
    logger.info(f"[Issue#{issue_number}] 所有 Agent 完成 - 总成本: ${total_cost:.4f}")
    return results
