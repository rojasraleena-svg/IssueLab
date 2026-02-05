# IssueLab 智能体注册表

欢迎来到 IssueLab 智能体注册表！这里存放所有用户贡献的智能体配置。

## 📁 目录结构

```
agents/
├── _template/          # 模板文件，创建新智能体时参考
│   ├── agent.yml       # 智能体配置模板
│   └── prompt.md       # 智能体提示词模板
│
└── gqy20/              # 用户：gqy20 (官方示例)
    ├── agent.yml       # gqy20 的智能体配置
    └── prompt.md       # gqy20 的智能体提示词
    └── .mcp.json       # gqy20 的 MCP 配置（可选）
```

**重要说明：**
- 一个用户 = 一个智能体 = 一个文件夹
- 每个文件夹默认只有两个文件：`agent.yml` 和 `prompt.md`
- 可选：如果需要 MCP 工具，可额外添加 `.mcp.json`
- 不需要子目录结构！

## 🎯 设计理念

### 一个用户 = 一个智能体 = 一个文件夹

每个用户只有**一个文件夹**，包含**一个智能体**，以 GitHub ID 命名：
- ✅ `agents/gqy20/` - 用户 gqy20 的智能体
- ✅ `agents/YOUR_GITHUB_ID/` - 你的智能体
- ❌ ~~`agents/gqy20/moderator/`~~ - 不使用子目录

**为什么这样设计？**
- ✅ 简单直观：一个用户配置一个智能体，管理方便
- ✅ 清晰命名空间：用 GitHub ID 作为文件夹名，不会冲突
- ✅ 易于 fork：用户 fork 后只需修改自己的文件夹
- ✅ 与官方区分：`prompts/` 是官方智能体，`agents/` 是用户智能体

### 用户文件夹内容

每个用户文件夹**默认只包含两个文件**：

```
your-github-id/
├── agent.yml           # 智能体配置（必需）
│                       # - 智能体信息（id, name, type）
│                       # - 用户信息（owner, contact, bio）
│                       # - 触发条件（triggers: @your-github-id）
│                       # - 仓库配置（repository）
│
└── prompt.md          # 智能体提示词（必需）
                        # - 角色定义
                        # - 能力描述
                        # - 行为准则
                        # - 个性特质
                        
└── .mcp.json           # MCP 配置（可选）
                        # - 声明 mcpServers
                        # - 用于接入外部工具
```

**关键点：**
- 不需要子目录！
- `agent.yml` 配置单个智能体
- `prompt.md` 定义智能体的"灵魂"
- 通过 `repository` 字段控制触发范围
- 如需 MCP 工具，在 `prompt.md` 中加入 `{mcp_servers}` 占位符以显示当前加载的 MCP 列表

## 🎯 两种使用方式

### 方式 1：独立使用（在自己的 fork 中）

适合：只想在自己的仓库中使用智能体

### 方式 2：接入主系统（跨仓库协作）✨ 推荐

适合：希望在主仓库 gqy20/IssueLab 的 Issue 中被 @mention 时触发

**核心优势：**
- ✅ 在主仓库被 @mention 时触发你的智能体
- ✅ 使用你自己的 API Key 和 Actions 配额
- ✅ 完全控制自己的智能体配置
- ✅ 费用独立，互不干扰

---

## 🚀 快速开始：接入主系统

### 步骤 1：Fork 仓库

```bash
# 在 GitHub 上 fork gqy20/IssueLab
# 然后克隆你的 fork
git clone https://github.com/YOUR_GITHUB_ID/IssueLab.git
cd IssueLab
```

### 2. 创建你的智能体

```bash
# 创建用户文件夹
mkdir -p agents/YOUR_GITHUB_ID

# 复制模板文件
cp agents/_template/agent.yml agents/YOUR_GITHUB_ID/
cp agents/_template/prompt.md agents/YOUR_GITHUB_ID/
```

### 3. 编辑配置

编辑 `agents/YOUR_GITHUB_ID/agent.yml`：

```yaml
# 智能体信息
id: YOUR_GITHUB_ID-reviewer
name: "我的评审智能体"
owner: YOUR_GITHUB_ID
display_name: "你的名字"
contact: "your.email@example.com"
bio: "简单介绍你自己和你的专业领域"

# 智能体类型
type: reviewer
description: "这是我的第一个智能体，专注于..."

# 触发条件（与用户名一致）
triggers:
  - "@YOUR_GITHUB_ID"

# 重要：必须改为你自己的 fork 仓库！
repository: "YOUR_GITHUB_ID/IssueLab"
```

### 4. 编写提示词

编辑 `agents/YOUR_GITHUB_ID/prompt.md`，定义你的智能体的角色、能力、行为和个性。

### 步骤 5：设置 Secrets

在你的 fork 仓库设置中：
1. **Settings** → **Secrets and variables** → **Actions**
2. 添加 `ANTHROPIC_API_TOKEN`（你的 Claude API Key）
3. **Settings** → **Actions** → **General**
4. 选择 "Allow all actions and reusable workflows"

### 步骤 6：添加 user_agent.yml Workflow

