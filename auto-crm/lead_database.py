"""
TXD CO., LTD — Lead Database & CRM System
Auto-managed customer database with lifecycle tracking.
"""

import json, os, csv, datetime, random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LEADS_FILE = DATA_DIR / "leads.json"
CONTACTS_FILE = DATA_DIR / "contacts_log.json"
STATS_FILE = DATA_DIR / "stats.json"

class LeadDatabase:
    """客户线索数据库，自动管理和跟踪"""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.leads = self._load(LEADS_FILE)
        self.contacts = self._load(CONTACTS_FILE)
        self.stats = self._load(STATS_FILE, {
            "total_searched": 0,
            "total_contacted": 0,
            "total_replied": 0,
            "total_converted": 0,
            "last_run": None,
            "daily_target": 15
        })

    def _load(self, path, default=None):
        if path.exists():
            try: return json.load(open(path, 'r', encoding='utf-8'))
            except: pass
        return default if default is not None else []

    def _save(self, data, path):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def add_lead(self, company, contact_person=None, email=None, phone=None,
                 country=None, source=None, product_interest=None, notes=""):
        """添加新客户"""
        now = datetime.datetime.now().isoformat()
        lead = {
            "id": f"LD{len(self.leads)+1:04d}",
            "company": company,
            "contact_person": contact_person or "",
            "email": email or "",
            "phone": phone or "",
            "country": country or "",
            "source": source or "manual",
            "product_interest": product_interest or "",
            "website": "",
            "notes": notes,
            "status": "new",           # new → contacted → interested → negotiating → converted
            "stage": "new",             # new, followup1, followup2, followup3, dormant, converted, lost
            "created_at": now,
            "updated_at": now,
            "last_contacted": None,
            "next_followup": None,
            "contact_count": 0,
            "tags": []
        }
        # 避免重复
        existing = [l for l in self.leads if l['email'] == email and email]
        if existing:
            existing[0]['notes'] += f"\n[更新] {now}: {notes}"
            existing[0]['updated_at'] = now
            self._save(self.leads, LEADS_FILE)
            return existing[0]['id']
        self.leads.append(lead)
        self._save(self.leads, LEADS_FILE)
        return lead['id']

    def search_leads(self, keyword=None, country=None, status=None, source=None):
        """搜索客户"""
        results = self.leads
        if keyword:
            results = [l for l in results if keyword.lower() in l['company'].lower()
                       or keyword.lower() in l['contact_person'].lower()
                       or keyword.lower() in l['notes'].lower()]
        if country: results = [l for l in results if l['country'].lower() == country.lower()]
        if status: results = [l for l in results if l['status'] == status]
        if source: results = [l for l in results if l['source'] == source]
        return results

    def get_leads_for_today(self, target=15):
        """获取今天要联系的客户"""
        today = datetime.date.today().isoformat()
        # 优先联系：新客户 + 需要跟进的老客户
        new_leads = [l for l in self.leads if l['status'] == 'new'][:target//2]
        followup = [l for l in self.leads if l['next_followup']
                    and l['next_followup'] <= today
                    and l['status'] not in ['converted', 'lost']
                    and l['id'] not in [n['id'] for n in new_leads]]
        followup = followup[:target - len(new_leads)]
        return new_leads + followup

    def mark_contacted(self, lead_id, email_sent=True, response=False):
        """标记为已联系"""
        for l in self.leads:
            if l['id'] == lead_id:
                l['status'] = 'contacted'
                l['stage'] = 'followup1'
                l['last_contacted'] = datetime.datetime.now().isoformat()
                l['contact_count'] += 1
                # 设置下次跟进（1个月后）
                next_date = datetime.date.today() + datetime.timedelta(days=30)
                l['next_followup'] = next_date.isoformat()
                l['updated_at'] = datetime.datetime.now().isoformat()
                self._save(self.leads, LEADS_FILE)
                return True
        return False

    def mark_response(self, lead_id, interested=False):
        """标记客户回复"""
        for l in self.leads:
            if l['id'] == lead_id:
                l['status'] = 'negotiating' if interested else 'contacted'
                l['notes'] += f"\n[回复] {datetime.datetime.now().isoformat()}: {'感兴趣' if interested else '未回复'}"
                if interested: l['stage'] = 'negotiating'
                else: l['next_followup'] = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
                l['updated_at'] = datetime.datetime.now().isoformat()
                self.stats['total_replied'] += 1
                self._save(self.leads, LEADS_FILE)
                self._save(self.stats, STATS_FILE)
                return True
        return False

    def mark_converted(self, lead_id):
        """标记成交"""
        for l in self.leads:
            if l['id'] == lead_id:
                l['status'] = 'converted'
                l['stage'] = 'converted'
                l['notes'] += f"\n[成交] {datetime.datetime.now().isoformat()}"
                l['next_followup'] = None
                l['updated_at'] = datetime.datetime.now().isoformat()
                self.stats['total_converted'] += 1
                self._save(self.leads, LEADS_FILE)
                self._save(self.stats, STATS_FILE)
                return True
        return False

    def get_stats(self):
        """获取统计数据"""
        self.stats['total_searched'] = len(self.leads)
        self.stats['total_contacted'] = len([l for l in self.leads if l['status'] != 'new'])
        self.stats['last_run'] = datetime.datetime.now().isoformat()
        self._save(self.stats, STATS_FILE)
        return {
            "total_leads": len(self.leads),
            "new": len([l for l in self.leads if l['status'] == 'new']),
            "contacted": len([l for l in self.leads if l['status'] == 'contacted']),
            "negotiating": len([l for l in self.leads if l['status'] == 'negotiating']),
            "converted": len([l for l in self.leads if l['status'] == 'converted']),
            "lost": len([l for l in self.leads if l['status'] == 'lost']),
            "today_target": self.stats.get('daily_target', 15),
            "replied": self.stats.get('total_replied', 0),
        }

    def export_csv(self):
        """导出客户数据到CSV"""
        path = DATA_DIR / "leads_export.csv"
        if not self.leads:
            return None
        keys = ['id', 'company', 'contact_person', 'email', 'phone', 'country',
                'source', 'product_interest', 'status', 'stage', 'created_at', 'notes']
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for l in self.leads:
                w.writerow({k: l.get(k, '') for k in keys})
        return str(path)

    def add_lead_from_search(self, search_result):
        """从搜索结果自动添加客户"""
        return self.add_lead(
            company=search_result.get('company', 'Unknown'),
            contact_person=search_result.get('contact', ''),
            email=search_result.get('email', ''),
            phone=search_result.get('phone', ''),
            country=search_result.get('country', ''),
            source=search_result.get('source', 'web_search'),
            product_interest=search_result.get('product', 'PP hollow sheet'),
            notes=search_result.get('notes', '')
        )

# 初始化
db = LeadDatabase()

if __name__ == "__main__":
    print("=== TXD CO., LTD Lead Database ===")
    print(json.dumps(db.get_stats(), indent=2))
    print(f"Database: {LEADS_FILE}")
