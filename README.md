# Newsblaette MVP

每日新闻晨报 MVP：采集 AI、全球经济、科技方向的信息源，筛选 10 条，生成每条 150-200 字中文摘要和一句话评价，并记录未成功爬取的信息源地址。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py --sample
```

示例输出会写到 `output/briefing_YYYY-MM-DD.md`。

如果在旧版 PowerShell 里直接 `Get-Content` 看到中文乱码，请用：

```powershell
Get-Content -Raw -Encoding UTF8 output\briefing_YYYY-MM-DD.md
```

## 正式运行

1. 编辑 `.env`：
   - 设置 `OPENAI_API_KEY` 后，会用 OpenAI 生成中文晨报。
   - 设置 `SMTP_*` 后，会邮件推送。
   - 设置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 后，会 Telegram 推送。
   - 设置 `FEISHU_WEBHOOK_URL` 后，会飞书自定义机器人推送；如果机器人开启了签名校验，同时设置 `FEISHU_SECRET`。
2. 编辑 `config/sources.yaml`：
   - 调整信息源、分类、权重、每天候选数量。
   - RSS/API 优先；HTML 源只做静态解析，抓不到会跳过并记录。
3. 执行：

```powershell
.\.venv\Scripts\python.exe run.py
```

不想推送、只想生成文件：

```powershell
.\.venv\Scripts\python.exe run.py --dry-run
```

## 每日 7:30 定时

Windows 任务计划程序：

```powershell
.\scripts\register_windows_task.ps1 -Time "07:30"
```

这个任务会每天调用 `scripts/run_daily.ps1`。脚本会进入项目目录、确保虚拟环境存在、安装依赖并运行晨报程序。

## 输出内容

每次运行都会生成：

- `output/briefing_YYYY-MM-DD.md`：当日晨报
- `data/newsblaette.sqlite3`：已推送 URL 去重记录

晨报底部会列出：

```text
今日未成功爬取的信息源
- Source Name：URL - failure reason
```

## 目前的 MVP 边界

- 不绕过登录、付费墙、反爬限制或动态加载限制。
- 抓不到的信息源会放弃，并进入失败源列表。
- 未配置 OpenAI API key 时会使用本地兜底摘要，适合试跑流程，但质量不等同于 AI 编辑。
- HTML 源是轻量静态解析，长期稳定建议优先替换为 RSS 或 API。
