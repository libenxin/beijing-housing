#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Supabase 导出最新数据为静态 JSON 文件，供 GitHub Pages 前端直接加载
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://emlyfidyvqgmuayhxpee.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtbHlmaWR5dnFnbXVheWh4cGVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMjgyNjgsImV4cCI6MjEwNDcwNDI2OH0.eP1g47fw6y9ne0c_7h8PLYhKuIFMDPQQexT2c9b1ufo"

BASE = SUPABASE_URL.rstrip("/") + "/rest/v1"
DAYS = 7  # 只导出最近 N 天，控制文件大小


def log(msg):
    print(msg, flush=True)


def supabase_get(table, params=None):
    url = f"{BASE}/{table}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url += "?" + qs
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def export_latest():
    log("正在从 Supabase 导出数据...")

    # 1. 所有项目 daily 快照（降序）
    daily_rows = supabase_get(
        "daily_project_snapshots",
        {"select": "*", "order": "snapshot_date.desc", "limit": "500"}
    )
    log(f"  daily 快照: {len(daily_rows)} 条")

    if not daily_rows:
        log("  没有数据，退出")
        return

    # 取最近 N 天的日期
    all_dates = sorted(set(r["snapshot_date"] for r in daily_rows), reverse=True)[:DAYS]
    log(f"  日期范围: {all_dates[-1]} ~ {all_dates[0]} (共 {len(all_dates)} 天)")

    # 每个项目的最新 daily
    latest_daily = {}
    for row in daily_rows:
        code = row["project_code"]
        if code not in latest_daily:
            latest_daily[code] = row

    log(f"  项目数: {len(latest_daily)}")

    # 2. 每个项目每天的 house 快照（只取已成交的）
    house_data = {}
    total_houses = 0
    for idx, code in enumerate(latest_daily.keys()):
        house_data[code] = {}
        for date in all_dates:
            try:
                rows = supabase_get(
                    "house_status_snapshots",
                    {
                        "select": "house_key,building,unit,room,house_no,building_area,unit_price,total_price,status",
                        "project_code": f"eq.{code}",
                        "snapshot_date": f"eq.{date}",
                        "status": "in.(已签约,已预订,网上联机备案)",
                        "limit": "2000",
                    }
                )
                if rows:
                    house_data[code][date] = rows
                    total_houses += len(rows)
            except Exception as e:
                log(f"  [警告] {code} {date} 读取失败: {e}")
        if (idx + 1) % 5 == 0:
            log(f"  进度: {idx+1}/{len(latest_daily)} 个项目，已收集 {total_houses} 条房源记录")

    log(f"  房源快照: 共 {total_houses} 条记录")

    # 3. 组装输出
    output = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_date": all_dates[0],
        "projects": {},
    }

    for code, row in latest_daily.items():
        # 过滤出这个项目的历史 daily（只保留最近 N 天）
        proj_daily = [
            {
                "snapshot_date": r["snapshot_date"],
                "signed_count": r.get("signed_count", 0),
                "signed_area": r.get("signed_area", 0),
                "avg_price": r.get("avg_price", 0),
            }
            for r in daily_rows
            if r["project_code"] == code and r["snapshot_date"] in all_dates
        ]
        proj_daily.sort(key=lambda x: x["snapshot_date"])

        output["projects"][code] = {
            "latest": {
                "snapshot_date": row["snapshot_date"],
                "signed_count": row.get("signed_count", 0),
                "signed_area": row.get("signed_area", 0),
                "avg_price": row.get("avg_price", 0),
                "total_count": row.get("total_count", 0),
                "available_count": row.get("available_count", 0),
            },
            "daily_history": proj_daily,
            "houses_by_date": house_data.get(code, {}),
        }

    # 4. 写入文件
    out_file = DATA_DIR / "latest-data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = out_file.stat().st_size / 1024
    log(f"\n导出完成: {out_file} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    export_latest()
