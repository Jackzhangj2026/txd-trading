# TXD CO., LTD — 自动化获客与成交系统 🚀

## 系统概述

每日自动运行的智能获客系统，帮你自动搜索、联系、跟进全球采购中空板的客户。

```
搜索客户 → 数据库 → 发开发信 → 跟踪回复 → 1月后再次跟进 → 循环
```

---

## 📦 文件结构

```
auto-crm/
├── lead_database.py    # 客户数据库（自动管理）
├── lead_search.py      # 客户搜索模块（海关/B2B/LinkedIn）
├── email_sender.py     # 邮件发送模块（精美HTML模板）
├── daily_automation.py # 主调度器（每天运行这个）
├── SETUP_GUIDE.md      # 本文件
├── data/               # 数据库自动生成
│   ├── leads.json      # 客户数据
│   ├── email_config.json  # 邮箱配置
│   └── daily_report.json  # 运行报告
├── templates/
│   └── email_template.html # 开发信HTML模板（精美排版）
└── email_images/       # 放产品图片（可选）
```

---

## ⚙️ 第一步：配置邮箱

你需要先配置发信邮箱。推荐使用 **QQ邮箱**（国内方便）或 **Gmail**。

### QQ邮箱配置

1. 登录你的 QQ 邮箱
2. 点 **设置 → 账户 → POP3/IMAP/SMTP服务**
3. 开启 **SMTP服务**，点击生成 **授权码**
4. 复制授权码（不是QQ密码！）

### 运行配置向导

打开 CMD，执行：

```bash
cd E:\hollowsheet\auto-crm
python email_sender.py --setup
```

按提示输入：
- 邮箱地址（如 `4621710@qq.com`）
- SMTP授权码（刚生成的那个）
- SMTP服务器：`smtp.qq.com`
- SMTP端口：`465`
- 每日发信上限：`20`

配置完成后会发送测试邮件，检查是否收到。

---

## 🚀 第二步：开始使用

### 每日运行（自动模式）

```bash
cd E:\hollowsheet\auto-crm
python daily_automation.py
```

执行后会自动：
1. 生成今天搜索关键词（轮换10大话题×多国家）
2. 搜索潜在客户
3. 筛选15个要联系的客户（新客户 + 需跟进的）
4. 发送精美开发信
5. 标记已联系，设置1月后跟进
6. 更新数据库统计

### 预览模式（先看看不发信）

```bash
python daily_automation.py --dry-run
```

### 查看数据面板

```bash
python daily_automation.py --dashboard
```

### 手动添加客户

```bash
python daily_automation.py --manual-add
```

### 导出客户数据到CSV

```bash
python daily_automation.py --export
```

---

## 🤖 第三步：设置自动运行（两个方式二选一）

### 方式A: Cowork定时任务（推荐）

已创建一个名为 `daily-lead-hunting` 的定时任务，每天 9:00 AM 自动运行。

如果需要启用邮件发送，请先完成邮箱配置，然后在任务运行前确保邮箱已配置好。

### 方式B: Windows 任务计划程序

1. 按 `Win + R`，输入 `taskschd.msc` 回车
2. 点 **创建基本任务**
3. 名称: `TXD Daily CRM`
4. 触发器: **每天**，时间选 `09:00`
5. 操作: **启动程序**
   - 程序: `python`
   - 参数: `E:\hollowsheet\auto-crm\daily_automation.py`
6. 完成

---

## 📊 第四步：查看效果

### 每天查看日报

运行以下命令查看数据库状态：

```bash
cd E:\hollowsheet\auto-crm
python daily_automation.py --dashboard
```

你会看到：
```
客户总数: 120
新客户: 15
已联系: 80
洽谈中: 8
已成交: 3
今日已发: 15/20
```

### 导出客户列表

```bash
python daily_automation.py --export
```
生成的 CSV 文件在 `auto-crm/data/leads_export.csv`，可以用 Excel 打开。

---

## 📧 开发信效果

我们预置的精美 HTML 模板包含：
- ✅ 渐变紫色头部（公司品牌色）
- ✅ 产品亮点卡片
- ✅ 产品图片插入位
- ✅ 产品速查表（厚度/宽度/颜色/交期）
- ✅ CTA按钮（引导访问网站）
- ✅ 底部完整联系信息

模板文件：`auto-crm/templates/email_template.html`，你可以直接编辑修改。

---

## 🔄 客户跟进流程

```
第1天 → 发送开发信
         ↓
第7天 → 没回复？再发一次（自动）
         ↓
第30天 → 还是没回复？第2次跟进
         ↓
第60天 → 最后一次跟进，标注"沉睡"
         ↓
如果回复 → 标记为"洽谈中"，转到人工跟进
         ↓
如果成交 → 标记为"已成交"，进入客户维护
```

---

## 💡 搜索关键词策略（每日轮换）

系统内置了**10大产品话题**，每天轮换：
1. PP hollow sheet
2. corrugated plastic sheet
3. PP hollow board
4. plastic packaging sheet
5. fluted plastic sheet
6. polypropylene twinwall sheet
7. plastic box manufacturer
8. reusable plastic container
9. ESD packaging material
10. plastic corrugated box

每个话题搭配 **5种买家类型** × **3个国家**，每天生成约20个搜索关键词。

---

## ❓ 常见问题

**Q: 会不会被判定为垃圾邮件？**
A: 每天上限20封，间隔3分钟，控制频率。主题行用个性化内容，不要带太多营销词汇。

**Q: 邮件发出去没有回复怎么办？**
A: 系统会自动每个月底再次跟进，持续3次。建议配合LinkedIn加人提高回复率。

**Q: 数据库存在哪里？**
A: `auto-crm/data/leads.json`，纯JSON格式，可以随时查看和编辑。

**Q: 可以同时给多个国家发吗？**
A: 可以！系统每天自动切换目标国家（美国→欧洲→南美→中东轮换）。
