"""
TXD CO., LTD — 每日自动化获客系统 🚀
主调度器：搜索 → 入库 → 发邮件 → 跟踪 → 报告

每日自动执行:
  1. 搜索新客户（web search + public data）
  2. 添加到数据库
  3. 筛选10-20个客户发送开发信
  4. 跟踪未回复客户（1月后再次联系）
  5. 生成日报
  6. 导出最新数据库到CSV
"""

import datetime, json, sys, os, importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lead_database import LeadDatabase, LEADS_FILE
from lead_search import run_search_today, generate_search_queries

# ─── Reliable import of email_sender (bypasses .pyc cache) ───
def _load_email_module():
    """Load email_sender functions bypassing stale .pyc cache"""
    path = Path(__file__).parent / "email_sender.py"
    # Set env var so email_sender knows its base dir
    os.environ['AUTO_CRM_DIR'] = str(Path(__file__).parent)
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    from pathlib import Path as _Path
    ns = {
        '__file__': str(path),
        '__name__': 'email_sender_reloaded',
        'Path': _Path,
        'os': os,
    }
    exec(src, ns)
    return ns

_email_ns = _load_email_module()
send_daily_batch = _email_ns['send_daily_batch']
send_development_email = _email_ns['send_development_email']
load_config = _email_ns['load_config']

REPORT_FILE = Path(__file__).parent / "data" / "daily_report.json"


# ─── 步骤1: 搜索新客户 ───

def step_search(search_results=None):
    """
    搜索新客户。
    search_results: 外部传入的搜索结果（由Cowork AI搜索产生）
    """
    print("  📡 步骤1: 搜索潜在客户 ...")

    result = run_search_today(search_results)

    print(f"     ✓ 搜索词: {result['queries_generated']} 个")
    print(f"     ✓ 新增客户: {result['leads_added']} 个")
    return result


# ─── 步骤2: 获取今天要联系的客户 ───

def step_get_todays_leads(target=15):
    """获取今天要联系/跟进的客户"""
    print(f"  📋 步骤2: 筛选今日目标客户 ({target}个) ...")

    db = LeadDatabase()
    leads = db.get_leads_for_today(target)

    print(f"     ✓ 新客户: {len([l for l in leads if l['status']=='new'])} 个")
    print(f"     ✓ 需跟进: {len([l for l in leads if l['status']!='new'])} 个")
    return leads


# ─── 步骤3: 发邮件 ───

def step_send_emails(leads, dry_run=False):
    """发送开发信"""
    print(f"  📧 步骤3: 发送开发信 ({'预览' if dry_run else '实际发送'}) ...")

    config = load_config()
    if not config.get("enabled") and not dry_run:
        print("     ⚠️  邮箱未配置，跳过发信。运行以下命令配置:")
        print("     python email_sender.py --setup")
        return {"sent_count": 0, "skipped": True}

    result = send_daily_batch(leads, dry_run=dry_run)

    print(f"     ✓ 目标: {result['target']} 封")
    if not dry_run:
        print(f"     ✓ 已发: {result['sent_count']} 封")
        if result['failed_count'] > 0:
            print(f"     ❌ 失败: {result['failed_count']} 封")
    else:
        print(f"     📝 预览模式，未实际发送")
    return result


# ─── 主函数 ───

