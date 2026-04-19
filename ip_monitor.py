#!/usr/bin/env python3
# =============================================================================
# ip-monitor.py — グローバルIPアドレス監視スクリプト
# =============================================================================
# 概要:
#   2つの外部サービスからグローバルIPを取得し、日時とともにログに記録する。
#
# 使い方:
#   python3 ip-monitor.py
#
# cronで1時間ごとに実行する例:
#   0 * * * * /usr/bin/python3 /opt/ip-monitor.py >> /var/log/ip-monitor.log 2>&1
# =============================================================================

import urllib.request
import urllib.error
from datetime import datetime

TIMEOUT = 10
SERVICES = [
    ("ifconfig.io", "https://ifconfig.io"),
    ("ipconfig.io", "https://ipconfig.io"),
]


def fetch_ip(url: str) -> str:
    """指定URLからグローバルIPアドレスを取得する。失敗時は空文字を返す。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode().strip().split("\n")[0]
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def determine_status(results: list[tuple[str, str]]) -> str:
    """取得結果リストからステータスを判定する。"""
    ips = [ip for _, ip in results]

    if all(ips):
        return "MATCH" if len(set(ips)) == 1 else "MISMATCH"
    if not any(ips):
        return "BOTH_FAILED"
    return "PARTIAL"


def main() -> None:
    log_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- IPアドレス取得 ---
    results = [(name, fetch_ip(url)) for name, url in SERVICES]

    # --- ステータス判定 ---
    status = determine_status(results)

    # --- ログ出力 ---
    parts = " ".join(
        f"{name}={ip if ip else '(unreachable)'}" for name, ip in results
    )
    print(f"[{log_date}] {parts} status={status}")


if __name__ == "__main__":
    main()
