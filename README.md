# TXD CO., LTD — PP Hollow Board & Box Trading Website

面向海外市场的中空板及中空板箱子贸易公司网站。

---

## 🚀 快速部署到 GitHub Pages

### 第一步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名输入：`hollowtech-trading` 或你喜欢的名字
3. 选择 **Public**（公开，免费托管）
4. **不要勾选** "Add a README"（我们已经有）
5. 点击 **Create repository**

### 第二步：推送代码

在电脑的终端（Terminal / CMD / PowerShell）中执行：

```bash
# 进入项目文件夹
cd E:\hollowsheet

# 初始化 Git（如果还没初始化）
git init
git checkout -b main

# 配置你的信息
git config user.email "your-email@example.com"
git config user.name "Your Name"

# 添加所有文件
git add -A

# 提交
git commit -m "Initial commit: TXD CO., LTD PP hollow board trading website"

# 关联远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/hollowtech-trading.git

# 推送
git push -u origin main
```

### 第三步：启用 GitHub Pages

1. 打开你的仓库 https://github.com/你的用户名/hollowtech-trading
2. 点击 **Settings** → **Pages**
3. Source 选择 **GitHub Actions**
4. 稍等1-2分钟，网站就会自动部署

**部署完成后你的网站地址是：**
`https://你的用户名.github.io/hollowtech-trading/`

---

## 📝 每日自动博客推广

### 方式一：GitHub Actions（已配置好）

仓库里的 `.github/workflows/deploy-site.yml` 已经包含了每日 SEO 博客自动生成功能。
- 每天北京时间 10:00 AM 自动运行
- 自动生成一篇关于 PP 中空板/箱子的 SEO 文章
- 自动推送到仓库，触发网站重新部署

---

## 📁 项目结构

```
hollowsheet/
├── index.html                          # 官网首页（单页，英文）
├── .nojekyll                           # GitHub Pages 配置
├── robots.txt                          # 爬虫规则（自动生成）
├── sitemap.xml                         # 站点地图（自动生成）
├── images/
│   ├── hero/                           # 横幅大图（6张）
│   ├── products/sheets/                # 中空板产品图（11张）
│   ├── products/boxes/                 # 中空板箱子图（36张）
│   ├── factory/                        # 工厂实拍图（18张）
│   └── catalog/                        # 产品目录图（4张）
├── blog/                               # SEO 博客文章
│   ├── index.html                      # 博客列表（动态加载 posts.json）
│   ├── posts.json                      # 博客文章数据
│   └── style.css                       # 博客样式
├── scripts/
│   ├── generate_blog.py                # 每日博客自动生成脚本
│   └── generate_sitemap.py             # sitemap.xml + robots.txt 生成脚本
├── .github/workflows/
│   └── deploy-site.yml                 # 自动部署 + 博客生成 + 站点地图
├── marketing-automation-plan.md        # 自动化推广计划
├── trade-automation-plan.md            # 自动化贸易业务计划
└── README.md                           # 本文档
```

## ✨ 网站功能

- 深色科技主题 + 粒子动画
- 产品分类展示（中空板/箱子/目录 Tab切换）
- 工厂实拍展示
- 全球市场覆盖（欧美/南美/中东）
- 贸易服务介绍
- 联系询盘表单
- 响应式设计（手机/平板/桌面）
- 每日 SEO 博客自动更新

## 🔧 SEO 优化配置

| 项目 | 状态 | 说明 |
|------|------|------|
| Google Analytics GA4 | ✅ 已配置 | ID: G-K7D5MN77C2 |
| JSON-LD 结构化数据 | ✅ 已配置 | Organization / Product / BreadcrumbList |
| sitemap.xml | ✅ 自动生成 | 每次部署自动更新，需在 Google Search Console 提交 |
| robots.txt | ✅ 自动生成 | 允许所有爬虫，指向 sitemap |
| Google Search Console | ✅ 已配置 | 验证文件已部署 |

## 📊 推广计划

详见 [marketing-automation-plan.md](marketing-automation-plan.md)

## 💼 贸易业务自动化

详见 [trade-automation-plan.md](trade-automation-plan.md)

## 🌐 外贸推广渠道

| 渠道 | 优先级 | 说明 |
|------|--------|------|
| Google SEO | ⭐ 已启动 | 每日博客 + sitemap 自动提交 |
| LinkedIn Company Page | 📋 待创建 | B2B 最佳免费渠道，发产品图和工厂实拍 |
| Made-in-China.com | 📋 待注册 | 免费会员产品对买家可见，适合起步 |
| Alibaba RFQ | 📋 待使用 | 免费会员每90天可报10次买家询盘 |
| TradeIndia.com | 📋 待注册 | 面向南亚/中东市场 |
| Google Business Profile | 📋 待创建 | 本地搜索曝光 |

## 📬 联系方式

- 网站联系表单：`/#contact`
- 邮箱：4621710@qq.com
- 办公室：Room 602, No. 191, Haifa Road, Haicang District, Xiamen, China
