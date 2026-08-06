#!/usr/bin/env python3
"""
DigitalPlat Domain Renewal Checker (Python 完整版)
支持多账号：API_KEY 环境变量可用英文逗号 "," 分隔多个 key
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime, timezone
from collections import defaultdict
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


API_KEYS_RAW = require_env("API_KEY")
API_KEYS = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]
TG_BOT_TOKEN = require_env("TG_BOT_TOKEN")
TG_CHAT_ID = require_env("TG_CHAT_ID")
MAGICPUSH_URL = require_env("MAGICPUSH_URL")
MAGICPUSH_TOKEN = require_env("MAGICPUSH_TOKEN")


# ========== 依赖检查 ==========
def check_dependencies() -> None:
    try:
        import cloudscraper  # noqa: F401
        import requests  # noqa: F401
    except ImportError as e:
        print(f"错误: 缺少依赖 {e.name}，运行: pip3 install cloudscraper requests", file=sys.stderr)
        sys.exit(1)


# ========== 脱敏工具（仅用于终端输出） ==========
def mask_domain(name: str) -> str:
    """隐藏域名中第一个 '.' 前的字符，保护隐私"""
    if "." not in name:
        return "***"
    idx = name.find(".")
    return "***" + name[idx:]


# ========== API 请求 ==========
def fetch_domains(api_key: str) -> Any:
    import cloudscraper

    url = f"{API_BASE}/domains"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "linux", "desktop": True}
        )
        resp = scraper.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"直接请求失败: {e}", file=sys.stderr)

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
    dt = parse_expiry(expiry)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    days_left = (dt - now).days
    return days_left <= RENEWAL_WINDOW_DAYS


# ========== 终端输出（脱敏） ==========
def print_table(domains: List[Tuple[int, str, str, str, str, str]]) -> None:
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
        masked = mask_domain(name)
        print(
            f"{acc_idx:<6} {masked:<30} {status:<12} {expiry_disp:<12} "
            f"{slot_type:<12} {lifecycle:<12} {renew:<6}"
        )

# ========== MagicPush 通知（不脱敏） ==========
def send_magicpush(text: str) -> None:
    if not MAGICPUSH_URL or not MAGICPUSH_TOKEN:
        print("未配置MagicPush信息，跳过MagicPush通知")
        return
    
    url = MAGICPUSH_URL
    headers = {
        "Authorization": f"Bearer {MAGICPUSH_TOKEN}",
        "Accept": "application/json"
    }
    payload = {
        "title": "DigitalPlat 域名续期检测",
        "content": text,
        "type": "text"
    }
    data = json.dumps(payload).encode("utf-8")
    resp = requests.post(url, data=data, headers=headers, timeout=30)
    resp.raise_for_status()
    
# ========== Telegram 通知（不脱敏） ==========
def send_telegram(text: str) -> None:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置TG通知信息，跳过TG通知")
        return
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()

def sendMSG(text: str) -> None:
    send_telegram(text)
    send_magicpush(text)
    
def send_long_message(lines: List[str]) -> None:
    message = ""
    for line in lines:
        if len(message) + len(line) > 3800:
            sendMSG(message)
            message = "<b>DigitalPlat 域名检查（续）</b>"
        message += ("\n" if message else "") + line
    if message:
        sendMSG(message)


# ========== 主流程 ==========
def main() -> None:
    check_dependencies()

    if not API_KEYS:
        print("错误: API_KEY 为空", file=sys.stderr)
        sys.exit(1)

    print(f"检测到 {len(API_KEYS)} 个账号", file=sys.stderr)

    # 存储结构: (账号编号, 原始域名, 状态, 到期时间, slot_type, lifecycle)
    all_domains: List[Tuple[int, str, str, str, str, str]] = []

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

    # 终端打印：脱敏
    print()
    print_table(all_domains)
    print()

    # ========== 构建 Telegram 通知 ==========
    # 按账号分组收集所有域名
    domains_by_account: dict[int, List[Tuple[str, bool]]] = defaultdict(list)
    renewal_needed = 0
    total_count = len(all_domains)

    for acc_idx, name, status, expiry, slot_type, lifecycle in all_domains:
        need = needs_renewal(expiry)
        if need:
            renewal_needed += 1
        domains_by_account[acc_idx].append((name, need))

    # 构建消息
    notification_lines: List[str] = [
        "<b>DigitalPlat 域名到期检查</b>",
        "",
    ]

    for acc_idx in sorted(domains_by_account.keys()):
        notification_lines.append(f"<b>账号 {acc_idx}</b>")
        for name, need in domains_by_account[acc_idx]:
            status_text = "⚠️ 需续期" if need else "✅ 无需续期"
            notification_lines.append(f"<code>{name}</code>：{status_text}")
        notification_lines.append("")

    notification_lines.append(f"📊 共 {total_count} 个域名（{len(API_KEYS)} 个账号）")
    notification_lines.append(f"⚠️ {renewal_needed} 个域名需在 120 天内续期")
    notification_lines.append("")
    notification_lines.append('🔗 <a href="https://dash.domain.digitalplat.org/dashboard">前往 Dashboard 续期</a>')
    notification_lines.append("")
    notification_lines.append("⚠️ API 未暴露 renewal 接口，需手动在 dashboard 操作")

    # 发送通知
    try:
        send_long_message(notification_lines)
        print("通知已发送")
    except Exception as e:
        print(f"错误: 发送 Telegram 通知失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()