#!/usr/bin/env python3
"""
DigitalPlat Domain Renewal Checker (Python 完整版)
支持多账号：API_KEY 环境变量可用英文逗号 "," 分隔多个 key
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Any

# ========== 配置 ==========
API_BASE = "https://domain-api.digitalplat.org/api/v1"
RENEWAL_WINDOW_DAYS = 120


# ========== 环境变量 ==========
def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"错误: 请先设置环境变量 {name}", file=sys.stderr)
        sys.exit(1)
    return value


# 读取多个 API_KEY
API_KEYS_RAW = require_env("API_KEY")
API_KEYS = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]
TG_BOT_TOKEN = require_env("TG_BOT_TOKEN")
TG_CHAT_ID = require_env("TG_CHAT_ID")


# ========== 依赖检查 ==========
def check_dependencies() -> None:
    try:
        import cloudscraper  # noqa: F401
        import requests  # noqa: F401
    except ImportError as e:
        print(f"错误: 缺少依赖 {e.name}，运行: pip3 install cloudscraper requests", file=sys.stderr)
        sys.exit(1)


# ========== API 请求 ==========
def fetch_domains(api_key: str) -> Any:
    """
    获取单个账号的域名列表。
    优先使用 cloudscraper 直接请求，失败时回退到同目录 helper 脚本。
    """
    import cloudscraper

    url = f"{API_BASE}/domains"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    # 直接请求
    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "linux", "desktop": True}
        )
        resp = scraper.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"直接请求失败: {e}", file=sys.stderr)

    # 回退 helper
    script_dir = os.path.dirname(os.path.abspath(__file__))
    helper = os.path.join(script_dir, "digitalplat_api_helper.py")

    if os.path.exists(helper):
        print("尝试调用 helper 脚本...", file=sys.stderr)
        result = subprocess.run(
            ["python3", helper, "/domains", f"Bearer {api_key}", "--debug"],
            capture_output=True,
            text=True,
        )
        if result.stderr:
            print("=== CF Debug Output ===", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Helper 调用失败: {result.stderr}", file=sys.stderr)

    raise RuntimeError("无法获取域名列表")


def extract_domain_list(data: Any) -> Tuple[List[dict], str]:
    """从多种可能的 JSON 结构中提取域名数组"""
    if isinstance(data, list):
        return data, "直接数组"
    if isinstance(data, dict):
        if data.get("success") is True and isinstance(data.get("data"), list):
            return data["data"], "{success:true, data:[]}"
        if isinstance(data.get("data"), list):
            return data["data"], "{data:[]}"
        if isinstance(data.get("domains"), list):
            return data["domains"], "{domains:[]}"
    raise ValueError("无法解析 API 响应结构")


def parse_domain_fields(item: dict) -> Optional[Tuple[str, str, str, str, str]]:
    """解析域名字段，支持多种字段名变体"""
    name = item.get("name") or item.get("domain") or ""
    status = item.get("status") or item.get("state") or ""
    expiry = item.get("expiry_date") or item.get("expiry") or item.get("expire") or ""
    slot_type = item.get("slot_type") or item.get("slot") or ""
    lifecycle = item.get("lifecycle_type") or item.get("lifecycle") or item.get("type") or ""
    if not name or name == "null":
        return None
    return name, status, expiry, slot_type, lifecycle


# ========== 到期判断 ==========
def parse_expiry(expiry: str) -> Optional[datetime]:
    """尝试多种格式解析到期时间"""
    if not expiry or expiry.lower() in ("null", "permanent", ""):
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(expiry, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except ValueError:
        pass

    return None


def needs_renewal(expiry: str) -> bool:
    """判断域名是否需要续期（120 天内到期）"""
    dt = parse_expiry(expiry)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    days_left = (dt - now).days
    return days_left <= RENEWAL_WINDOW_DAYS


# ========== 终端输出 ==========
def print_table(domains: List[Tuple[int, str, str, str, str, str]]) -> None:
    """打印终端表格（含账号编号）"""
    header = (
        f"{'账号':<6} {'域名':<30} {'状态':<12} {'到期时间':<12} "
        f"{'Slot Type':<12} {'Lifecycle':<12} {'需续期':<6}"
    )
    sep = (
        "-" * 6 + " " + "-" * 30 + " " + "-" * 12 + " " + "-" * 12 + " "
        + "-" * 12 + " " + "-" * 12 + " " + "-" * 6
    )
    print(header)
    print(sep)

    for acc_idx, name, status, expiry, slot_type, lifecycle in domains:
        renew = "yes" if needs_renewal(expiry) else "no"
        expiry_disp = expiry if len(expiry) <= 12 else expiry[:9] + "..."
        print(
            f"{acc_idx:<6} {name:<30} {status:<12} {expiry_disp:<12} "
            f"{slot_type:<12} {lifecycle:<12} {renew:<6}"
        )


# ========== Telegram 通知 ==========
def send_telegram(text: str) -> None:
    import requests
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()


def send_long_message(lines: List[str]) -> None:
    """发送长消息，超过 3800 字符时分片"""
    message = ""
    for line in lines:
        if len(message) + len(line) > 3800:
            send_telegram(message)
            message = "<b>DigitalPlat 域名检查（续）</b>"
        message += ("\n" if message else "") + line
    if message:
        send_telegram(message)


# ========== 主流程 ==========
def main() -> None:
    check_dependencies()

    if not API_KEYS:
        print("错误: API_KEY 为空", file=sys.stderr)
        sys.exit(1)

    print(f"检测到 {len(API_KEYS)} 个账号", file=sys.stderr)

    # 存储结构: (账号编号, 域名, 状态, 到期时间, slot_type, lifecycle)
    all_domains: List[Tuple[int, str, str, str, str, str]] = []

    # 逐个账号获取
    for idx, api_key in enumerate(API_KEYS, start=1):
        print(f"\n正在获取账号 {idx} 的域名列表...", file=sys.stderr)
        try:
            raw_data = fetch_domains(api_key)
        except Exception as e:
            print(f"账号 {idx} 获取失败，跳过: {e}", file=sys.stderr)
            continue

        try:
            domain_list, structure = extract_domain_list(raw_data)
            print(f"账号 {idx} API 返回: {structure}", file=sys.stderr)
        except ValueError as e:
            print(f"账号 {idx} 解析失败: {e}", file=sys.stderr)
            print(f"原始响应: {json.dumps(raw_data, ensure_ascii=False)}", file=sys.stderr)
            continue

        account_count = 0
        for item in domain_list:
            parsed = parse_domain_fields(item)
            if parsed:
                all_domains.append((idx, *parsed))
                account_count += 1

        print(f"账号 {idx} 已解析 {account_count} 个域名", file=sys.stderr)

    if not all_domains:
        print("警告: 所有账号均未解析到数据", file=sys.stderr)
        sys.exit(0)

    # 打印表格
    print()
    print_table(all_domains)
    print()

    # 构建 Telegram 通知
    notification_lines: List[str] = [
        "<b>DigitalPlat 域名到期检查</b>",
        "",
    ]

    renewal_needed = 0
    total_count = len(all_domains)

    # 按账号分组列出需续期域名
    current_account = 0
    for acc_idx, name, status, expiry, slot_type, lifecycle in all_domains:
        if needs_renewal(expiry):
            renewal_needed += 1
            if acc_idx != current_account:
                notification_lines.append(f"<b>账号 {acc_idx}</b>")
                current_account = acc_idx
            notification_lines.append(f"⚠️ <code>{name}</code> - 到期: {expiry}")

    notification_lines.append("")
    notification_lines.append(f"📊 共 {total_count} 个域名（{len(API_KEYS)} 个账号）")
    notification_lines.append("")
    notification_lines.append(f"⚠️ {renewal_needed} 个域名需在 120 天内续期")
    notification_lines.append("")
    notification_lines.append('🔗 <a href="https://dash.domain.digitalplat.org/dashboard">前往 Dashboard 续期</a>')
    notification_lines.append("")
    notification_lines.append("⚠️ API 未暴露 renewal 接口，需手动在 dashboard 操作")

    if renewal_needed == 0:
        notification_lines.append("✅ 所有域名无需续期")

    # 发送通知
    try:
        send_long_message(notification_lines)
        print("通知已发送")
    except Exception as e:
        print(f"错误: 发送 Telegram 通知失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()