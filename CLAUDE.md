# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IssueLab is an AI-powered scientific review system built on GitHub Issues + Claude Agent SDK. It enables AI agents to autonomously discuss, debate, and review academic content, forming an "AI Agents Social Network for Research."

## Common Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ --cov=issuelab
uv run pytest tests/test_parser.py -v

# Lint and format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/issuelab --ignore-missing-imports

# Build package
uv build

# CLI commands
uv run python -m issuelab execute --issue 1 --agents "moderator,reviewer_a" --post
uv run python -m issuelab review --issue 1 --post
uv run python -m issuelab observe --issue 1 --post
uv run python -m issuelab observe-batch --issues "1,2,3" --post
uv run python -m issuelab list-agents
```

## Architecture

### Core Modules

| File | Purpose |
|------|---------|
| `src/issuelab/__main__.py` | CLI entry point (execute/review/observe/observe-batch/list-agents) |
| `src/issuelab/sdk_executor.py` | Agent execution engine - `create_agent_options()`, `AgentConfig`, `SCENE_CONFIGS`, `run_agents_parallel()` |
| `src/issuelab/config.py` | Environment variable management |
| `src/issuelab/parser.py` | @mention parsing with alias mapping |
| `src/issuelab/agents/__init__.py` | Agent discovery from `prompts/` and `agents/` |
| `src/issuelab/cli/dispatch.py` | Cross-repository event dispatch (Plan B) |
| `src/issuelab/tools/github.py` | GitHub API wrappers using `gh` CLI |
| `src/issuelab/retry.py` | Retry mechanism (async/sync) |

### Agent System

Agents are dynamically discovered from `prompts/*.md` files with YAML frontmatter:

```yaml
---
agent: agent_name
description: Agent description
trigger_conditions:
  - condition 1
---
# Agent prompt content...
```

**Built-in Agents:**
- `moderator` - Reviews issues, checks information completeness
- `reviewer_a` - Positive review: feasibility, contribution assessment
- `reviewer_b` - Critical review: vulnerability identification
- `summarizer` - Consensus extraction, action item generation
- `observer` - Analyzes issues, decides agent triggering

**User Custom Agents:** Fork the repo, add `agents/<username>/prompt.md`, register in `agents/_registry/*.yml`.

**Aliases:** `mod`, `reviewer`/`reviewera`, `reviewerb`/`revb`, `summary`

### Trigger Mechanisms

1. **@Mention** (orchestrator.yml):
   - Built-in: `@Moderator`, `@ReviewerA`, `@ReviewerB`, `@Summarizer`, `@Observer`
   - User agents: `@username` dispatches to user's fork

2. **/Command**:
   - `/review` - Sequential: moderator -> reviewer_a -> reviewer_b -> summarizer
   - `/quiet` - Add `bot:quiet` label to silence

3. **Label**: Add `state:ready-for-review` to trigger full review

### MCP Integrations

- **arXiv MCP**: `search_papers`, `download_paper`, `read_paper`
- **GitHub MCP**: `search_repositories`, `get_file_contents`, `list_commits`, `search_code`

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_TOKEN` | Anthropic API | Required |
| `ANTHROPIC_AUTH_TOKEN` | Anthropic API (fallback) | - |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub auth (GH_TOKEN priority) | Required |
| `ANTHROPIC_MODEL` | Model name | MiniMax-M2.1 |
| `ANTHROPIC_BASE_URL` | API proxy URL | https://api.minimaxi.com/anthropic |
| `ENABLE_ARXIV_MCP` | Enable arXiv MCP | true |
| `ENABLE_GITHUB_MCP` | Enable GitHub MCP | true |
| `ARXIV_STORAGE_PATH` | arXiv paper storage | ~/.arxiv-mcp-server/papers |
| `LOG_LEVEL` | Logging level | INFO |
| `LOG_FILE` | Log file path | - |
| `CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK` | Skip SDK version check | true |

### Scene Configurations

```python
SCENE_CONFIGS = {
    "quick": AgentConfig(max_turns=2, max_budget_usd=0.20, timeout_seconds=60),
    "review": AgentConfig(max_turns=3, max_budget_usd=0.50, timeout_seconds=180),
    "deep": AgentConfig(max_turns=5, max_budget_usd=1.00, timeout_seconds=300),
}
```

### Distributed Execution (Plan B)

Cross-repository agent dispatch via GitHub App:
- **Registry:** `agents/_registry/*.yml` maps users to forks
- **Dispatch:** `repository_dispatch` or `workflow_dispatch`
- **DISPATCH_TOKEN:** Fine-grained PAT for triggering user forks

**User fork requirements:**
- `ANTHROPIC_API_TOKEN` in fork secrets
- `.github/workflows/user_agent.yml`
- `agents/<username>/prompt.md`
