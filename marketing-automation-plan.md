# Automated Website Promotion Plan

## Overview
Zero-cost automated promotion system for the TXD CO., LTD B2B website targeting overseas markets (Europe, North America, South America, Middle East).

---

## 1. SEO Automation (GitHub Pages + GitHub Actions)

### Technical SEO
- [x] Static site on GitHub Pages (fast loading, free hosting)
- [ ] Generate `sitemap.xml` automatically via GitHub Actions weekly
- [ ] Generate `robots.txt` pointing to sitemap
- [ ] Add structured data (Product, Organization, BreadcrumbList JSON-LD)

### Content Strategy
| Frequency | Task | Tool |
|-----------|------|------|
| Daily | Auto-generate 1 SEO-optimized blog post about PP hollow board applications | GitHub Actions + AI |
| Weekly | Submit sitemap to Google Search Console | GitHub Actions webhook |
| Monthly | Auto-generate case study page from template | GitHub Actions |

### GitHub Actions Workflow — Daily SEO Blog Post
```yaml
name: Daily SEO Post
on:
  schedule:
    - cron: '0 2 * * *'  # 10:00 AM Beijing time
jobs:
  generate-post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate blog post
        run: |
          # Use AI to generate SEO content about PP hollow boards
          # Topic templates rotate automatically
          # Output to blog/YYYY-MM-DD-title.md
      - name: Build & deploy
        run: |
          # Rebuild static site with new blog post
          git add . && git commit -m "Daily SEO post $(date +%Y-%m-%d)"
          git push
```

---

## 2. Social Media Automation (Free Tier)

### Platform Strategy

| Platform | Content Type | Posting Frequency | Target Audience |
|----------|-------------|-------------------|-----------------|
| LinkedIn | B2B product posts, case studies | 3x/week | Europe, US buyers |
| YouTube Shorts | 30-60s product showcase videos | 2x/week | Global |
| Pinterest | Product catalog images | 5x/week | US, South America |
| Twitter/X | Industry news + product links | Daily | Global B2B |
| Facebook Page | Company updates + promotions | 3x/week | Middle East, South America |

### Tools (Free)
- **Buffer** — free plan: schedule up to 10 posts per platform
- **Canva** — free product image templates
- **CapCut** — free video editing for shorts
- **Hootsuite** — free plan: 5 scheduled posts

### Automated Content Pipeline
```
Product Image → Canva template → Social post image → Buffer schedule → Multi-platform publish
```

---

## 3. Email Marketing Automation

### Setup (Free)
- **Mailchimp** free tier: 500 contacts, 1,000 emails/month
- **Brevo (Sendinblue)** free tier: 300 emails/day

### Email Sequences

#### Sequence A: Cold Outreach (Importers/Distributors)
1. **Day 0** — Intro: "Premium PP Hollow Sheets — Direct from Manufacturer"
2. **Day 3** — Follow-up: Product Catalog + Specifications
3. **Day 7** — Case Study: "How [Client] saved 30% on packaging"
4. **Day 14** — Free sample offer

#### Sequence B: Warm Leads (Website Inquiries)
1. **Immediate** — Thank you + Product info pack
2. **Day 2** — Custom quote request details
3. **Day 5** — Factory tour video + quality certs
4. **Day 10** — Shipping & logistics information

### Lead Source → Auto-Email Trigger
```
Website contact form → Google Sheets → Zapier (free) → Mailchimp → Sequence B
```

---

## 4. B2B Marketplace Listings (Free)

| Platform | Action | Frequency |
|----------|--------|-----------|
| Alibaba.com | Maintain product listings | Weekly update |
| Made-in-China.com | Free listing | Monthly refresh |
| TradeIndia.com | Free directory listing | Monthly |
| Europages (EU) | B2B directory | Setup once |
| GlobalSources.com | Free listing | Monthly |
| IndustrySearch (AU) | B2B listing | Setup once |

### Automation
```
Price list update → Auto-sync to all platforms → Weekly
```

---

## 5. Google Business Profile

- [ ] Create Google Business Profile (free)
- [ ] Add product photos (use selected images)
- [ ] Post weekly updates
- [ ] Collect reviews

---

## 6. Automated Analytics & Reporting

### Google Analytics 4 (Free)
- Track page views, bounce rate, conversion
- Set up goals: "Quote Request" form submissions
- Auto-report via Google Looker Studio (free)

### Monthly Report (GitHub Actions)
```yaml
name: Monthly Marketing Report
on:
  schedule:
    - cron: '0 8 1 * *'  # 1st of each month
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - name: Fetch GA4 data via API
        run: curl -X GET "https://analyticsdata.googleapis.com/..."
      - name: Generate report
        run: python generate_report.py
      - name: Send report email
        run: mail -s "Monthly Marketing Report" jack@company.com < report.md
```

---

## 7. Implementation Timeline

### Week 1-2: Foundation
- [ ] Deploy website to GitHub Pages
- [ ] Submit to Google Search Console
- [ ] Create Google Business Profile
- [ ] Set up GA4

### Week 3-4: Content & Social
- [ ] Set up LinkedIn Company Page
- [ ] Create Canva templates
- [ ] Set up Buffer scheduling
- [ ] First 10 blog posts

### Week 5-6: Outreach
- [ ] Set up Mailchimp + email sequences
- [ ] Create B2B marketplace listings
- [ ] First batch of cold emails (100 contacts)

### Ongoing (Daily)
- [ ] GitHub Actions auto-generates blog post
- [ ] Social posts auto-schedule
- [ ] Monitor contact form responses
- [ ] Weekly: check Google Search Console for keywords

---

## 8. Target Keywords (for SEO & Content)

### Primary Keywords
- PP hollow sheet manufacturer
- Corrugated plastic sheet supplier
- Hollow board exporter China
- PP plastic box wholesale

### Secondary Keywords
- Polypropylene twinwall sheet
- Fluted plastic sheet for packaging
- Reusable plastic container manufacturer
- ESD plastic box for electronics

### Long-tail
- Waterproof corrugated plastic sheets for greenhouse
- Lightweight hollow board for automotive packaging
- Custom printed PP boxes for retail display
- Anti-static corrugated sheets for electronics

---

## 9. Key Performance Indicators (Monthly)

| Metric | Target |
|--------|--------|
| Website visitors | 500+ in first 3 months |
| Bounce rate | < 60% |
| Contact form submissions | 10+ per month |
| LinkedIn followers | 200+ in 6 months |
| Email subscribers | 100+ in 6 months |
| Google Search impressions | 5,000+ in 6 months |
