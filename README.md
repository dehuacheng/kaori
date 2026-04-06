# Kaori

**[English](#english)** | **[中文](#中文)**

<details open>
<summary><h2>English</h2></summary>

Personal AI-powered life management app. Self-hosted, privacy-first.

Kaori is a FastAPI backend that tracks meals, weight, workouts, and more — with LLM-powered analysis. All data stays on your machine.

### Features

- **Meal tracking** — Log meals via photo or text. LLM analyzes nutrition (calories, protein, carbs, fat). Supports reprocessing and rollback.
- **Weight tracking** — Multiple entries per day, trend charts, BMR/TDEE calculations.
- **Workout tracking** — Structured logging with exercises, sets, reps, weights. LLM workout summaries with calorie estimation.
- **Exercise catalog** — Standard exercises + custom additions. Identify gym machines from photos via LLM.
- **Timer presets** — Configurable rest/work timers consumed by the iOS app.
- **User profile** — Height, weight, age, macro targets. Dynamic nutrition targets based on body composition.
- **Multi-LLM support** — Claude CLI, Anthropic API, or Codex CLI (ChatGPT). Switchable per-user.
- **Notifications & AI summaries** — Configurable meal/weight reminders. LLM-generated daily and weekly health summaries with persistent storage.
- **Financial accounts** — Track brokerage portfolio value across multiple accounts (Schwab, Fidelity, Moomoo, etc.). Import holdings via screenshot or PDF with LLM extraction. Daily portfolio change card on the feed with live prices via yfinance. Snapshot system for historical values.
- **AI agent chat** — SSE-streaming chat endpoint with agentic tool loop. The agent can query all your kaori data (meals, weight, workouts, portfolio, reminders) via 17 server-side tools. Supports session persistence, cross-session memory, personal prompts, and transcript compaction. Swappable LLM backends (Anthropic, DeepSeek, OpenAI).

### Setup

**Requirements:** Python 3.12+, `claude` CLI (for default LLM mode)

```bash
git clone https://github.com/dehuacheng/kaori.git
cd kaori
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Optional: for Anthropic API mode
pip install -e ".[llm-api]"

# Optional: for AI agent chat
pip install -e ".[agent]"
```

### Running

```bash
# Production
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000

# Test mode (uses separate database, safe for development)
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAORI_TOKEN` | `dev-token` | Bearer token for API auth |
| `KAORI_TEST_MODE` | `0` | Use test database when `1` |
| `KAORI_LLM_MODE` | `claude_cli` | LLM backend: `claude_cli`, `claude_api`, or `codex_cli` |
| `ANTHROPIC_API_KEY` | — | Required for `claude_api` mode and agent chat (Anthropic backend) |
| `KAORI_AGENT_BACKEND` | `anthropic` | Agent chat LLM: `anthropic`, `deepseek`, `openai`, `kimi` |
| `DEEPSEEK_API_KEY` | — | Required for agent chat with DeepSeek backend |

### Architecture

**Feed-first, card-first.** Every feature is a card type. The backend uses a `CARD_LOADERS` registry in `feed_service.py` — adding a new card type means adding one loader function and one dict entry. No hardcoded per-type if-blocks in the feed aggregation.

4-layer separation: **Models** (Pydantic) → **Storage** (SQLite repos) → **Services** (business logic + LLM) → **API** (JSON endpoints).

- SQLite with WAL mode, raw/processed data separation
- LLM results are versioned and rollback-safe
- Bearer token auth (designed for single-user, Tailscale-gated access)
- Unified feed endpoint (`GET /api/feed`) aggregates all card types via registry pattern

### iOS App

The companion iOS app is at [kaori-ios](https://github.com/dehuacheng/kaori-ios).

### Roadmap

- **Personal Document Vault** — Upload and retrieve personal documents (passport, IDs, etc.) with password/Face ID protection. Design in progress: considering both a full LLM assistant mode for rich querying and a static presentation mode for maximum security. May offer both and let users choose based on their LLM setup and risk tolerance.
- **Medical Record Keeper** — Store exam results, lab work, and health records. Acts as your AI-powered PCP, nutritionist, and personal trainer — all in one place.
- **Feed-Based UI Revamp** ✅ — Unified "news feed" timeline with rich cards (Apple Health–inspired), multi-day infinite scroll, daily nutrition progress bars, AI summary cards, iOS 18 Control Center–style add menu, and analytics. 3-tab layout: Home | + | More.
- **Financial Accounts** ✅ — Brokerage portfolio tracking with daily feed card, screenshot/PDF import via LLM, live stock prices, daily snapshots. General financial account model for future credit card and bank account support.
- **Personal AI Assistant (Long-Term Vision)** — The ultimate goal: a personal AI assistant (Kaori by default — pick your own name) that provides comprehensive care across all aspects of your life. Core design principle: **your data stays in your hands**. Self-host or choose a trusted LLM provider. Everything else in the app is completely free and open-source — fork it and vibe-code it to make it yours.

</details>

<details>
<summary><h2>中文</h2></summary>

个人 AI 驱动的生活管理应用。自托管，隐私优先。

Kaori 是一个基于 FastAPI 的后端服务，可追踪饮食、体重、健身等数据，并借助 LLM 进行智能分析。所有数据保存在本地。

### 功能

- **饮食记录** — 通过照片或文字记录饮食。LLM 自动分析营养成分（卡路里、蛋白质、碳水、脂肪）。支持重新分析和回滚。
- **体重追踪** — 每天可记录多次，趋势图表，BMR/TDEE 计算。
- **健身记录** — 结构化记录运动项目、组数、次数、重量。LLM 生成训练摘要和卡路里估算。
- **运动目录** — 标准运动库 + 自定义添加。通过照片让 LLM 识别健身器材。
- **计时器预设** — 可配置的休息/训练计时器，供 iOS 应用使用。
- **用户档案** — 身高、体重、年龄、营养目标。根据身体数据动态计算营养目标。
- **多 LLM 支持** — Claude CLI、Anthropic API 或 Codex CLI (ChatGPT)。可按用户切换。
- **通知与 AI 总结** — 可配置的饮食/体重提醒。LLM 生成每日和每周健康总结，持久化存储。
- **财务账户** — 跨多个券商账户（Schwab、Fidelity、Moomoo 等）追踪投资组合市值。通过截图或 PDF 导入持仓，LLM 自动提取。信息流显示每日组合涨跌卡片，通过 yfinance 获取实时行情。支持每日快照。
- **AI 助手对话** — SSE 流式对话接口，支持 Agent 工具循环。助手可通过 9 个服务端工具查询所有 kaori 数据（饮食、体重、运动、投资、提醒等）。支持会话持久化、跨会话记忆、个性化提示和上下文压缩。可切换 LLM 后端（Anthropic、DeepSeek、OpenAI）。

### 安装

**环境要求：** Python 3.12+，`claude` CLI（默认 LLM 模式需要）

```bash
git clone https://github.com/dehuacheng/kaori.git
cd kaori
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 可选：使用 Anthropic API 模式
pip install -e ".[llm-api]"

# 可选：AI 助手对话功能
pip install -e ".[agent]"
```

### 运行

```bash
# 生产模式
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000

# 测试模式（使用独立数据库，开发安全）
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KAORI_TOKEN` | `dev-token` | API 认证 Bearer token |
| `KAORI_TEST_MODE` | `0` | 设为 `1` 使用测试数据库 |
| `KAORI_LLM_MODE` | `claude_cli` | LLM 后端：`claude_cli`、`claude_api` 或 `codex_cli` |
| `ANTHROPIC_API_KEY` | — | `claude_api` 模式和 AI 助手对话（Anthropic 后端）需要 |
| `KAORI_AGENT_BACKEND` | `anthropic` | AI 助手 LLM 后端：`anthropic`、`deepseek`、`openai`、`kimi` |
| `DEEPSEEK_API_KEY` | — | AI 助手使用 DeepSeek 后端时需要 |

### 架构

**信息流优先，卡片优先。** 每个功能都是一种卡片类型。后端使用 `feed_service.py` 中的 `CARD_LOADERS` 注册表 — 添加新卡片类型只需添加一个加载函数和一行字典注册。信息流聚合中没有硬编码的按类型判断逻辑。

四层分离：**模型**（Pydantic）→ **存储**（SQLite 仓库）→ **服务**（业务逻辑 + LLM）→ **API**（JSON 接口）。

- SQLite WAL 模式，原始数据与处理数据分离
- LLM 结果版本化，支持安全回滚
- Bearer token 认证（单用户设计，通过 Tailscale 网关访问）
- 统一信息流接口（`GET /api/feed`）通过注册表模式聚合所有卡片类型

### iOS 应用

配套 iOS 应用在 [kaori-ios](https://github.com/dehuacheng/kaori-ios)。

### 未来规划

- **个人文档保险库** — 上传和检索个人文档（护照、身份证等），通过密码/Face ID 保护。设计仍在进行中：考虑提供完整的 LLM 助手模式（功能更丰富）和静态展示模式（安全性最高），可能两者都提供，让用户根据自己的 LLM 配置和风险偏好自行选择。
- **医疗记录管理** — 存储体检报告、化验结果等健康档案。充当你的 AI 全科医生、营养师和私人教练 — 一站式服务。
- **信息流式 UI 重构** ✅ — 统一的信息流时间线，支持多日无限滚动、Apple Health 风格的卡片设计、每日营养进度条、AI 总结卡片、iOS 18 控制中心风格的添加菜单、数据分析视图。三标签布局：首页 | + | 更多。
- **财务账户** ✅ — 券商投资组合追踪，信息流每日涨跌卡片，截图/PDF 导入持仓（LLM 提取），实时行情，每日快照。通用财务账户模型，未来支持信用卡和银行账户。
- **个人 AI 助手（终极愿景）** — 最终目标：一个个人 AI 助手（默认叫 Kaori，你也可以自定义名字），全方位照顾你生活的各个方面。核心设计原则：**数据掌握在自己手中**。你需要自行部署或选择信任的 LLM 服务商。应用的其他部分完全免费开源 — 随意 fork，用 AI 编程定制成你自己的版本。

</details>

## License

[MIT](LICENSE)