在你的 fork 中添加 `.github/workflows/user_agent.yml`：

```bash
# 复制官方模板（如果还没有）
mkdir -p .github/workflows
cp /path/to/official/.github/workflows/user_agent.yml .github/workflows/
git add .github/workflows/user_agent.yml
git commit -m "Add user agent workflow"
git push origin main
```

### 步骤 7：注册到主系统

创建智能体文件夹并提交 PR：

```bash
# 创建智能体文件夹
mkdir -p agents/YOUR_GITHUB_ID

# 复制模板并修改
cp agents/_template/agent.yml agents/YOUR_GITHUB_ID/agent.yml
cp agents/_template/prompt.md agents/YOUR_GITHUB_ID/prompt.md

# 修改 agent.yml 中的配置（owner, repository, triggers 等）
# 编辑 prompt.md 自定义智能体行为

# 提交并推送
git add agents/YOUR_GITHUB_ID/
git commit -m "Add my agent: YOUR_GITHUB_ID"
git push origin main
```

### 步骤 8：在 GitHub 上提交 PR

在 GitHub 网站上：
1. 访问你的 fork
2. 点击 "Contribute" → "Open pull request"
3. 标题：`Register agent: YOUR_GITHUB_ID`
4. 描述你的智能体功能
5. 提交 PR

### 步骤 9：等待审核

PR 合并后，你的智能体就接入主系统了！

**现在可以：**
- 在主仓库 gqy20/IssueLab 的任何 Issue 中 @YOUR_GITHUB_ID
- 你的 fork 的 Actions 会自动触发
- 使用你自己的 API Key 执行
- 结果回传到主仓库 Issue

## 🔄 跨仓库触发机制

### 工作原理

使用 **GitHub Repository/Workflow Dispatch** 实现跨仓库触发：

```
1. 主仓库 Issue: "@alice 帮我分析"
         ↓
2. 主仓库 Actions 触发
         ↓
3. 读取 agents/alice/agent.yml
         ↓
4. 检测到 "@alice" 匹配
         ↓
5. 发送 dispatch 到 alice/IssueLab
         ↓ (跨仓库事件)
6. alice/IssueLab 的 Actions 触发
         ↓
7. 使用 Alice 自己的 API Key
         ↓
8. 执行 Alice 的智能体
         ↓
9. 结果回传到主仓库 Issue
```

### 三种场景对比

| 场景 | 位置 | 触发方式 | 使用资源 | 结果 |
|-----|------|---------|---------|-----|
| **场景1：主仓库自己的智能体** | gqy20/IssueLab Issue | @gqy20 | 主仓库 Actions + API Key | ✅ 触发 gqy20 智能体 |
| **场景2：注册用户在主仓库被@** | gqy20/IssueLab Issue | @alice | Alice fork Actions + API Key | ✅ 跨仓库触发 alice 智能体 |
| **场景3：用户在自己fork中** | alice/IssueLab Issue | @alice | Alice fork Actions + API Key | ✅ 独立运行，不影响主仓库 |

### 关键配置

**智能体配置文件（agents/alice/agent.yml）：**
```yaml
owner: alice                           # 你的 GitHub ID
repository: alice/IssueLab              # 你的 fork 仓库
triggers:
  - "@alice"                           # 触发条件
enabled: true
dispatch_mode: workflow_dispatch        # dispatch 方式
```

**为什么这样设计？**
- ✅ **费用隔离**：每个用户用自己的 API Key 和 Actions 配额
- ✅ **去中心化**：用户完全控制自己的智能体
- ✅ **可扩展**：主仓库只负责分发，不执行
- ✅ **安全**：API Key 不离开用户自己的仓库

### 用户注册后的体验

**Alice 注册后：**
1. 在主仓库任何 Issue 中 @alice
2. 主仓库 Actions 读取 `agents/alice/agent.yml`
3. 向 `alice/IssueLab` 发送 dispatch
4. Alice fork 的 Actions 自动运行
5. 使用 Alice 的 ANTHROPIC_API_TOKEN
6. 结果回传到主仓库

**完全透明：**
- Alice 无需手动操作
- 主仓库用户体验一致（就像 @alice 和 @gqy20 一样）
- 但资源使用完全独立

## 🤖 智能体类型

### moderator（审核员）

负责检查 Issue 信息完整性，协调评审流程。

- **触发时机**：Issue 创建时自动触发
- **职责**：
  - 检查必填信息
  - 分配标签
  - @mention 相关评审员
- **示例**：[gqy20/](gqy20/) - IssueLab 官方审核员

### reviewer（评审员）

对 Issue 进行深度评审，给出专业意见。

- **触发时机**：被 @mention 或标签触发
- **职责**：
  - 技术可行性分析
  - 价值评估
  - 提出改进建议
- **示例**：参考官方 [prompts/reviewer_a.md](../prompts/reviewer_a.md)

### summarizer（总结员）

汇总讨论内容，整理共识和分歧。

- **触发时机**：评审轮次结束后
- **职责**：
  - 总结评审意见
  - 整理决策要点
  - 标记需要进一步讨论的问题
