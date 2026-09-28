#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动导入熙区嘉园的每日快照数据（从图片提取的汇总数据）
用于在爬虫跑到之前，先把首页数据补上
用法: python tools/import_xiqu_manual.py
"""
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://emlyfidyvqgmuayhxpee.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtbHlmaWR5dnFnbXVheWh4cGVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMjgyNjgsImV4cCI6MjEwNDcwNDI2OH0.eP1g47fw6y9ne0c_7h8PLYhKuIFMDPQQexT2c9b1ufo"

BASE = SUPABASE_URL.rstrip("/") + "/rest/v1"


def supabase_request(table, method="GET", data=None, params=None, prefer=None, retries=3):
    url = f"{BASE}/{table}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url += "?" + qs
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer
    for i in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")
        except Exception as e:
            print(f"    [supabase 重试 {i+1}] {e}")
            time.sleep(1 + i)
    return 0, "network error"


def import_daily():
    """从图片提取的每日汇总数据（2026-09-27）"""
    # 来自项目首页截图：期房签约统计
    # 住宅：已签约 69 套 / 6116.83㎡ / 69910.44元/㎡
    # 总房源：4栋楼，546套，总面积51090.72㎡

    snapshot_date = "2026-09-27"
    project_code = "xiqu_jiayuan"

    daily_row = {
        "project_code": project_code,
        "snapshot_date": snapshot_date,
        "signed_count": 69,
        "signed_area": 6116.83,
        "avg_price": 69910.44,
        "total_houses": 546,
        "total_area": 51090.72,
    }

    print(f"导入 {project_code} {snapshot_date} 每日快照...")
    print(f"  总套数: 546, 已签约: 69, 均价: 69910.44")

    s, b = supabase_request(
        "daily_project_snapshots", "POST", [daily_row],
        params={"on_conflict": "project_code,snapshot_date"},
        prefer="resolution=merge-duplicates"
    )
    print(f"  状态: {s}")
    if s >= 400:
        print(f"  错误: {b[:500]}")
    else:
        print(f"  导入成功！")
    return s, b


if __name__ == "__main__":
    import_daily()
