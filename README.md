# Newsblaette MVP

每日新闻晨报 MVP：采集 AI、全球经济、科技方向的信息源，筛选 10 条，二次抓取原文页面后生成每条尽量 300 字以内的概括，并记录未成功爬取的信息源地址。

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
   - 可用 `OPENAI_TIMEOUT_SECONDS` 设置 OpenAI 请求超时，默认 30 秒。
   - 设置 `SMTP_*` 后，会邮件推送。
   - 设置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 后，会 Telegram 推送。
   - 设置 `FEISHU_WEBHOOK_URL` 后，会飞书自定义机器人推送；如果机器人开启了签名校验，同时设置 `FEISHU_SECRET`。
2. 编辑 `config/sources.yaml`：
   - 调整信息源、分类、权重、每天候选数量。
   - RSS/API 优先；系统会对最终选中的 10 条新闻再尝试抓取原文页面，抓不到会保留 RSS 摘要并记录失败链接。
3. 执行：

```powershell
.\.venv\Scripts\python.exe run.py
```

不想推送、只想生成文件：

```powershell
.\.venv\Scripts\python.exe run.py --dry-run
```

跳过 OpenAI、使用本地兜底摘要：

```powershell
.\.venv\Scripts\python.exe run.py --dry-run --no-ai
```

正式抓取和生成，但跳过所有推送通道：

```powershell
.\.venv\Scripts\python.exe run.py --no-push
```

推荐排错顺序：

```powershell
.\.venv\Scripts\python.exe run.py --sample
.\.venv\Scripts\python.exe run.py --dry-run --no-ai
.\.venv\Scripts\python.exe run.py --dry-run
.\.venv\Scripts\python.exe run.py
```

运行时会输出当前阶段，例如抓取、二次抓取原文、筛选、生成摘要、推送。OpenAI、Gmail、Telegram、飞书其中一个通道失败时，会打印对应错误，并继续处理其他通道。未配置 `OPENAI_API_KEY` 时，系统会使用原文抽取式兜底概括；英文来源会保留英文，不会自动翻译。

## Gmail 推送

Gmail 推荐配置：

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.name@gmail.com
SMTP_PASSWORD=your_16_digit_app_password
SMTP_FROM=your.name@gmail.com
SMTP_TO=receiver@example.com
SMTP_USE_TLS=true
```

`SMTP_PASSWORD` 应填写 Google 应用专用密码，不要填写 Gmail 登录密码。创建应用专用密码前，需要在 Google 账号安全设置中开启两步验证。

## 飞书推送

飞书自定义机器人配置：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-bot-id
FEISHU_SECRET=
```

`FEISHU_WEBHOOK_URL` 可以填完整 Webhook 地址，也可以只填 `/hook/` 后面的 token。如果机器人开启了签名校验，填入 `FEISHU_SECRET`；未开启时留空。`FEISHU_SECRET` 是群自定义机器人的签名密钥，不是开放平台应用的 App Secret。

正式推送时，如果 `FEISHU_WEBHOOK_URL` 没有被程序读到，会输出 `feishu error`，用于区分“配置没加载”和“飞书服务端拒绝”。

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
