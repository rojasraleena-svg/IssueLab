"""Claude Agent SDK 选项构建

处理 SDK 选项的创建和缓存管理。
"""

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

from issuelab.agents.config import AgentConfig
from issuelab.agents.discovery import discover_agents
from issuelab.config import Config
from issuelab.logging_config import get_logger

logger = get_logger(__name__)

# 全局缓存：存储 Agent 选项
_cached_agent_options: dict[tuple, ClaudeAgentOptions] = {}


def clear_agent_options_cache() -> None:
    """清除 Agent 选项缓存

    在测试或配置更改后调用此函数以确保使用最新的配置。
    """
    global _cached_agent_options
    _cached_agent_options = {}
    logger.info("Agent 选项缓存已清除")


def _create_agent_options_impl(
    max_turns: int | None,
    max_budget_usd: float | None,
) -> ClaudeAgentOptions:
    """创建 Agent 选项的实际实现（无缓存）"""
    env = Config.get_anthropic_env()
    env["CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK"] = "true"

    # 收集 SDK 内部日志的回调
    sdk_logs: list[str] = []

    def sdk_stderr_handler(message: str) -> None:
        """捕获 SDK 内部日志（包含详细的模型交互信息）"""
        log_entry = f"[SDK] {message}"
        sdk_logs.append(log_entry)
        # 输出到终端
        print(message, end="", flush=True)
        # 记录到日志
        logger.debug(f"[SDK] {message}")

    agents = discover_agents()

    base_tools = ["Read", "Write", "Bash"]

    all_tools = base_tools
    model = Config.get_anthropic_model()

    agent_definitions = {}
    for name, config in agents.items():
        if name == "observer":
            continue
        agent_definitions[name] = AgentDefinition(
            description=config["description"],
            prompt=config["prompt"],
            tools=all_tools,
            model=model,
        )

    return ClaudeAgentOptions(
        agents=agent_definitions,
        max_turns=max_turns if max_turns is not None else AgentConfig().max_turns,
        max_budget_usd=max_budget_usd if max_budget_usd is not None else AgentConfig().max_budget_usd,
        setting_sources=["user", "project"],
        env=env,
        permission_mode="bypassPermissions",
        stderr=sdk_stderr_handler,  # 捕获 SDK 内部详细日志
    )


def create_agent_options(
    max_turns: int | None = None,
    max_budget_usd: float | None = None,
) -> ClaudeAgentOptions:
    """创建包含所有评审代理的配置（动态发现）

    官方推荐的超时控制参数：
    - max_turns: 限制对话轮数，防止无限循环
    - max_budget_usd: 限制花费，防止意外支出

    Args:
        max_turns: 最大对话轮数（默认使用 AgentConfig 默认值）
        max_budget_usd: 最大花费限制（默认使用 AgentConfig 默认值）

    Returns:
        ClaudeAgentOptions: 配置好的 SDK 选项

    Note:
        此函数使用缓存来避免重复创建相同的配置。
        如果需要强制刷新配置，请先调用 clear_agent_options_cache()。
    """
    # 使用默认值
    effective_max_turns = max_turns if max_turns is not None else AgentConfig().max_turns
    effective_max_budget = max_budget_usd if max_budget_usd is not None else AgentConfig().max_budget_usd

    # 缓存键：使用参数元组
    cache_key = (effective_max_turns, effective_max_budget)

    # 检查缓存
    if cache_key in _cached_agent_options:
        logger.debug(f"使用缓存的 Agent 选项 (key={cache_key})")
        return _cached_agent_options[cache_key]

    # 创建新配置
    options = _create_agent_options_impl(max_turns, max_budget_usd)

    # 存入缓存
    _cached_agent_options[cache_key] = options
    logger.debug(f"创建新的 Agent 选项并缓存 (key={cache_key})")

    return options
