#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首次爬取小区（通用版）：类型①楼栋详情全量(含面积) + 类型③首页概览→daily_project_snapshots
用法:
  python tools/first_crawl.py --pid 8132033 --name 海辰里 --code haichenli \
      --district 海淀区 --location 四五环之间

产物:
  1. assets/{code}-data.js   前端详情数据（全部房源；可售且有真实面积的才带面积）
  2. Supabase 写入:
     - projects           小区基础信息（upsert, on_conflict=code）
     - daily_project_snapshots  首页「期房签约统计」住宅行权威三值（③，与日度更新同一段代码）
     - house_status_snapshots   已成交房源全量（含官方面积）
"""
import argparse
import json
import re
import time
import random
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("需要 bs4: pip install beautifulsoup4")
    raise

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


def fetch_once(url, referer=False):
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = f"{BASE}/eportal/ui?pageId=411612"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_retry(url, retries=8, label="", min_len=20000, require_marker=None):
    """交替带/不带 Referer 抓取；内容过长度下限且含标记才成功（识别限流页 11912B/0 houseId）"""
    for i in range(retries):
        try:
            html = fetch_once(url, referer=(i % 2 == 1))
        except Exception as e:
            print(f"    [{label}重试 {i+1}] 异常: {e}")
            time.sleep(6 + i * 4)
            continue
        if len(html) < min_len:
            print(f"    [{label}重试 {i+1}] 内容过短({len(html)}B), 疑似限流")
            time.sleep(6 + i * 4)
            continue
        if require_marker and require_marker not in html:
            print(f"    [{label}重试 {i+1}] 缺标记 {require_marker}({len(html)}B), 疑似限流")
            time.sleep(6 + i * 4)
            continue
        return html
    return None


def fetch_homepage_stats(url, retries=8):
    """③ 首页「期房签约统计」住宅行权威三值 —— 首次爬取与日度更新共用"""
    for i in range(retries):
        try:
            html = fetch_once(url, referer=False)
            if len(html) < 5000:
                print(f"    [首页重试 {i+1}] 内容过短({len(html)}B)")
                time.sleep(5 + i * 2)
                continue
            start = html.find("期房签约统计")
            if start < 0:
                print(f"    [首页重试 {i+1}] 未找到签约统计")
                time.sleep(5 + i * 2)
                continue
            seg = html[start:start + 3000]
            m = re.search(r">\s*住宅\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d,]+)\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d.]+)\s*<\s*/td\s*>\s*<td[^>]*>\s*([\d.]+)\s*<\s*/td", seg)
            if not m:
                print(f"    [首页重试 {i+1}] 住宅行未命中")
                time.sleep(5 + i * 2)
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
            time.sleep(2 + i * 2)
    return 0, "network error"


def parse_unit_room(house_no):
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
    soup = BeautifulSoup(html, "html.parser")
    buildings = []
    seen = set()
    # 第一遍：有楼盘表链接的在售楼栋
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
        seen.add(name)
    # 第二遍：补充已售完/不可售（无楼盘表链接，href 为 #）的楼栋，仅保留楼栋级数据
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4: continue
        name = tds[0].get_text(strip=True)
        if not name or name in seen or not re.search(r"[\d]+[#－\-]", name): continue
        status_txt = tds[3].get_text(strip=True)
        if status_txt not in ("已售完", "不可售"): continue
        try: count = int(tds[1].get_text(strip=True).replace(",", ""))
        except: count = 0
        try: area = float(tds[2].get_text(strip=True).replace(",", ""))
        except: area = 0
        buildings.append({"name": name, "buildingId": None, "houseCount": count,
                          "houseArea": area, "status": status_txt, "price": 0})
        seen.add(name)
    return buildings


def get_building_list(pid, retries=8):
    url = f"{BASE}/eportal/ui?pageId=411612&systemId=2&srcId=1&id={pid}&rowcount=30"
    for i in range(retries):
        html = fetch_retry(url, retries=1, label="楼栋列表", min_len=20000, require_marker="pageId=320833")
        if html is None:
            time.sleep(3 + i * 2)
            continue
        buildings = parse_buildings(html)
        if buildings:
            return buildings
        print(f"    [楼栋列表 {i+1}] 解析 0 栋, 疑似限流, 重试")
        time.sleep(3 + i * 2)
    return None


def parse_floorplan(html):
    """楼盘表页：提取全部房源（含 houseId、状态、楼层）"""
    soup = BeautifulSoup(html, "html.parser")
    house_id_map = {}
    for a in soup.find_all("a", href=re.compile(r"houseId=")):
        m = re.search(r"houseId=(\d+)&houseNo=([^&]+)", a["href"])
        if m:
            house_id_map[m.group(2)] = m.group(1)
    divs = sorted(soup.find_all("div", style=re.compile(r"background\s*:\s*#")),
                  key=lambda d: int(d.get("id", "0") or "0"))
    houses = []
    for div in divs:
        style = div.get("style", "")
        color_m = re.search(r"background\s*:\s*(#[0-9A-Fa-f]+)", style)
        if not color_m: continue
        color = color_m.group(1).upper()
        status = STATUS_COLORS.get(color)
        if not status: continue
        a = div.find("a")
        text = (a.get_text(strip=True) if a else div.get_text(strip=True))
        if not text: continue
        text = text.replace("■", "").strip()
        if not text: continue
        raw_text = text
        if "单元-" in text:
            house_no = text
            unit, room = parse_unit_room(house_no)
        elif re.match(r"^\d{3,4}$", text):
            house_no = f"1单元-{text}"
            unit, room = 1, text
        else:
            continue
        floor = int(room[:-2]) if len(room) >= 3 and room.isdigit() else 0
        house_id = (house_id_map.get(house_no)
                    or house_id_map.get(urllib.parse.quote(house_no))
                    or house_id_map.get(raw_text)
                    or house_id_map.get(urllib.parse.quote(raw_text)))
        houses.append({"houseNo": house_no, "rawHouseNo": raw_text, "unit": unit,
                       "room": room, "floor": floor, "status": status, "houseId": house_id})
    return houses


def fetch_house_detail(house_id, house_no, pid):
    """房源详情页：建筑面积 / 户型 / 按建筑面积拟售单价"""
    hno_enc = urllib.parse.quote(house_no, safe="")
    url = f"{BASE}/eportal/ui?pageId=373432&houseId={house_id}&houseNo={hno_enc}&categoryId=1&salePermitId={pid}&systemId=2"
    html = fetch_retry(url, retries=6, label="详情", min_len=1500, require_marker="建筑面积")
    if not html:
        return None
    txt = re.sub(r'<[^>]+>', ' ', html)
    txt = re.sub(r'\s+', ' ', txt)
    m_area = re.search(r'建筑面积\s*([\d.]+)', txt)
    m_layout = re.search(r'户\s*型\s*(\S+)', txt)
    m_price = re.search(r'按建筑面积拟售单价\s*([\d.]+)', txt)
    return {
        "buildingArea": int(round(float(m_area.group(1)))) if m_area else 0,
        "layout": m_layout.group(1) if m_layout else "",
        "unitPrice": int(round(float(m_price.group(1)))) if m_price else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--district", required=True)
    ap.add_argument("--location", required=True)
    ap.add_argument("--date", default="", help="快照日期 YYYY-MM-DD，默认今天")
    args = ap.parse_args()

    pid = args.pid
    project_url = f"{BASE}/eportal/ui?pageId=320794&projectID={pid}&systemID=2&srcId=1"
    output = ROOT / "assets" / f"{args.code}-data.js"
    today = args.date or time.strftime("%Y-%m-%d")

    # 1) ③ 首页概览 + 项目信息
    print("1. 首页（类型③）...")
    hp = fetch_homepage_stats(project_url)
    if hp:
        hp_count, hp_area, hp_price = hp
        print(f"  [首页权威] 已签约 {hp_count} 套 / {hp_area}㎡ / {hp_price}元")
    else:
        print("  WARN: 首页权威值抓取失败（daily 将改用明细反推）")
        hp = None
    html = fetch_retry(project_url, retries=6, label="项目页", min_len=10000)
    info = {}
    if html:
        for tr in BeautifulSoup(html, "html.parser").find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                info[tds[0].get_text(strip=True)] = tds[1].get_text(strip=True)

    # 2) 楼栋列表
    print("2. 楼栋列表...")
    buildings = get_building_list(pid)
    if not buildings:
        print("ERROR: 楼栋列表抓取失败"); return
    print(f"  [楼栋] {len(buildings)} 栋, 总套数 {sum(b['houseCount'] for b in buildings)}")
    print("    状态: " + ", ".join(f"{b['name']}={b['status']}" for b in buildings))

    # 3) 逐栋爬楼盘表全量 + 可售房源抓详情（①）
    print("3. 逐栋爬取（类型①）...")
    buildings_data = []
    for i, b in enumerate(buildings):
        print(f"\n  [{i+1}/{len(buildings)}] {b['name']} ({b['status']})")
        if b["status"] in ("已售完", "不可售"):
            buildings_data.append({**b, "houses": []})
            print("    [已售完/不可售] 不生成房源")
            continue
        url = f"{BASE}/eportal/ui?pageId=320833&systemId=2&categoryId=1&salePermitId={pid}&buildingId={b['buildingId']}"
        floor_html = None
        for attempt in range(6):
            h = fetch_retry(url, retries=1, label=f"{b['name']}", min_len=20000)
            if h is None:
                time.sleep(3 + attempt * 2)
                continue
            if h.count("houseId=") > 0 or len(re.findall(r"background\s*:\s*#[0-9A-Fa-f]+", h)) > 2:
                floor_html = h
                break
            print(f"    [{b['name']} {attempt+1}] 内容无房源({len(h)}B), 疑似限流, 重试")
            time.sleep(3 + attempt * 2)
        if floor_html is None:
            print(f"    {b['name']}: 楼盘表抓取失败, 跳过")
            buildings_data.append({**b, "houses": []})
            continue
        time.sleep(random.uniform(0.4, 0.8))
        houses = parse_floorplan(floor_html)
        sc = {}
        for h in houses:
            sc[h["status"]] = sc.get(h["status"], 0) + 1
        for h in houses:
            h["buildingArea"] = 0
            h["unitPrice"] = int(b["price"])
            h["totalPrice"] = 0
            h["layout"] = ""
            h["purpose"] = "住宅"
            h["source"] = None
        details_to_fetch = [h for h in houses if h["status"] == "可售" and h.get("houseId")]
        print(f"    楼盘表: {len(houses)} 套 {sc}, 可售待抓面积: {len(details_to_fetch)}")
        for j, h in enumerate(details_to_fetch):
            detail = fetch_house_detail(h["houseId"], h.get("rawHouseNo") or h["houseNo"], pid)
            if detail and detail["buildingArea"] > 0:
                h["buildingArea"] = detail["buildingArea"]
                h["unitPrice"] = detail["unitPrice"] or int(b["price"])
                h["layout"] = detail["layout"]
                h["totalPrice"] = int(h["buildingArea"] * h["unitPrice"])
                h["source"] = "official"
            time.sleep(random.uniform(0.8, 1.4))
            if (j + 1) % 20 == 0:
                print(f"      进度: {j+1}/{len(details_to_fetch)}")
        buildings_data.append({**b, "houses": houses})

    # 4) 统计
    print("\n4. 统计...")
    total_signed = total_signed_area = total_signed_amount = 0
    official_signed = available_with_area = 0
    for b in buildings_data:
        for h in b["houses"]:
            if h["status"] in SOLD_STATUS:
                total_signed += 1
                if h["buildingArea"] > 0:
                    total_signed_area += h["buildingArea"]
                    total_signed_amount += h["buildingArea"] * h["unitPrice"]
                    if h["source"] == "official":
                        official_signed += 1
            elif h["status"] == "可售" and h["buildingArea"] > 0 and h["source"] == "official":
                available_with_area += 1
    avg_price = total_signed_amount / total_signed_area if total_signed_area > 0 else 0
    print(f"  总已签约: {total_signed}, 有真实面积 {official_signed}")
    print(f"  已签约面积: {total_signed_area:.0f}㎡, 均价: {avg_price:.2f}")
    print(f"  可售且真实面积: {available_with_area} 套")
    total_houses = sum(b["houseCount"] for b in buildings_data)
    total_area = sum(b["houseArea"] for b in buildings_data)

    # 5) 写前端 data 文件
    print("\n5. 写入前端数据文件...")
    out = {
        "project": {
            "name": args.name, "code": args.code,
            "permitNo": info.get("预售许可证编号", ""),
            "permitDate": info.get("发证日期", "").replace("/", "-"),
            "developer": info.get("开发企业", ""),
            "address": info.get("坐落位置", ""),
            "extractedAt": today, "sourceUrl": project_url,
            "overview": {
                "signedCount": total_signed, "signedArea": round(total_signed_area, 2),
                "avgPrice": round(avg_price, 2), "totalCount": total_houses,
            },
        },
        "buildings": [
            {"name": b["name"], "houseCount": b["houseCount"], "totalArea": b["houseArea"],
             "status": b["status"], "price": int(b["price"]),
             "houses": [{"houseNo": h["houseNo"], "unit": h["unit"], "room": h["room"],
                         "floor": h["floor"], "status": h["status"], "purpose": h.get("purpose", "住宅"),
                         "layout": h.get("layout", ""), "buildingArea": h.get("buildingArea", 0),
                         "unitPrice": h.get("unitPrice", int(b["price"])),
                         "totalPrice": h.get("totalPrice", 0),
                         "areaBucket": f"{h.get('buildingArea', 0)}平" if h.get("buildingArea", 0) > 0 else "",
                         "source": h.get("source")}
                        for h in b["houses"]]}
            for b in buildings_data
        ],
    }
    js = "window.PROJECT_DATA = " + json.dumps(out, ensure_ascii=False, indent=2) + ";\n"
    output.write_text(js, encoding="utf-8")
    print(f"  已写入: {output} ({len(js)} 字符)")

    # 6) 上传 Supabase
    print("\n6. 上传 Supabase...")
    # projects
    proj_row = {
        "code": args.code, "name": args.name,
        "district": args.district, "location": args.location,
        "permit_no": info.get("预售许可证编号", ""),
        "permit_date": info.get("发证日期", "").replace("/", "-") or None,
        "developer": info.get("开发企业", ""),
        "address": info.get("坐落位置", ""),
        "building_count": len(buildings_data), "house_count": total_houses,
        "source_url": project_url,
    }
    s, b = supabase_request("projects", "POST", [proj_row],
                            params={"on_conflict": "code"}, prefer="resolution=merge-duplicates")
    print(f"  [projects] status={s}")
    if s >= 400: print(f"    ERROR: {b[:300]}")
    # daily（③ 首页权威值；抓不到则明细反推兜底）
    if hp:
        d_count, d_area, d_price = hp_count, hp_area, hp_price
        print(f"  [daily] 首页权威值 {d_count} / {d_area} / {d_price}")
    else:
        d_count, d_area, d_price = total_signed, round(total_signed_area, 2), round(avg_price, 2)
        print(f"  [daily] 首页失败, 兜底明细 {d_count} / {d_area} / {d_price}")
    daily_row = {
        "project_code": args.code, "snapshot_date": today,
        "signed_count": d_count, "signed_area": d_area, "avg_price": d_price,
        "total_houses": total_houses, "total_area": round(total_area, 2),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    s, b = supabase_request("daily_project_snapshots", "POST", [daily_row],
                            params={"on_conflict": "project_code,snapshot_date"},
                            prefer="resolution=merge-duplicates")
    print(f"  [daily] status={s}")
    if s >= 400: print(f"    ERROR: {b[:300]}")
    # house（已成交全量，含官方面积）
    house_rows = []
    for b in buildings_data:
        for h in b["houses"]:
            if h["status"] not in SOLD_STATUS:
                continue
            area = h["buildingArea"] if h["buildingArea"] > 0 else None
            house_rows.append({
                "project_code": args.code, "snapshot_date": today,
                "building": b["name"], "house_no": h["houseNo"],
                "house_key": f"{b['name']} {h['houseNo']}",
                "unit": h["unit"], "room": h["room"], "floor": h["floor"],
                "status": h["status"], "purpose": "住宅", "layout": h.get("layout", ""),
                "building_area": area,
                "unit_price": h.get("unitPrice", 0) if area else 0,
                "total_price": h.get("totalPrice", 0) if area else 0,
                "area_bucket": h.get("areaBucket", "") or None,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "data_source": "official" if area else None,
            })
    for i in range(0, len(house_rows), 500):
        batch = house_rows[i:i+500]
        s, b = supabase_request("house_status_snapshots", "POST", batch,
                                params={"on_conflict": "project_code,snapshot_date,house_key"},
                                prefer="resolution=merge-duplicates")
        print(f"  [house] batch {i//500+1}: status={s} ({len(batch)} 条)")
        if s >= 400: print(f"    ERROR: {b[:300]}")
    print("\nDone!")


if __name__ == "__main__":
    main()
