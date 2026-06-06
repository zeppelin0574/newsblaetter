# Newsblaette MVP

每日新闻推送 MVP：采集公开新闻源，二次抓取公开原文页面，筛选 10 条新闻，生成每条尽量 300 字以内的概括，并通过 Gmail、飞书、Telegram 等已配置通道推送。

当前项目内包含两套独立简报：

- 【晨报】：每天 07:30，AI、科技、经济、全球政治。
- 【晚报】：每天 22:00，德国政治动态、自然、人文、教育。

周末照常推送。Gmail、飞书、OpenAI、Telegram 继续复用同一个 `.env`。晨报和晚报使用独立数据库去重，互不影响。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py --sample
```

如果在旧版 PowerShell 里直接 `Get-Content` 看到中文乱码，请用：

```powershell
Get-Content -Raw -Encoding UTF8 output\morning\briefing_YYYY-MM-DD.md
Get-Content -Raw -Encoding UTF8 output\evening\briefing_YYYY-MM-DD.md
```

## 两套配置

晨报：

```powershell
.\.venv\Scripts\python.exe run.py --config config\sources_morning.yaml
```

晚报：

```powershell
.\.venv\Scripts\python.exe run.py --config config\sources_evening.yaml
```

只生成文件、不推送：

```powershell
.\.venv\Scripts\python.exe run.py --config config\sources_morning.yaml --dry-run
.\.venv\Scripts\python.exe run.py --config config\sources_evening.yaml --dry-run
```

跳过 OpenAI、使用本地兜底摘要：

```powershell
.\.venv\Scripts\python.exe run.py --config config\sources_morning.yaml --dry-run --no-ai
.\.venv\Scripts\python.exe run.py --config config\sources_evening.yaml --dry-run --no-ai
```

正式抓取和生成，但跳过所有推送通道：

```powershell
.\.venv\Scripts\python.exe run.py --config config\sources_morning.yaml --no-push
.\.venv\Scripts\python.exe run.py --config config\sources_evening.yaml --no-push
```

## 输出与去重

晨报：

- 输出文件：`output/morning/briefing_YYYY-MM-DD.md`
- 去重数据库：`data/morning.sqlite3`
- 标题：`【晨报】每日新闻晨报`
- 筛选策略：不设置硬性类别配额，按综合评分动态选出 10 条。

晚报：

- 输出文件：`output/evening/briefing_YYYY-MM-DD.md`
- 去重数据库：`data/evening.sqlite3`
- 标题：`【晚报】每日新闻晚报`
- 筛选策略：尽量按德国政治动态 3、自然 2、人文 2、教育 3 均衡选取，不足时由其他类别补齐。

默认 `config/sources.yaml` 仍可用于兼容旧的单简报运行方式。`scripts/run_daily.ps1` 也会委托执行晨报脚本。

## 推送配置

编辑 `.env`：

- 设置 `OPENAI_API_KEY` 后，会用 OpenAI 生成更高质量概括。
- 可用 `OPENAI_TIMEOUT_SECONDS` 设置 OpenAI 请求超时，默认 30 秒。
- 设置 `SMTP_*` 后，会邮件推送。
- 设置 `FEISHU_WEBHOOK_URL` 后，会飞书自定义机器人推送。
- 如果飞书机器人开启了签名校验，同时设置 `FEISHU_SECRET`。
- 设置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 后，会 Telegram 推送。

运行时会输出当前阶段，例如抓取、二次抓取原文、筛选、生成摘要、推送。OpenAI、Gmail、Telegram、飞书其中一个通道失败时，会打印对应错误，并继续处理其他通道。未配置 `OPENAI_API_KEY` 时，系统会使用原文抽取式兜底概括；英文来源保留英文，德语来源保留德语，不强制翻译。

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

飞书自定义机器人推荐配置：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-token
FEISHU_SECRET=your_signing_secret
```

`FEISHU_WEBHOOK_URL` 可以填完整 Webhook 地址，也可以只填 `/hook/` 后面的 token。如果机器人未开启签名校验，`FEISHU_SECRET` 留空。`FEISHU_SECRET` 是群自定义机器人的签名密钥，不是开放平台应用的 App Secret。

## Windows 定时任务

一次性注册晨报和晚报：

```powershell
.\scripts\register_briefing_tasks.ps1
```

该脚本会注册：

- `NewsblaetteMorningBriefing`：每天 07:30 执行 `scripts/run_morning.ps1`
- `NewsblaetteEveningBriefing`：每天 22:00 执行 `scripts/run_evening.ps1`

如果旧任务 `NewsblaetteDailyBriefing` 存在，注册脚本会将其禁用，避免晨报重复发送。

手动运行脚本：

```powershell
.\scripts\run_morning.ps1
.\scripts\run_evening.ps1
```

## 信息源边界

- 只使用公开摘要、公开 RSS、公开网页或机构公开页面。
- WSJ/FAZ 仅使用公开可访问内容，不抓取或转发付费正文。
- 不绕过登录、付费墙、反爬限制或动态加载限制。
- 抓不到的源会放弃，并进入失败源列表。
- HTML 源是轻量静态解析，长期稳定建议优先替换为 RSS 或 API。
