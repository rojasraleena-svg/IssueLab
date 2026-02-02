"""SDK 执行器：使用 Claude Agent SDK 构建评审代理"""
import anyio
import os
from pathlib import Path
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
)

# 提示词目录
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_prompt(agent_name: str) -> str:
    """加载代理提示词"""
    prompts = {
        "moderator": "moderator.md",
        "reviewer_a": "reviewer_a.md",
        "reviewer_b": "reviewer_b.md",
        "summarizer": "summarizer.md",
    }
    if agent_name not in prompts:
        return ""
    prompt_path = PROMPTS_DIR / prompts[agent_name]
    if prompt_path.exists() and prompt_path.is_file():
        return prompt_path.read_text()
    return ""


def create_agent_options() -> ClaudeAgentOptions:
    """创建包含所有评审代理的配置"""
    # 从环境变量读取配置
    api_key = os.environ.get("ANTHROPIC_AUTH_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    model = os.environ.get("ANTHROPIC_MODEL", "sonnet")

    # 构建环境变量字典传给 SDK
    env = {}
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    if model:
        env["ANTHROPIC_MODEL"] = model

    # arxiv MCP 存储路径
    arxiv_storage_path = os.environ.get("ARXIV_STORAGE_PATH", str(Path.home() / ".arxiv-mcp-server" / "papers"))

    # MCP 服务器配置
    mcp_servers = []
    if os.environ.get("ENABLE_ARXIV_MCP", "true").lower() == "true":
        mcp_servers.append({
            "name": "arxiv-mcp-server",
            "command": "uv",
            "args": [
                "--directory",
                str(Path(__file__).parent.parent.parent),
                "tool",
                "run",
                "arxiv-mcp-server",
                "--storage-path",
                arxiv_storage_path,
            ],
            "env": env.copy(),
        })

    # 定义评审代理使用的 arxiv 工具列表
    arxiv_tools = ["search_papers", "download_paper", "read_paper", "list_papers"]

    return ClaudeAgentOptions(
        agents={
            "moderator": AgentDefinition(
                description="分诊与控场代理",
                prompt=load_prompt("moderator"),
                tools=["Read", "Write", "Bash"] + arxiv_tools,
                model=model,
            ),
            "reviewer_a": AgentDefinition(
                description="正方评审代理",
                prompt=load_prompt("reviewer_a"),
                tools=["Read", "Write", "Bash"] + arxiv_tools,
                model=model,
            ),
            "reviewer_b": AgentDefinition(
                description="反方评审代理",
                prompt=load_prompt("reviewer_b"),
                tools=["Read", "Write", "Bash"] + arxiv_tools,
                model=model,
            ),
            "summarizer": AgentDefinition(
                description="共识汇总代理",
                prompt=load_prompt("summarizer"),
                tools=["Read", "Write"] + arxiv_tools,
                model=model,
            ),
        },
        setting_sources=["user", "project"],
        env=env,
        mcp_servers=mcp_servers,
    )


async def run_single_agent(prompt: str, agent_name: str) -> str:
    """运行单个代理

    Args:
        prompt: 用户提示词
        agent_name: 代理名称

    Returns:
        代理响应文本
    """
    options = create_agent_options()

    response_text = []

    async for message in query(
        prompt=prompt,
        options=options,
    ):
        from claude_agent_sdk import AssistantMessage, TextBlock
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text.append(block.text)

    return "\n".join(response_text)


async def run_agents_parallel(issue_number: int, agents: list[str], context: str = "", comment_count: int = 0) -> dict:
    """并行运行多个代理

    Args:
        issue_number: Issue 编号
        agents: 代理名称列表
        context: 上下文信息
        comment_count: 评论数量（用于增强上下文）

    Returns:
        {agent_name: response_text}
    """
    # 构建增强的上下文
    full_context = context
    if comment_count > 0:
        full_context += f"\n\n**重要提示**: 本 Issue 已有 {comment_count} 条历史评论。Summarizer 代理应读取并分析这些评论，提取共识、分歧和行动项。"

    base_prompt = f"""请对 GitHub Issue #{issue_number} 执行以下任务：

{full_context}

请以 [Agent: {{agent_name}}] 为前缀发布你的回复。"""

    results = {}
    async with anyio.create_task_group() as tg:
        async def run_and_store(agent_name: str):
            prompt = base_prompt.format(agent_name=agent_name)
            response = await run_single_agent(prompt, agent_name)
            results[agent_name] = response

        for agent in agents:
            tg.start_soon(run_and_store, agent)

    return results