def run_daily(search_results=None, dry_run=False, target=15):
    """
    每日自动化主入口
    - search_results: 可选，外部搜索结果
    - dry_run: True则只预览不发信
    """
    start = datetime.datetime.now()
    today = start.date().isoformat()

    print("\n" + "=" * 55)
    print(f"  🏢 TXD CO., LTD  —  每日自动化获客系统")
    print(f"  📅 {today}")
    print("=" * 55)

    # 步骤1: 搜索
    search = step_search(search_results)

    # 步骤2: 获取客户
    leads = step_get_todays_leads(target)

    # 步骤3: 发邮件
    email_result = {}
    if leads:
        email_result = step_send_emails(leads, dry_run=dry_run)
        # 标记已联系
        if not dry_run and email_result.get("sent_count", 0) > 0:
            db = LeadDatabase()
            for l in leads:
                db.mark_contacted(l['id'])

    # 完成
    elapsed = (datetime.datetime.now() - start).total_seconds()
    db = LeadDatabase()
    stats = db.get_stats()

    report = {
        "date": today,
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": dry_run,
        "search": {
            "queries": search["queries_generated"],
            "new_leads": search["leads_added"],
        },
        "email": {
            "target": target,
            "sent": email_result.get("sent_count", 0),
            "failed": email_result.get("failed_count", 0),
        },
        "database": stats,
        "sources_generated": search.get("sample_queries", [])[:5],
    }

    # 保存报告
    db = LeadDatabase()
    reports = []
    if REPORT_FILE.exists():
        try: reports = json.load(open(REPORT_FILE))
        except: pass
    reports.append(report)
    json.dump(reports[-90:], open(REPORT_FILE, 'w'), indent=2, ensure_ascii=False)

    # 导出最新CSV
    csv_path = db.export_csv()

    # 输出摘要
    print("\n" + "-" * 55)
    print(f"  📊 今日摘要")
    print(f"  ⏱  耗时: {elapsed:.0f} 秒")
    print(f"  🔍 搜索词: {search['queries_generated']} 个")
    print(f"  👤 联系客户: {email_result.get('sent_count', 0)} 个")
    print(f"  📁 数据库总计: {stats['total_leads']} 个客户")
    print(f"     ├ 新客户: {stats['new']}")
    print(f"     ├ 已联系: {stats['contacted']}")
    print(f"     ├ 洽谈中: {stats['negotiating']}")
    print(f"     ├ 已成交: {stats['converted']}")
    print(f"     └ 流失: {stats['lost']}")
    if csv_path:
        print(f"  📎 客户数据已导出到: {csv_path}")
    print("-" * 55)
    print("  ✅ 每日自动化完成！明天将继续运行。")
    print("=" * 55 + "\n")

    return report


# ─── 数据概览（快速查看） ───

def show_dashboard():
    db = LeadDatabase()
    stats = db.get_stats()

    print("\n" + "=" * 50)
    print("  📊 TXD CO., LTD  —  客户开发数据面板")
    print("=" * 50)
    print(f"  📁 客户总数:   {stats['total_leads']}")
    print(f"  🆕 新客户:     {stats['new']}")
    print(f"  📨 已联系:     {stats['contacted']}")
    print(f"  🤝 洽谈中:     {stats['negotiating']}")
    print(f"  ✅ 已成交:     {stats['converted']}")
    print(f"  ❌ 流失:       {stats['lost']}")
    print(f"  💬 回复数:     {stats['replied']}")
    print(f"  📊 今日目标:   {stats['today_target']} 个/天")
    print(f"  📈 转化率:     ", end="")
    if stats['total_leads'] > 0:
        rate = stats['converted'] / stats['total_leads'] * 100
        print(f"{rate:.1f}%")
    else:
        print("N/A")

    # 发信统计
    cfg = load_config()
    if cfg.get("enabled"):
        from email_sender import get_send_stats
        es = get_send_stats()
        print(f"  📧 今日已发:   {es['today_sent']}/{es['daily_limit']}")
        print(f"  📧 本周已发:   {es['week_sent']}")
        print(f"  📧 累计发送:   {es['total_sent']}")
    else:
        print(f"  ⚠️  邮件发送: 未配置")

    print("=" * 50 + "\n")


# ─── 手动添加客户 ───

def manual_add():
    print("\n📝 手动添加客户")
    company = input("公司名称: ").strip()
    person = input("联系人: ").strip()
    email = input("邮箱: ").strip()
    phone = input("电话: ").strip()
    country = input("国家: ").strip()
    source = input("来源 (web/linkedin/b2b/referral): ").strip() or "manual"