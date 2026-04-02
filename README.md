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
| `ANTHROPIC_API_KEY` | — | Required only for `claude_api` mode |

### Architecture

4-layer separation: **Models** (Pydantic) → **Storage** (SQLite repos) → **Services** (business logic + LLM) → **API** (JSON endpoints).

- SQLite with WAL mode, raw/processed data separation
- LLM results are versioned and rollback-safe
- Bearer token auth (designed for single-user, Tailscale-gated access)

### iOS App

The companion iOS app is at [kaori-ios](https://github.com/dehuacheng/kaori-ios).

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
| `ANTHROPIC_API_KEY` | — | 仅 `claude_api` 模式需要 |

### 架构

四层分离：**模型**（Pydantic）→ **存储**（SQLite 仓库）→ **服务**（业务逻辑 + LLM）→ **API**（JSON 接口）。

- SQLite WAL 模式，原始数据与处理数据分离
- LLM 结果版本化，支持安全回滚
- Bearer token 认证（单用户设计，通过 Tailscale 网关访问）

### iOS 应用

配套 iOS 应用在 [kaori-ios](https://github.com/dehuacheng/kaori-ios)。

</details>

## License

[MIT](LICENSE)
