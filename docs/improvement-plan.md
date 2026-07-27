# TXD CO., LTD — 项目完善计划

**生成日期：** 2026-07-27  
**基于：** 设计文档 `docs/superpowers/specs/2026-06-11-trade-agent-system-design.md` 与代码实际实现对比

---

## 一、Bug 修复（立即处理）

### BUG-01：`content_media.py` — calendar 端点缺少 return
- **文件：** `backend/routers/content_media.py`
- **问题：** `GET /api/content-media/calendar` 端点构建了 `calendar` 字典但函数末尾没有 `return` 语句，运行时返回 `None`，前端无法获取日历数据。
- **修复：** 在函数末尾添加 `return calendar`。

### BUG-02：`emails.py` — POST /send 未实际发送邮件
- **文件：** `backend/routers/emails.py`
- **问题：** `POST /api/emails/send` 端点仅创建一条状态为 "pending" 的 EmailLog 记录，未调用 `EmailService` 实际发送邮件。Admin 面板的发送按钮形同虚设。
- **修复：** 在创建日志后调用 `EmailService.send_email()` 执行真实发送，并更新日志状态。

### BUG-03：`customers.py` — 路由顺序冲突
- **文件：** `backend/routers/customers.py`
- **问题：** `GET /api/customers/export/csv` 定义在 `GET /api/customers/{customer_id}` 之后。FastAPI 按顺序匹配，"export" 会被当作 `customer_id` 参数捕获，导致 CSV 导出 404。
- **修复：** 将 `/export/csv` 路由移到 `/{customer_id}` 之前。

### BUG-04：`customers.py` — 冗余死代码
- **文件：** `backend/routers/customers.py`
- **问题：** `POST /{customer_id}/unmark-interested` 端点第 185 行有一个永远不会执行的 `return` 语句。
- **修复：** 删除冗余 return。

### BUG-05：`httpx` 依赖未声明
- **文件：** `backend/requirements.txt`
- **问题：** `market_scanner.py` 和 `auto_crm_daily.py` 都 `import httpx`，但 requirements.txt 中 httpx 被注释掉（`# httpx==0.28.0`）。生产环境 `pip install` 后这两个模块会 ImportError。
- **修复：** 取消注释 `httpx==0.28.0`，或升级到最新稳定版本并取消注释。

### BUG-06：GitHub Actions 双 workflow 竞争
- **文件：** `.github/workflows/`
- **问题：** `static.yml` 和 `deploy-site.yml` 都在 push to main 时触发，可能同时部署互相覆盖。
- **修复：** `deploy-site.yml` 的博客生成 commit 后会触发 `static.yml` 的二次部署。可以在 `static.yml` 中添加 `paths-ignore` 排除 `blog/` 目录的变更，或在 `deploy-site.yml` 中自行处理部署而不再依赖 `static.yml`。

### BUG-07：博客存在重复 slug
- **文件：** `blog/`
- **问题：** `pp-hollow-sheet-applications-automotive-packaging.html` 和 `pp-hollow-sheet-applications-in-automotive-packaging.html` 主题重复，index.html 中也注册了两次。
- **修复：** 删除重复文章，保留内容质量更高的一篇。

---

## 二、高优先级完善

### P01：前端网站对接后端 API

**现状：** `index.html` 是纯静态页面，产品数据全部硬编码，联系表单为模拟提交。

**需要改造：**

| 项目 | 说明 |
|------|------|
| 产品列表动态化 | 用 JS `fetch('/api/products')` 从后端获取产品数据，动态渲染产品卡片 |
| 分类过滤 | Tab 切换时根据 category 字段过滤 |
| 联系表单真实提交 | `POST /api/inquiries` 提交到后端，触发 LLM 自动分类 |
| 博客列表 | 从 `GET /api/websites` 或博客 API 获取，或保留静态但确保与后端同步 |
| 工厂图片 | 从 `GET /api/campaign/images` 动态加载，支持后台上传新图 |
| SEO 结构化数据 | 添加 Schema.org JSON-LD（Organization、Product、BreadcrumbList） |
| Open Graph / Twitter Card | 为首页和博客添加 OG meta 标签，提升社交分享效果 |

### P02：社交媒体矩阵扩展

**现状：** 9 个平台中仅小红书有自动发布能力（Playwright 浏览器自动化），其余 8 个平台均未实现。

**建议实现优先级：**

