#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量更新今日交易信息（不爬面积，只抓状态）
- 嘉华珺园 / 海岄雅苑（长安已删除，跳过）
- 每日运行：抓首页权威值 → daily_project_snapshots
- 抓各楼栋楼盘表状态 → 当天全部已成交房源写入 house_status_snapshots（面积置空）
- 对比昨天快照，打印新增成交 / 退房
- 任一非已售完楼栋抓取失败 → 跳过 house 上传，避免假退房

反爬要点：限流页特征为固定 11912 字节 / 0 个 houseId 链接；
Referer 有无交替重试，内容验证通过才算成功。
"""
import json
import re
import sys
import time
import random
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
import os
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://emlyfidyvqgmuayhxpee.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtbHlmaWR5dnFnbXVheWh4cGVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMjgyNjgsImV4cCI6MjEwNDcwNDI2OH0.eP1g47fw6y9ne0c_7h8PLYhKuIFMDPQQexT2c9b1ufo"

BASE = "http://bjjs.zjw.beijing.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
STATUS_COLORS = {
    "#CCCCCC": "不可售", "#33CC00": "可售", "#FFCC99": "已预订",
    "#FF0000": "已签约", "#FFFF00": "已办理预售项目抵押", "#D2691E": "网上联机备案",
}
SOLD_STATUS = {"已签约", "已预订", "网上联机备案"}
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

_today_override = None
_sys_argv = getattr(sys, "argv", [])
if "--date" in _sys_argv:
    _i = _sys_argv.index("--date")
    if _i + 1 < len(_sys_argv):
        _today_override = _sys_argv[_i + 1]

TODAY = _today_override or datetime.now().strftime("%Y-%m-%d")
anchored = datetime.strptime(TODAY, "%Y-%m-%d")
YESTERDAY = (anchored - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"今日: {TODAY}, 昨日: {YESTERDAY}")

PROJECTS = [
    {"code": "jiahua_junyuan", "name": "嘉华珺园", "pid": "7976631"},
    {"code": "haiyue_yayuan", "name": "海岄雅苑", "pid": "8132032"},
    {"code": "haichenli", "name": "海辰里", "pid": "8132033"},
    {"code": "anhe_yayuan", "name": "安和雅苑", "pid": "8130467"},
    {"code": "zhenyun_yayuan", "name": "臻云雅苑", "pid": "8048704"},
    {"code": "haiyan_yayuan", "name": "海晏雅苑", "pid": "8051500"},
    {"code": "ruijing_yayuan_1", "name": "瑞璟佳苑-1", "pid": "8156312"},
    {"code": "ruijing_yayuan_2", "name": "瑞璟佳苑-2", "pid": "8162284"},
    {"code": "tianjun_heyuan", "name": "天珺和苑", "pid": "8044423"},
    {"code": "xiqu_jiayuan", "name": "熙区嘉园", "pid": "8191996"},
    {"code": "yunhuali", "name": "云华里", "pid": "7949140"},
    {"code": "xianan_wanting", "name": "贤岸湾庭", "pid": "8176764"},
    {"code": "runyue_yayuan_1", "name": "润樾雅苑-1", "pid": "8252613"},
    {"code": "runyue_yayuan_2", "name": "润樾雅苑-2", "pid": "8252612"},
    {"code": "jingyue_jiayuan", "name": "璟悦家园", "pid": "8067898"},
    {"code": "jingrui_jiayuan", "name": "璟瑞家园", "pid": "8195341"},
    {"code": "yusong_jiayuan", "name": "隅颂佳苑", "pid": "8028609"},
    {"code": "shanglin_yunsong", "name": "尚霖云颂佳苑", "pid": "8264052"},
    {"code": "jingxu_jiayuan", "name": "璟序家园", "pid": "8272818"},
    {"code": "manmao_wenyuan", "name": "满茂文苑", "pid": "8248005"},
    {"code": "shuipan_fanglin", "name": "水畔芳邻嘉园", "pid": "8017587"},
]


def fetch_once(url, referer=False):
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = f"{BASE}/eportal/ui?pageId=411612"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_retry(url, retries=5, label="", min_len=20000, require_marker=None):
    """交替带/不带 Referer 抓取；内容需过长度下限并可选标记（识别限流页 11912B/0 houseId）"""
    for i in range(retries):
        try:
            html = fetch_once(url, referer=(i % 2 == 1))
        except Exception as e:
            print(f"    [{label}重试 {i+1}] 异常: {e}")
            time.sleep(0.5 + i * 0.5)
            continue
        if len(html) < min_len:
            print(f"    [{label}重试 {i+1}] 内容过短({len(html)}B), 疑似限流")
            time.sleep(0.5 + i * 0.5)
            continue
        if require_marker and require_marker not in html:
            print(f"    [{label}重试 {i+1}] 缺标记 {require_marker}({len(html)}B), 疑似限流")
            time.sleep(0.5 + i * 0.5)
            continue
        return html
    return None


def fetch_homepage_stats(url, retries=8):
    for i in range(retries):
        try:
            html = fetch_once(url, referer=False)
            if len(html) < 5000:
                print(f"    [首页重试 {i+1}] 内容过短({len(html)}B)")
                time.sleep(2 + i)
                continue
            start = html.find("期房签约统计")
            if start < 0:
                print(f"    [首页重试 {i+1}] 未找到签约统计")
                time.sleep(2 + i)
                continue
            seg = html[start:start + 3000]
            m = re.search(r">\s*住宅\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d,]+)\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d.]+)\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d.]+)\s*<\s*/td", seg)
            if not m:
                print(f"    [首页重试 {i+1}] 住宅行未命中")
                time.sleep(2 + i)
                continue
            return int(m.group(1).replace(",", "")), float(m.group(2)), float(m.group(3))
        except Exception as e:
            print(f"    [首页重试 {i+1}] 异常: {e}")
            time.sleep(5 + i * 2)
    return None


def supabase_request(table, method="GET", data=None, params=None, prefer=None, retries=3):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
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


def get_yesterday_signed(project_code):
    """读取昨天 house_status_snapshots 中已成交房源的 house_key 集合"""
    params = {
        "project_code": f"eq.{project_code}",
        "snapshot_date": f"eq.{YESTERDAY}",
        "select": "house_key,status",
    }
    status, body = supabase_request("house_status_snapshots", "GET", params=params)
    if status != 200:
        print(f"  [读取昨日] status={status}")
        return set()
    rows = json.loads(body) if body else []
    return {r["house_key"] for r in rows}


def parse_unit_room(house_no):
    """解析 '1单元-1001' / '一单元-1001' → (unit, room)"""
    m = re.match(r"([0-9一二三四五六七八九十]+)单元-(\d+)", house_no)
    if not m:
        room = house_no.split("-")[-1] if "-" in house_no else house_no
        return 0, room
    u = m.group(1)
    if u.isdigit():
        unit = int(u)
    elif u == "十":
        unit = 10
    elif "十" in u:
        a, _, b = u.partition("十")
        unit = CN_NUM.get(a, 1) * 10 + CN_NUM.get(b, 0)
    else:
        unit = CN_NUM.get(u, 0)
    return unit, m.group(2)


def parse_buildings(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    buildings = []
    for a in soup.find_all("a", href=re.compile(r"pageId=320833")):
        m = re.search(r"buildingId=(\d+)", a["href"])
        if not m: continue
        tr = a.find_parent("tr")
        if not tr: continue
        tds = tr.find_all("td")
        if len(tds) < 6: continue
        name = tds[0].get_text(strip=True)
        try: count = int(tds[1].get_text(strip=True).replace(",", ""))
        except: count = 0
        try: area = float(tds[2].get_text(strip=True).replace(",", ""))
        except: area = 0
        status_txt = tds[3].get_text(strip=True)
        try: price = float(tds[4].get_text(strip=True).replace(",", ""))
        except: price = 0
        buildings.append({"name": name, "buildingId": m.group(1), "houseCount": count,
                          "houseArea": area, "status": status_txt, "price": price})
    return buildings


def get_building_list(pid, retries=5):
    """抓楼栋列表并解析，解析为 0 栋视为限流页，重试"""
    from bs4 import BeautifulSoup
    url = f"{BASE}/eportal/ui?pageId=411612&systemId=2&srcId=1&id={pid}&rowcount=30"
    for i in range(retries):
        html = fetch_retry(url, retries=1, label="楼栋列表", min_len=20000, require_marker="pageId=320833")
        if html is None:
            time.sleep(1 + i)
            continue
        buildings = parse_buildings(html)
        if buildings:
            return buildings
        print(f"    [楼栋列表 {i+1}] 解析 0 栋, 疑似限流, 重试")
        time.sleep(1 + i)
    return None


def run_project(p):
    print(f"\n===== {p['name']} =====")
    pid = p["pid"]
    project_url = f"{BASE}/eportal/ui?pageId=320794&projectID={pid}&systemID=2&srcId=1"

    # 1) 首页权威值（失败不中断，daily 沿用已有行并只补总量）
    hp = fetch_homepage_stats(project_url)
    if hp:
        hp_count, hp_area, hp_price = hp
        print(f"  [首页] 已签约 {hp_count} 套 / {hp_area}㎡ / {hp_price}元")
    else:
        hp_count = hp_area = hp_price = None
        print("  WARN: 首页解析失败（daily 仅更新楼栋总量，signed 值沿用已有行）")

    # 2) 楼栋列表
    buildings = get_building_list(pid)
    if not buildings:
        print("  ERROR: 楼栋列表抓取失败，跳过该项目")
        return
    total_houses = sum(b["houseCount"] for b in buildings)
    total_area = sum(b["houseArea"] for b in buildings)
    print(f"  [楼栋] {len(buildings)} 栋, 总套数 {total_houses}, 总面积 {total_area:.0f}㎡")
    print("    状态: " + ", ".join(f"{b['name']}={b['status']}" for b in buildings))

    # 3) 昨日快照（提前取，用于 0 格楼栋校验）
    yset = get_yesterday_signed(p["code"])
    print(f"  [昨日快照] {len(yset)} 套")

    # 4) 逐栋抓楼盘表（交替 Referer 重试，验证 houseId 内容）
    from bs4 import BeautifulSoup
    today_signed = []
    failed_buildings = []
    crawlable = [b for b in buildings if b["status"] not in ("已售完", "不可售")]
    for b in crawlable:
        url = f"{BASE}/eportal/ui?pageId=320833&systemId=2&categoryId=1&salePermitId={pid}&buildingId={b['buildingId']}"
        divs = None
        for attempt in range(4):
            html = fetch_retry(url, retries=1, label=f"{b['name']}", min_len=20000)
            if html is None:
                time.sleep(1 + attempt)
                continue
            bsoup = BeautifulSoup(html, "html.parser")
            d = sorted(bsoup.find_all("div", style=re.compile(r"background\s*:\s*#")),
                       key=lambda x: int(x.get("id", "0") or "0"))
            if len(d) > 2 or html.count("houseId=") > 0:
                divs = d
                break
            print(f"    [{b['name']} {attempt+1}] 内容无房源({len(html)}B), 疑似限流, 重试")
            time.sleep(1 + attempt)
        if divs is None:
            print(f"    {b['name']}: 抓取失败")
            failed_buildings.append(b["name"])
            continue
        time.sleep(0.05)
        sold_here = 0
        for div in divs:
            style = div.get("style", "")
            cm = re.search(r"background\s*:\s*(#[0-9A-Fa-f]+)", style)
            if not cm: continue
            color = cm.group(1).upper()
            status_txt = STATUS_COLORS.get(color)
            if not status_txt: continue
            a = div.find("a")
            text = (a.get_text(strip=True) if a else div.get_text(strip=True))
            if not text: continue
            text = text.replace("■", "").strip()
            if not text: continue
            if "单元-" in text:
                house_no = text
                unit, room = parse_unit_room(house_no)
            elif re.match(r"^\d{3,4}$", text):
                house_no = f"1单元-{text}"
                unit, room = 1, text
            else:
                continue
            floor = int(room[:-2]) if len(room) >= 3 and room.isdigit() else 0
            if status_txt in SOLD_STATUS:
                today_signed.append({
                    "building": b["name"], "house_no": house_no,
                    "house_key": f"{b['name']} {house_no}", "unit": unit, "room": room,
                    "floor": floor, "status": status_txt,
                })
                sold_here += 1
        print(f"    {b['name']}: {len(divs)} 格, 已成交 {sold_here}")
        prev_here = sum(1 for k in yset if k.split(" ")[0] == b["name"])
        if sold_here == 0 and prev_here > 0:
            print(f"      WARN: 0 格但昨日该楼栋有 {prev_here} 套成交，判定抓取/解析失败")
            failed_buildings.append(b["name"])
    print(f"  [今日已成交] {len(today_signed)} 套")

    # 5) house 上传判断：任一非已售完楼栋失败 → 跳过 house，避免假退房
    if failed_buildings:
        print(f"  WARN: 楼栋抓取失败 {len(failed_buildings)} 栋: {failed_buildings}，跳过 house 上传避免假退房")
        if hp:
            daily_row = {
                "project_code": p["code"], "snapshot_date": TODAY,
                "signed_count": hp_count, "signed_area": round(hp_area, 2), "avg_price": round(hp_price, 2),
                "total_houses": total_houses, "total_area": round(total_area, 2),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }
            s, b = supabase_request("daily_project_snapshots", "POST", [daily_row],
                                    params={"on_conflict": "project_code,snapshot_date"},
                                    prefer="resolution=merge-duplicates")
            print(f"  [daily] status={s}")
            if s >= 400: print(f"    ERROR: {b[:300]}")
        return

    # 6) 对比昨日（退房仅统计今日成功抓取的楼栋，已售完/失败楼栋不误报）
    today_keys = {h["house_key"] for h in today_signed}
    crawled_names = {h["building"] for h in today_signed}
    new_signed = [h for h in today_signed if h["house_key"] not in yset]
    returned = [k for k in yset if k not in today_keys and k.split(" ")[0] in crawled_names]
    print(f"  [变动] 新增成交 {len(new_signed)} 套, 退房 {len(returned)} 套")
    for h in sorted(new_signed, key=lambda x: (x["building"], x["house_no"]))[:30]:
        print(f"    + {h['building']} {h['house_no']} ({h['status']})")
    for k in sorted(returned)[:20]:
        print(f"    - {k}")

    # 7) 上传 daily（首页成功 upsert 全字段；失败仅 PATCH 总量）
    if hp:
        daily_row = {
            "project_code": p["code"], "snapshot_date": TODAY,
            "signed_count": hp_count, "signed_area": round(hp_area, 2), "avg_price": round(hp_price, 2),
            "total_houses": total_houses, "total_area": round(total_area, 2),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        s, b = supabase_request("daily_project_snapshots", "POST", [daily_row],
                                params={"on_conflict": "project_code,snapshot_date"},
                                prefer="resolution=merge-duplicates")
    else:
        s, b = supabase_request("daily_project_snapshots", "PATCH",
                                {"total_houses": total_houses, "total_area": round(total_area, 2)},
                                params={"project_code": f"eq.{p['code']}", "snapshot_date": f"eq.{TODAY}"})
    print(f"  [daily] status={s}")
    if s >= 400: print(f"    ERROR: {b[:300]}")

    # 8) 上传今日全量已成交房源（面积置空）
    # 注意：anon 角色无 DELETE 权限（DELETE 静默 0 行），故用 on_conflict upsert；
    # 今日全量快照 ⊇ 当日早前部分上传的快照，upsert 后不会残留脏键
    seen = set()
    house_rows = []
    for h in today_signed:
        if h["house_key"] in seen: continue
        seen.add(h["house_key"])
        house_rows.append({
            "project_code": p["code"], "snapshot_date": TODAY,
            "building": h["building"], "house_no": h["house_no"], "house_key": h["house_key"],
            "unit": h["unit"], "room": h["room"], "floor": h["floor"],
            "status": h["status"], "purpose": "住宅", "layout": "",
            "building_area": None, "unit_price": 0, "total_price": 0,
            "area_bucket": None, "extracted_at": datetime.now(timezone.utc).isoformat(),
            "data_source": None,
        })
    for i in range(0, len(house_rows), 500):
        batch = house_rows[i:i+500]
        s, b = supabase_request("house_status_snapshots", "POST", batch,
                                params={"on_conflict": "project_code,snapshot_date,house_key"},
                                prefer="resolution=merge-duplicates")
        print(f"  [house] batch {i//500+1}: status={s} ({len(batch)} 条)")
        if s >= 400: print(f"    ERROR: {b[:300]}")


for idx, p in enumerate(PROJECTS):
    try:
        run_project(p)
    except Exception:
        import traceback
        traceback.print_exc()
    if idx < len(PROJECTS) - 1:
        time.sleep(2)
print("\nDone!")
