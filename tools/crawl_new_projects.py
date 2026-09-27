"""只爬取指定项目列表，用于首次新增项目。
用法: python crawl_new_projects.py code1,code2 --date 2026-09-27
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用 update_today_delta 中的所有函数
from update_today_delta import PROJECTS, run_project, TODAY, YESTERDAY, time

def main():
    codes = sys.argv[1].split(",")
    date_override = None
    if "--date" in sys.argv:
        di = sys.argv.index("--date")
        if di + 1 < len(sys.argv):
            date_override = sys.argv[di + 1]

    # 如果指定了日期，覆盖 TODAY/YESTERDAY（从模块导入的变量需要重新赋值）
    if date_override:
        import update_today_delta as m
        from datetime import datetime, timedelta
        m.TODAY = date_override
        anchored = datetime.strptime(date_override, "%Y-%m-%d")
        m.YESTERDAY = (anchored - timedelta(days=1)).strftime("%Y-%m-%d")

    targets = [p for p in PROJECTS if p["code"] in codes]
    if not targets:
        print(f"未找到项目: {codes}")
        return

    print(f"爬取 {len(targets)} 个项目, 日期: {date_override or TODAY}")

    for idx, p in enumerate(targets):
        run_project(p)
        if idx < len(targets) - 1:
            time.sleep(2)

    print("\nDone!")

if __name__ == "__main__":
    main()