| 优先级 | 平台 | 方法 | 工作量 |
|--------|------|------|--------|
| 1 | LinkedIn | API v2（OAuth 2.0） | 中 |
| 2 | Twitter/X | API v2（OAuth 2.0） | 中 |
| 3 | Pinterest | API v5（OAuth 2.0） | 中 |
| 4 | Facebook | Graph API | 中 |
| 5 | YouTube | Data API v3 | 大 |
| 6 | 微信公众号 | Official Account API | 大 |
| 7 | 抖音 | 开放平台 API | 大 |
| 8 | TikTok | Content Posting API | 大 |

**注意：** 内容生成器 `content_generator.py` 已经为所有 10 个平台实现了 prompt 模板，只差发布层对接。

### P03：数据库迁移到 PostgreSQL

**现状：** 使用 SQLite（`sqlite+aiosqlite:///./trade_agent.db`），设计文档要求 PostgreSQL。

**影响：**
- SQLite 不支持并发写入，定时任务并行运行时可能出现锁冲突
- 数据量增长后查询性能下降
- 无内置全文搜索（市场扫描关键词匹配需要）

**迁移步骤：**
1. 安装 PostgreSQL + `psycopg[binary]` 或 `asyncpg`
2. 更新 `database.py` 连接字符串
3. 用 Alembic 初始化迁移
4. 导入 SQLite 数据
5. 更新 `requirements.txt`

### P04：补齐缺失的数据模型

**设计文档中有但未实现的模型：**

| 模型 | 用途 | 优先级 |
|------|------|--------|
| `MarketKeyword` | 监控关键词管理，跟踪扫描频率 | 中 |
| `MarketScan` | 市场扫描原始数据存储 | 中 |
| `MarketReport` | 市场情报报告（日/周/月） | 中 |
| `ContentMetrics` | 内容效果分析（曝光/点击/互动/分享） | 低 |

**对应缺失的 API 路由：**
- `GET /api/intel/keywords` — 列出监控关键词
- `POST /api/intel/keywords` — 添加关键词
- `GET /api/intel/leads` — 线索列表（按评分/市场过滤）
- `POST /api/intel/scan` — 手动触发扫描
- `GET /api/intel/reports` — 报告列表

### P05：邮件系统 IMAP 收信闭环

**现状：** 
- SMTP 发送 ✅ 已实现
- IMAP 收信 ✅ `email_service.py` 已实现 `fetch_unseen()`
- 邮件分类 ✅ `email_service.py` 已实现 `classify_email()`
- Campaign 收件箱扫描 ✅ `campaign.py` 已实现 `POST /inbox/scan`

**缺失：**
- 没有定时轮询收件箱的调度任务（当前只有 Campaign 手动触发扫描）
- 分类后的自动回复策略未与 SequenceService 联动
- 收到客户询盘邮件后未自动创建 Inquiry 记录

**建议：** 在 `scheduler.py` 中添加定时收件箱检查任务（如每 30 分钟），复用 `email_service.py` 和 `campaign.py` 的已有逻辑。

---

## 三、中优先级完善

### P06：图片处理服务完善

**文件：** `backend/services/image_processor.py`

**现状问题：**
- `describe_image()` 仅基于文件名推断描述，没有真正的图像识别能力
- 缺少缩略图生成方法
- 缺少批量处理入口

**完善方案：**
- 集成多模态 LLM（如 Claude Vision / GPT-4o）进行真实图片描述
- 使用 Pillow 生成缩略图
- 添加 `process_new_images()` 批量处理方法
- 在 Admin 面板 `content.html` 中补全媒体库功能

### P07：Docker 部署配置

**现状：** 无 Dockerfile / docker-compose.yml

**需要创建：**

| 文件 | 内容 |
|------|------|
| `Dockerfile` | FastAPI 应用容器化（Python 3.13 + 依赖安装） |
| `docker-compose.yml` | 编排 FastAPI + PostgreSQL 服务 |
| `nginx.conf` | 反向代理配置（静态文件 + API 转发） |
| `.dockerignore` | 排除不必要的文件 |

### P08：多语言支持

**现状：** 网站仅英文，博客仅英文，邮件仅英文。

**设计文档要求：** EN 主、ZH/ES 可选。

**完善方案：**
- 网站模板：Jinja2 添加 i18n 支持，`website_generator.py` 已有中英文生成能力，可扩展
- 博客：`blog_generator.py` 生成时支持多语言版本
- 邮件模板：`email_generator.py` 添加目标市场语言适配
- 前端：添加语言切换器

