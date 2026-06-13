"""
TXD CO., LTD — Automated Customer Search Module
Searches importers, customs data (free), LinkedIn, B2B platforms.
每天自动搜索 → 生成搜索词 → 入库
"""

import datetime, json
from lead_database import LeadDatabase

db = LeadDatabase()

SEARCH_TOPICS = [
    {"product": "PP hollow sheet", "buyer": ["importer", "distributor", "wholesaler", "buyer"]},
    {"product": "corrugated plastic sheet", "buyer": ["importer", "distributor", "wholesaler"]},
    {"product": "PP hollow board", "buyer": ["manufacturer", "importer", "procurement"]},
    {"product": "plastic packaging sheet", "buyer": ["importer", "buyer", "distributor"]},
    {"product": "fluted plastic sheet", "buyer": ["importer", "wholesaler"]},
    {"product": "polypropylene twinwall sheet", "buyer": ["importer", "distributor"]},
    {"product": "plastic box manufacturer", "buyer": ["importer", "wholesaler", "buyer"]},
    {"product": "reusable plastic container", "buyer": ["importer", "distributor"]},
    {"product": "ESD packaging material", "buyer": ["importer", "procurement"]},
    {"product": "plastic corrugated box", "buyer": ["importer", "wholesaler", "buyer"]},
]

COUNTRY_KEYWORDS = {
    "USA": ["USA", "United States"],
    "Germany": ["Germany", "Deutschland"],
    "UK": ["UK", "United Kingdom"],
    "France": ["France"],
    "Italy": ["Italy"],
    "Spain": ["Spain"],
    "Netherlands": ["Netherlands"],
    "Brazil": ["Brazil"],
    "Mexico": ["Mexico"],
    "UAE": ["UAE", "Dubai"],
    "Saudi Arabia": ["Saudi Arabia", "KSA"],
    "South Africa": ["South Africa"],
    "Australia": ["Australia"],
    "Poland": ["Poland"],
    "Turkey": ["Turkey"],
    "India": ["India"],
    "Vietnam": ["Vietnam"],
    "Thailand": ["Thailand"],
}

CUSTOMS_SOURCES = [
    "importgenius.com", "panjiva.com", "importyeti.com",
    "tradesparq.com", "zauba.com", "customsdata.net",
]

B2B_SOURCES = [
    "alibaba.com", "made-in-china.com", "tradeindia.com",
    "europages.com", "globalsources.com", "ecplaza.net",
]

# ─── 搜索关键词生成 ───

def generate_search_queries(day_of_month=None):
    if day_of_month is None:
        day_of_month = datetime.date.today().day

    queries = []
    topic = SEARCH_TOPICS[day_of_month % len(SEARCH_TOPICS)]
    product = topic["product"]

    for buyer in topic["buyer"]:
        queries.append(f'"{buyer}" "{product}" email')
        queries.append(f'"{product}" {buyer} contact')

    countries = list(COUNTRY_KEYWORDS.keys())
    for i in range(3):
        c = countries[(day_of_month + i) % len(countries)]
        queries.append(f'"{product}" importer {c} email')
        queries.append(f'"{product}" distributor {c} contact')

    for b2b in B2B_SOURCES[:3]:
        queries.append(f'site:{b2b} "{product}" buy request')

    queries.append(f'"{product}" HS code 392010')
    queries.append(f'site:linkedin.com "{product}" procurement manager')
    queries.append(f'site:linkedin.com "{product}" packaging manager')

    return queries


def search_instructions_text(queries):
    """生成搜索指引文本（供 AI 使用）"""
    lines = []
    for q in queries:
        lines.append(f"🔍 {q}")
    return "\n".join(lines)


# ─── 模拟海关/网站搜索结果解析 ───

def infer_country(query):
    for c, keywords in COUNTRY_KEYWORDS.items():
        if any(k.lower() in query.lower() for k in keywords):
            return c
    return "Unknown"


def infer_product(query):
    for t in SEARCH_TOPICS:
        if t["product"].lower() in query.lower():
            return t["product"]
    return "PP hollow sheet"


# ─── 主入口 ───

def run_search_today(search_results=None):
    """
    每天调用的主函数。
    search_results: 外部传入的搜索结果列表，每个元素为 dict
      { company, contact, email, phone, country, source, product, notes }
    """
    today = datetime.date.today()
    day = today.day
    queries = generate_search_queries(day)

    stats = {
        "date": today.isoformat(),
        "queries_generated": len(queries),
        "leads_added": 0,
        "sample_queries": queries[:8],
        "search_guide": search_instructions_text(queries[:5]),
    }

    if search_results:
        for r in search_results:
            lid = db.add_lead_from_search(r)
            if lid:
                stats["leads_added"] += 1
        db.export_csv()

    stats["database"] = db.get_stats()
    return stats


# ─── 快速添加已知客户 ───

def quick_add(company, email=None, phone=None, country=None, source="manual", person=None):
    return db.add_lead(company, contact_person=person or "",
                       email=email or "", phone=phone or "",
                       country=country or "", source=source)


if __name__ == "__main__":
    print("═" * 50)
    print("TXD CO., LTD  —  自动获客搜索模块")
    print("═" * 50)

    today = datetime.date.today()
    queries = generate_search_queries(today.day)

    print(f"\n📅 {today.isoformat()}  |  今日搜索计划")
    print(f"搜索关键词数: {len(queries)}\n")

    for i, q in enumerate(queries[:10], 1):
        print(f"  {i:2d}. {q}")

    print(f"\n📊 数据库状态:")
    print(json.dumps(db.get_stats(), indent=2, ensure_ascii=False))

    csv_path = db.export_csv()
    if csv_path:
        print(f"\n📁 客户数据已导出: {csv_path}")

    print("\n✅ 模块就绪。将 lead_search.py 集成到定时任务中即可每日自动运行。")
