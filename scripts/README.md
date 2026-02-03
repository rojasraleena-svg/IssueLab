# Scripts 目录

## 📁 设计目的

这个目录包含 **轻量级包装器脚本**，用于在 GitHub Actions 中快速执行 CLI 功能，**无需安装完整的 issuelab 包**。

## 🎯 使用场景

### 1. 轻量级 Workflow（推荐使用 scripts）

对于只需要**基础功能**的 workflow（如 `dispatch_agents.yml`）：

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.12'

- name: Install minimal dependencies
  run: pip install PyYAML requests

- name: Parse mentions (fast!)
  run: python scripts/parse_mentions.py --comment-body "..."
```

**优势：**
- ✅ 无需 `uv sync`（节省 ~10-20 秒）
- ✅ 不安装 Claude SDK 等重量级依赖
- ✅ 只需要 PyYAML 和 requests

### 2. 完整功能 Workflow（使用 uv run）

对于需要**完整 Agent 功能**的 workflow（如 `orchestrator.yml`）：

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4

- name: Install dependencies
  run: uv sync

- name: Parse mentions (integrated)
  run: uv run python -m issuelab.cli.mentions --comment-body "..."
```

**优势：**
- ✅ 使用已安装的包，避免重复代码
- ✅ 类型检查和 IDE 支持更好
- ✅ 与主代码库保持一致

## 📄 包含的脚本

| 脚本 | 功能 | 最小依赖 |
|------|------|----------|
| `parse_mentions.py` | 解析 @mentions | 无（stdlib） |
| `dispatch_to_users.py` | 跨仓库分发事件 | PyYAML, requests |

## 🔧 工作原理

Scripts 通过动态导入实现零依赖启动：

```python
if __name__ == "__main__":
    # 添加 src 到路径，无需安装包
    src_path = Path(__file__).parent.parent / "src"
    sys.path.insert(0, str(src_path))

    # 直接导入 CLI 模块
    from issuelab.cli.mentions import main
    sys.exit(main())
```

## ⚖️ 何时使用哪种方式？

| 场景 | 使用方式 | 原因 |
|------|----------|------|
| 只需解析 mentions 和分发 | `python scripts/xxx.py` | 快速，轻量 |
| 需要运行 Agents（LLM 调用） | `uv run python -m issuelab.cli.xxx` | 需要完整依赖 |
| 本地开发测试 | `uv run python -m issuelab.cli.xxx` | 类型安全 |

## 🚫 不要混用！

❌ **错误做法：**
```yaml
- run: uv sync  # 安装了完整包
- run: python scripts/parse_mentions.py  # 却用 scripts 包装器
```

✅ **正确做法：**
```yaml
# 方案 A：轻量级
- run: pip install PyYAML requests
- run: python scripts/parse_mentions.py

# 方案 B：完整功能
- run: uv sync
- run: uv run python -m issuelab.cli.mentions
```

## 📚 相关文件

- **CLI 模块实现**: `src/issuelab/cli/`
- **Lightweight workflow**: `.github/workflows/dispatch_agents.yml`
- **Full-featured workflow**: `.github/workflows/orchestrator.yml`

## 🔑 配置要求

### 认证方式

系统支持两种认证方式：

#### 方式 1：GitHub App（推荐 ⭐）

使用 GitHub App 提供更安全的跨仓库访问：

**优势：**
- ✅ 细粒度权限控制
- ✅ Token 自动刷新
- ✅ 支持 fork 仓库
- ✅ 独立审计日志

**配置步骤：**
1. 创建 GitHub App
2. 生成 Private Key
3. 安装到主仓库和 fork 仓库
4. 配置 secrets：
   - `ISSUELAB_APP_ID`
   - `ISSUELAB_APP_PRIVATE_KEY`

📖 **完整指南**：[docs/GITHUB_APP_SETUP.md](../docs/GITHUB_APP_SETUP.md)

#### 方式 2：Personal Access Token (PAT)

快速配置选项（适用于测试）：

**配置步骤：**

1. 创建 PAT：https://github.com/settings/tokens (选择 "classic")
   - 权限：`repo` + `workflow`
2. 添加到仓库：https://github.com/gqy20/IssueLab/settings/secrets/actions
   - 名称：`PAT_TOKEN`
   - 值：粘贴你的 token

⚠️ **为什么不能用 `GITHUB_TOKEN`？**

GitHub 的 `GITHUB_TOKEN` 有安全限制，无法触发其他仓库（包括 fork）的 workflow。
需要使用 PAT 或 GitHub App 来实现跨仓库 dispatch。

---

### 在 Workflow 中的使用

**使用 GitHub App (推荐)：**
```yaml
- name: Generate GitHub App Token
  id: app-token
  uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ secrets.ISSUELAB_APP_ID }}
    private-key: ${{ secrets.ISSUELAB_APP_PRIVATE_KEY }}

- name: Dispatch
  env:
    GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}
  run: python scripts/dispatch_to_users.py ...
```

**使用 PAT：**
```yaml
- name: Dispatch
  env:
    GITHUB_TOKEN: ${{ secrets.PAT_TOKEN }}
  run: python scripts/dispatch_to_users.py ...
```

---

📖 **详细配置指南**：
- GitHub App 配置：[docs/GITHUB_APP_SETUP.md](../docs/GITHUB_APP_SETUP.md)
- Dispatch 配置：[docs/DISPATCH_SETUP.md](../docs/DISPATCH_SETUP.md)

### 支持的 Dispatch 模式

系统支持两种 dispatch 模式：

1. **repository_dispatch** (默认) - 适用于主仓库
2. **workflow_dispatch** (推荐) - 适用于 fork 仓库

在 `agents/_registry/{username}.yml` 中配置：

```yaml
username: your_username
repository: your_username/IssueLab
dispatch_mode: workflow_dispatch  # 对 fork 仓库使用此模式
workflow_file: user_agent.yml
```