### P09：竞争对手监控

**设计文档要求：** 每周监控竞争对手网站（价格、新产品）。

**完善方案：**
- 利用现有 Playwright 基础，添加 Competitor 模型
- 定时爬取竞争对手网站，LLM 提取关键信息
- 在 Admin 面板添加竞争情报展示

### P10：SEO 博客质量提升

**现状：** GitHub Actions `deploy-site.yml` 生成的博客使用固定模板，内容通用化，与手工撰写的博客质量差距大。

**完善方案：**
- 利用后端 `BlogGenerator`（已有 LLM 生成能力）替代 GitHub Actions 的模板生成
- 添加动态主题选择（基于行业趋势 + 客户询盘关键词）
- 添加 Schema.org JSON-LD 结构化数据
- 添加内部链接策略（文章间互链）

---

## 四、低优先级 / 未来扩展

### P11：内容效果分析
- `ContentMetrics` 模型 + API
- 跨平台数据聚合仪表盘
- AI 内容优化建议

### P12：WhatsApp Business 集成
- WhatsApp Business API 对接
- 自动回复 + 订单通知

### P13：客户门户
- 独立前端（React/Vue）
- 订单跟踪、历史记录、在线下单

### P14：订单管理系统
- Order 模型
- 报价单 → 订单 → 发货 → 付款 全流程
- PDF 报价单/发票自动生成

### P15：供应商管理
- 供应商信息维护
- 原料价格跟踪（PP 树脂行情）
- 采购订单管理

---

## 五、代码质量清理

| 编号 | 文件 | 问题 |
|------|------|------|
| CQ-01 | `services/lead_scoring.py` | 冗余 import `TradeAgent`（未使用） |
| CQ-02 | `services/social_publisher.py` | FIXME 注释（日志缺失） |
| CQ-03 | `tasks/red_publish_standalone.py` | 5 处 FIXME 注释（日志缺失） |
| CQ-04 | `models/` | 多个模型文件缺少 `__all__` 导出声明 |
| CQ-05 | 全局 | 无单元测试（`pytest` 在 requirements.txt 中被注释） |

---

## 六、建议实施路线图

```
第 1 周：Bug 修复
  ├── BUG-01 ~ BUG-07 全部修复
  └── 添加 httpx 到 requirements.txt

第 2-3 周：前端对接 + 邮件闭环
  ├── P01：前端网站动态化（产品列表、表单提交）
  ├── P05：IMAP 定时收信 + 自动回复联动
  └── P10：SEO 博客质量提升（用后端 BlogGenerator 替代 Actions 模板）

第 4-5 周：社交媒体 + 数据库
  ├── P02：LinkedIn + Twitter API 对接（先做两个平台）
  ├── P03：数据库迁移到 PostgreSQL
  └── P04：补齐 MarketKeyword / MarketScan / MarketReport 模型

第 6-7 周：基础设施 + 运维
  ├── P06：图片处理服务完善
  ├── P07：Docker 化部署
  ├── P08：多语言基础支持
  └── CQ-01 ~ CQ-05：代码质量清理

第 8 周+：扩展功能
  ├── P09：竞争对手监控
  ├── P11：内容效果分析
  └── 根据业务需求排列 P12-P15
```

---

## 七、当前项目健康度总览

| 维度 | 评分 | 说明 |
|------|------|------|
| 后端 API 完整度 | 90% | ~97 个端点，94 个完整实现，2 个部分实现，2 个有缺陷 |
| 服务层完整度 | 95% | 13 个服务中 12 个完整实现，1 个功能不完整（图片处理） |
| 定时任务完整度 | 100% | 9 个任务全部完整实现 |
| Admin 管理面板 | 95% | 10 个页面全部有真实功能，仅媒体库占位 |
| 前端网站 | 70% | UI 完整但纯静态，无 API 交互 |
| CI/CD | 75% | 部署流程完整，但有 workflow 竞争和内容质量问题 |
| 社交媒体 | 15% | 9 个平台仅 1 个实现（小红书） |
| 邮件闭环 | 70% | 发送完整，收信已实现但未自动化调度 |
| 部署配置 | 40% | 无 Docker，无 Nginx，无 PostgreSQL |
| 测试覆盖 | 0% | 无任何测试 |

**总体评估：后端系统已相当成熟（90%+），前端和运维层是主要短板。**
