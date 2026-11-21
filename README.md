<p align="center">
  <img src="https://img.shields.io/badge/DigitalPlat-Domain%20Renewal-blue?style=for-the-badge&logo=google-cloud&logoColor=white" alt="DigitalPlat Domain Renewal">
</p>

<h1 align="center">DigitalPlat 域名自动续期检查</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Shell-脚本-5391FE?style=flat-square&logo=gnubash&logoColor=white">
  <img src="https://img.shields.io/badge/API-DigitalPlat%20v1-00ADD8?style=flat-square">
  <img src="https://img.shields.io/badge/通知-Telegram-26A5E4?style=flat-square&logo=telegram&logoColor=white">
  <img src="https://img.shields.io/badge/依赖-cloudscraper%20%7C%20jq-ff69b4?style=flat-square">
</p>

<p align="center">
  定期检查 DigitalPlat 托管的 <code>.us.kg</code> / <code>.xx.kg</code> 域名到期时间，<br>
  通过 Telegram 通知提醒在 120 天免费续期窗口内操作。
</p>

---

## 📋 功能

- ✅ 通过 DigitalPlat API v1 获取域名列表（cloudscraper 绕过 Cloudflare 验证）
- ✅ 兼容多种 API 响应格式（`{success,data}` / 直接数组 / `{data}`）
- ✅ 检查每个域名的到期时间，自动识别永久到期
- ✅ 标记 120 天窗口内需续期的域名
- ✅ 打印终端表格概览
- ✅ 通过 Telegram Bot 发送通知（支持长消息分片）
- ✅ 通过第三方推送服务（MsgPush）同步推送 Markdown 消息
- ✅ 支持 GitHub Actions 定时运行

---

## 🚀 快速使用

### 通过 GitHub Actions 运行

1. Fork 本仓库到你的 GitHub 账号
2. 进入 **Settings → Secrets and variables → Actions**
3. 添加以下 Secrets：

| Secret | 说明 |
|--------|------|
| `API_KEY` | DigitalPlat API Bearer Token（多个账号用英文逗号分隔） |
| `TG_BOT_TOKEN` | Telegram Bot Token（可选） |
| `TG_CHAT_ID` | 接收通知的 Chat ID（可选） |
| `MSG_PUSH_URL` | 第三方推送接口地址，如 `https://push.example.com/api/push`（可选） |
| `MSG_PUSH_TOKEN` | 第三方推送 Token，以 `Authorization: Bearer <token>` 发送（可选） |
| `MSG_PUSH_TO` | 推送接收人（可选，服务端已配置默认接收人时留空） |

> Telegram 与第三方推送可以只配一个，也可以同时配置；脚本会各发一份，任一失败不影响另一个。
> 工作流同时兼容旧的 `MAGICPUSH_URL` / `MAGICPUSH_TOKEN` Secret 名称（`MSG_PUSH_*` 为空时会回退使用）。

4. 到 **Actions** 页面手动触发一次 `Check DigitalPlat Domains Renew` 工作流验证配置
5. 成功后，工作流会按 Schedule 每天自动运行

**Schedule：** 每天北京时间 07:00（UTC 23:00）

---

### 本地运行

```bash
git clone https://github.com/GaoZitian/digitalplat-renew.git
cd digitalplat-renew

# 安装依赖
pip3 install cloudscraper requests

# 设置环境变量（至少配置 API_KEY；通知渠道按需配置其一或全部）
export API_KEY="***"
export TG_BOT_TOKEN="***"
export TG_CHAT_ID="your_chat_id"
export MSG_PUSH_URL="https://push.example.com/api/push"
export MSG_PUSH_TOKEN="***"

# 运行
python3 check_renew.py
```

---

## ⚙️ GitHub Actions 配置

工作流文件：`.github/workflows/check-digitalplat-renew.yml`

```yaml
name: Check DigitalPlat Domains Renew
on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = 北京时间 07:00
  workflow_dispatch:       # 支持手动触发
```

> 注意： Secrets 在 fork 后需要重新设置，不会从 upstream 继承。

---

## 📦 依赖

| 工具 / 包 | 用途 |
|------|------|
| `cloudscraper` (Python) | 绕过 Cloudflare challenge，获取 API 数据 |
| `jq` | JSON 解析 |
| `python3` ≥ 3.8 | 脚本运行环境 |

脚本内部通过 `cloudscraper` 调用 `digitalplat_api_helper.py` 发起请求，不再直接使用 `curl`（会被 Cloudflare 拦截）。

---

## 📂 项目结构

```
├── renew-digitalplat-subdomains.sh   # 主脚本（域名检查 + Telegram 通知）
├── digitalplat_api_helper.py         # API 请求代理（Cloudflare bypass）
└── .github/workflows/
    └── renew-digitalplat.yml         # GitHub Actions 定时任务
```

---

## 🔗 API 参考

| 端点 | 方法 | 说明 |
|------|------|------|
| `domain-api.digitalplat.org/api/v1/domains` | `GET` | 获取所有域名列表 |

**认证：** `Authorization: Bearer *** `dp_test_xxx`（测试）

> API 未暴露 renewal 端点，续期需在 Dashboard 手动操作。
