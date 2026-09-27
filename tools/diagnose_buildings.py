#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：获取两个项目的楼栋列表，核对 buildingId，并检查'可售无面积'楼栋的详情链接"""
import re
import sys
from bs4 import BeautifulSoup
import requests

BASE = "http://bjjs.zjw.beijing.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

def get(url, sess):
    try:
        r = sess.get(url, headers=HEADERS, timeout=30)
        r.encoding = "utf-8"
        return r.text if r.status_code == 200 else None
    except Exception as e:
        return None

def parse_buildings(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=re.compile(r"pageId=320833")):
        href = a["href"]
        m = re.search(r"buildingId=(\d+)", href)
        if not m:
            continue
        tr = a.find_parent("tr")
        tds = tr.find_all("td") if tr else []
        name = tds[0].get_text(strip=True) if len(tds) > 0 else "?"
        status = tds[3].get_text(strip=True) if len(tds) > 3 else "?"
        out.append((name, m.group(1), status))
    return out

sess = requests.Session()

print("=" * 60)
print("嘉华珺园 楼栋列表 (ALL_BUILDINGS_URL)")
print("=" * 60)
jiahua_all = f"{BASE}/eportal/ui?pageId=411612&systemId=2&srcId=1&id=7976631&rowcount=16"
html = get(jiahua_all, sess)
if html:
    for name, bid, status in parse_buildings(html):
        print(f"  {name}  buildingId={bid}  status={status}")
else:
    print("  获取失败")

print()
print("=" * 60)
print("长安锦和嘉苑 楼栋列表")
print("=" * 60)
changan_all = f"{BASE}/eportal/ui?pageId=411612&systemId=2&srcId=1&id=7976630&rowcount=16"
html2 = get(changan_all, sess)
if html2:
    for name, bid, status in parse_buildings(html2):
        print(f"  {name}  buildingId={bid}  status={status}")
else:
    print("  获取失败")

print()
print("=" * 60)
print("检查嘉华 1-3# 楼盘表（可售是否带 houseId 链接）")
print("=" * 60)
# 先取嘉华 1-3# 的 buildingId
if html:
    for name, bid, status in parse_buildings(html):
        if "1-3#" in name:
            fp = f"{BASE}/eportal/ui?pageId=320833&systemId=2&categoryId=1&salePermitId=7976631&buildingId={bid}"
            fhtml = get(fp, sess)
            if fhtml:
                # 统计可售格子是否带 houseId
                soup = BeautifulSoup(fhtml, "html.parser")
                divs = soup.find_all("div", style=re.compile(r"background"))
                avail_dom = []
                for d in divs:
                    st = d.get("style", "")
                    if re.search(r"#33CC00", st, re.I):
                        avail_dom.append(d)
                print(f"  1-3# buildingId={bid}, 可售 div 数量: {len(avail_dom)}")
                with_href = 0
                for d in avail_dom:
                    a = d.find("a")
                    if a and a.get("href") and "houseId" in a["href"]:
                        with_href += 1
                print(f"  其中带 houseId 链接的可售: {with_href}")
                # 打印一个可售格子的 HTML
                if avail_dom:
                    print("  样例可售格子 HTML:")
                    print("   ", str(avail_dom[0])[:600])
            else:
                print("  1-3# 楼盘表获取失败")
            break