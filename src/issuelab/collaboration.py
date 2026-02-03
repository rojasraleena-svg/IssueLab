"""协作配置模块 - 系统级 @mentions 指南

负责加载协作配置并构建协作指南，为所有 agents 统一提供协作能力。
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_collaboration_config() -> dict[str, Any]:
    """加载协作配置

    Returns:
        协作配置字典，如果加载失败返回默认配置（disabled）
    """
    config_paths = [
        Path(__file__).parent.parent.parent / "config" / "collaboration.yml",
        Path.cwd() / "config" / "collaboration.yml",
    ]

    config_file = None
    for path in config_paths:
        if path.exists():
            config_file = path
            break

    # 默认配置（禁用）
    default_config = {
        "enabled": False,
        "guidelines_template": "",
    }

    if not config_file:
        logger.debug("未找到 collaboration.yml，协作指南已禁用")
        return default_config

    try:
        import yaml

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "collaboration" not in config:
            logger.warning("collaboration.yml 格式错误，协作指南已禁用")
            return default_config

        collaboration = config["collaboration"]
        logger.info(f"加载协作配置: enabled={collaboration.get('enabled', False)}")
        return collaboration

    except ImportError:
        logger.warning("缺少 pyyaml 依赖，协作指南已禁用")
        return default_config
    except Exception as e:
        logger.error(f"加载协作配置失败: {e}，协作指南已禁用")
        return default_config


def build_collaboration_guidelines(agents: dict[str, dict]) -> str:
    """构建协作指南

    Args:
        agents: agents 字典 {agent_name: agent_config}

    Returns:
        协作指南文本，如果禁用或构建失败返回空字符串
    """
    try:
        # 加载配置
        config = load_collaboration_config()

        if not config.get("enabled", False):
            return ""

        template = config.get("guidelines_template", "")
        if not template:
            return ""

        # 构建可用 agents 列表
        agent_lines = []
        for name, info in sorted(agents.items()):
            description = info.get("description", "Agent")
            agent_lines.append(f"- @{name}（{description}）")

        available_agents = "\n".join(agent_lines)

        # 替换模板变量
        guidelines = template.format(available_agents=available_agents)

        logger.debug(f"构建协作指南成功，包含 {len(agents)} 个 agents")
        return guidelines

    except Exception as e:
        logger.error(f"构建协作指南失败: {e}")
        return ""
