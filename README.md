# CSCD 审稿人推荐 Agent

Python 硬过滤 + LangChain 流式精筛的审稿人推荐 Agent。

## 架构

```
阶段一 (pipeline + filters)  → COI 熔断 + 重合度最高档全部入选
阶段二 (pipeline + scoring)  → 拉取发文 + activity_score
阶段三 (chain)               → LLM 语义精筛，JSON 流式输出
```

工具调用结果持久化在 `data/tool_memory.db`（长期记忆）。

## 目录结构

```
reviewer-agent/
├── agent/
│   ├── main.py       # CLI 入口
│   ├── pipeline.py   # 阶段一/二编排
│   ├── chain.py      # 阶段三 LangChain 流式精筛
│   ├── filters.py    # COI + 关键词粗筛
│   ├── scoring.py    # 活跃度评分
│   ├── tools.py      # CSCD 调用 + 长期记忆
│   ├── memory.py     # SQLite 持久化
│   ├── types.py      # 数据结构
│   └── golden_cases.py
├── cscd/client.py    # CSCD API 封装
├── mcp_servers/      # 可选：Cursor MCP 独立调试
├── prompt/system.md
├── mcp.json
└── requirements.txt
```

## 快速开始

```bash
cd reviewer-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 填入 CSCD_API_CODE（或 CSCD_USER/PASSWORD）和 MINIMAX_API_KEY
```

```bash
python -m agent.main \
  --title "基于深度学习的医学图像分割研究" \
  --keywords "深度学习,医学图像,图像分割" \
  --author-org "浙江大学计算机学院"
```

输出为流式 JSON（`{"reviewers": [...]}`）。加 `--include-meta` 可先输出一行 pipeline 元信息。

## CSCD 鉴权

ApiCode 获取接口（约 10 分钟有效）：

```
GET http://sciencechina.cn/cscdboot/CscdService/getApiCode?user=...&password=...
```

业务接口在 Header 中携带 `ApiCode`。客户端会按以下顺序获取：

1. 内存缓存（9 分钟）
2. 环境变量 `CSCD_API_CODE`
3. 调用 `getApiCode` 自动刷新（需配置 `CSCD_USER` / `CSCD_PASSWORD`）

ApiCode 过期时会自动重新获取并重试。

## 环境变量

| 变量 | 说明 |
|------|------|
| `CSCD_API_CODE` | CSCD ApiCode |
| `CSCD_USER` / `CSCD_PASSWORD` | 自动获取 ApiCode |
| `MINIMAX_API_KEY` | MiniMax API Key |
| `MINIMAX_MODEL` | 默认 `MiniMax-M3` |
| `LLM_PROVIDER` | `minimax`、`tokenhub` 或 `openai` |
| `OPENAI_BASE_URL` / `LLM_MODEL` | OpenAI 兼容服务地址及模型名；方舟 Coding Plan 可用 `ark-code-latest` |
| `LANGSMITH_API_KEY` | LangSmith Trace 密钥（选填） |
| `LANGSMITH_PROJECT` | LangSmith 项目名，默认 `cscd-reviewer-agent` |
| `MEMORY_DB_PATH` | 长期记忆数据库路径 |
| `AGENT_RECENT_PAPER_YEARS` | 阶段二拉取近 N 年论文，默认 3 |
| `CSCD_SEARCH_ARTICLES_MAX_PER_SEC` | searchArticles 限流，默认 3/秒 |

## 单独启动 MCP Server

```bash
python mcp_servers/reviewers.py
python mcp_servers/author_info.py
```