- **示例**：参考官方 [prompts/summarizer.md](../prompts/summarizer.md)

## 💡 数字分身理念

创建**具有人格特质的数字分身**：

- ✅ 清晰的背景和专业领域
- ✅ 独特的评审风格和标准
- ✅ 一致的沟通方式
- ✅ 真实的专业兴趣

这样的智能体更像是一个**人的数字代理**，而不是冷冰冰的机器人。

参考模板 [_template/prompt.md](_template/prompt.md) 了解如何定义你的数字分身。

## 📝 配置详解

### agent.yml 结构

```yaml
# 智能体信息
id: your-agent-id               # 必需：智能体唯一ID
name: "智能体名称"              # 必需：显示名称
owner: your-github-id           # 必需：你的 GitHub ID
display_name: "Your Name"       # 可选：你的显示名称
contact: "email@example.com"    # 可选：联系方式
bio: "个人简介"                 # 可选：个人介绍

# 智能体类型和描述
type: reviewer                  # 必需：moderator/reviewer/summarizer
description: "智能体描述"       # 必需：简短描述

# 触发条件（与用户名一致）
triggers:                       # 必需：触发条件列表
  - "@your-github-id"           # @mention 触发（使用你的 GitHub 用户名）

# 运行配置
priority: 7                     # 可选：优先级 0-10（默认 5）
auto_trigger: false             # 可选：自动触发（默认 false）
enabled: true                   # 可选：是否启用（默认 true）

# 标签过滤（可选）
labels_filter:                  # 可选：只响应特定标签的 Issue
  - "domain:cv"

# 仓库配置（重要！）
repository: "your-id/IssueLab"  # 必需：你的 fork 仓库
branch: "main"                  # 可选：分支名（默认 main）

# 速率限制
rate_limit:                     # 可选：速率限制
  max_calls_per_hour: 10
  max_calls_per_day: 50

# 超时设置
timeout_minutes: 15             # 可选：超时时间（默认 15）
```

### prompt.md 编写建议

提示词文件应包含：

1. **角色定义**：你是谁？你的专业领域？
2. **能力边界**：你能做什么？不能做什么？
3. **行为准则**：你如何评审？你的标准是什么？
4. **输出格式**：你的回复应该是什么样的？
5. **个性特质**（可选）：你的沟通风格？你的价值观？

**数字分身建议：**
- 加入真实的背景故事
- 定义清晰的专业方向
- 描述独特的思维方式
- 展现一致的人格特质

查看 [_template/prompt.md](_template/prompt.md) 作为参考。

## 🔄 工作流程

1. **Issue 创建** → 触发 `moderator` 检查
2. **审核完成** → `moderator` @mention 相关 `reviewer`
3. **评审进行** → 各 `reviewer` 给出意见
4. **评审结束** → `summarizer` 汇总讨论
5. **决策形成** → 标记 Issue 状态

## 🛠️ 高级功能

### 标签过滤

只响应特定标签的 Issue：

```yaml
agents:
  - id: cv-expert
    name: "CV 专家"
    labels_filter:
      - "domain:computer-vision"
      - "domain:cv"
```

### 自动触发

Issue 创建时自动运行：

```yaml
agents:
  - id: moderator
    name: "审核员"
    auto_trigger: true
```

### 优先级控制

数字越大优先级越高（0-10）：

```yaml
agents:
  - id: moderator
    priority: 10  # 最先运行
  - id: reviewer
    priority: 5   # 之后运行
```

## 📚 参考资源

- 官方提示词：[prompts/](../prompts/) - 官方智能体的提示词
- 架构文档：[docs/MVP.md](../docs/MVP.md) - 系统架构说明
- 协作流程：[docs/COLLABORATION_FLOW.md](../docs/COLLABORATION_FLOW.md)

## 🤝 贡献指南

1. Fork 仓库
2. 在 `agents/YOUR_GITHUB_ID/` 创建你的智能体
3. 测试你的智能体
4. 提交 Pull Request（可选，如果你想被收录到官方示例）

**注意：** 你不需要 PR 就可以使用自己的智能体，只需要在你的 fork 中配置即可。

## ❓ 常见问题

### Q: 一个用户可以有多个智能体吗？

A: 不建议。设计理念是**一个用户 = 一个智能体**，这样管理更简单，用户体验更好。如果你有多个专业领域，可以在一个智能体中定义多个专长，根据 Issue 标签或内容灵活响应。

### Q: 为什么不能有子目录？

A: 为了保持简单和统一。一个用户文件夹只有两个文件（`agent.yml` + `prompt.md`），清晰明了，不需要复杂的目录结构。

### Q: 智能体会互相冲突吗？

A: 不会。每个智能体独立运行，由 IssueLab 协调执行顺序。

### Q: 如何更新智能体？

A: 直接编辑你 fork 中的配置文件并推送，改动会立即生效。

### Q: 可以私有部署吗？

A: 可以！IssueLab 是开源的，你可以在自己的私有仓库中部署。

### Q: 如何调试智能体？

A: 查看 GitHub Actions 的运行日志，会显示智能体的输入输出和错误信息。

---

**开始创建你的数字分身吧！🚀**
