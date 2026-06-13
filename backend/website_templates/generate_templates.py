"""Generate 20 multi-page template folders (Home/Products/About/Blog/Contact)."""
from pathlib import Path

DIR = Path(__file__).parent

def make_page(page_name, css_vars, extra_css):
    """Generate a complete page HTML. css_vars and extra_css are injected directly."""
    # Build nav with active page link
    pages = ["index", "products", "about", "blog", "contact"]
    page_labels = {"index":"Home","products":"Products","about":"About","blog":"Blog","contact":"Contact"}

    nav_links = ""
    for p in pages:
        active = ' class="active"' if p == page_name else ""
        nav_links += f'<li><a href="{p}.html"{active}>{page_labels[p]}</a></li>\n'

    nav = f"""<nav>
  <div class="container">
    <a href="index.html" class="logo">{{{{ company_name }}}}<span>.</span></a>
    <div class="nav-toggle" onclick="document.querySelector('nav .nav-links').classList.toggle('show')">&#9776;</div>
    <ul class="nav-links">
{nav_links}    </ul>
  </div>
</nav>"""

    footer = """<footer>
  <div class="container">
    <div class="footer-grid">
      <div class="footer-col">
        <h4>{{ company_name }}</h4>
        <p>{{ tagline }}</p>
      </div>
      <div class="footer-col">
        <h4>Quick Links</h4>
        <a href="index.html">Home</a>
        <a href="products.html">Products</a>
        <a href="about.html">About Us</a>
        <a href="blog.html">Blog</a>
        <a href="contact.html">Contact</a>
      </div>
      <div class="footer-col">
        <h4>Contact</h4>
        <p>&#x2709; {{ contact_email }}</p>
        <p>&#x260E; {{ contact_phone }}</p>
        <p>&#x1f4cd; {{ contact_address }}</p>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&copy; 2025 <a href="index.html">{{ company_name }}</a>. All rights reserved.</p>
    </div>
  </div>
</footer>"""

    common_css = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; }
a { color: var(--accent); text-decoration: none; }
img { max-width: 100%; height: auto; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 2rem; }
nav { background: var(--primary); color: white; padding: 1rem 0; position: sticky; top: 0; z-index: 100; }
nav .container { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; }
nav .logo { font-size: 1.5rem; font-weight: 800; color: white; }
nav .logo span { color: var(--accent); }
nav .nav-links { display: flex; gap: 1.5rem; list-style: none; flex-wrap: wrap; }
nav .nav-links a { color: rgba(255,255,255,0.8); transition: color 0.3s; font-weight: 500; font-size: 0.95rem; padding: 0.25rem 0; }
nav .nav-links a:hover, nav .nav-links a.active { color: white; border-bottom: 2px solid var(--accent); }
.nav-toggle { display: none; font-size: 1.5rem; cursor: pointer; color: white; }
.hero { padding: 5rem 0; background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%); color: white; text-align: center; }
.hero h1 { font-size: 3rem; font-weight: 800; margin-bottom: 1rem; line-height: 1.2; }
.hero p { font-size: 1.2rem; max-width: 700px; margin: 0 auto 2rem; opacity: 0.9; }
.hero .btn { display: inline-block; padding: 1rem 2.5rem; background: var(--accent); color: white; border-radius: var(--radius); font-weight: 600; transition: transform 0.3s; border: none; font-size: 1rem; cursor: pointer; }
.hero .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.2); }
section { padding: 4rem 0; }
section:nth-child(even) { background: var(--bg-alt); }
.section-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; text-align: center; }
.section-sub { text-align: center; color: var(--text-light); max-width: 600px; margin: 0 auto 3rem; }
.products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 2rem; }
.product-card { background: var(--bg); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; transition: transform 0.3s; border: 1px solid rgba(0,0,0,0.05); }
.product-card:hover { transform: translateY(-4px); }
.product-card .img-wrap { height: 220px; background: var(--bg-alt); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.product-card .img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.product-card .img-wrap .no-img { color: var(--text-light); font-size: 2.5rem; opacity: 0.3; }
.product-card .info { padding: 1.25rem; }
.product-card .info h3 { font-size: 1.1rem; margin-bottom: 0.5rem; color: var(--primary); }
.product-card .info p { font-size: 0.9rem; color: var(--text-light); }
.services-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 2rem; }
.service-card { background: var(--bg); padding: 2rem; border-radius: var(--radius); box-shadow: var(--shadow); transition: transform 0.3s; }
.service-card:hover { transform: translateY(-4px); }
.service-card h3 { font-size: 1.2rem; margin-bottom: 0.75rem; color: var(--primary); }
.service-card p { color: var(--text-light); font-size: 0.95rem; }
.page-header { background: var(--primary); color: white; padding: 3rem 0; text-align: center; }
.page-header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
.page-header p { opacity: 0.8; }
.mission-vision { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 3rem; }
.mission-vision .card { background: var(--bg); padding: 2rem; border-radius: var(--radius); box-shadow: var(--shadow); }
.mission-vision .card h3 { color: var(--accent); margin-bottom: 1rem; }
.stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 2rem; text-align: center; margin: 3rem 0; }
.stat-item .num { font-size: 2.5rem; font-weight: 800; color: var(--accent); }
.stat-item .label { color: var(--text-light); font-size: 0.9rem; }
.blog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 2rem; }
.blog-card { background: var(--bg); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; transition: transform 0.3s; border: 1px solid rgba(0,0,0,0.05); }
.blog-card:hover { transform: translateY(-4px); }
.blog-card .img-wrap { height: 200px; background: var(--bg-alt); display: flex; align-items: center; justify-content: center; }
.blog-card .img-wrap .no-img { color: var(--text-light); font-size: 3rem; opacity: 0.3; }
.blog-card .img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.blog-card .info { padding: 1.5rem; }
.blog-card .info .date { font-size: 0.8rem; color: var(--text-light); margin-bottom: 0.5rem; }
.blog-card .info h3 { font-size: 1.15rem; margin-bottom: 0.5rem; }
.blog-card .info p { font-size: 0.9rem; color: var(--text-light); margin-bottom: 1rem; }
.blog-card .info .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.blog-card .info .tags span { font-size: 0.75rem; background: var(--bg-alt); padding: 0.15rem 0.5rem; border-radius: 999px; color: var(--text-light); }
.contact-section { padding: 4rem 0; }
.contact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; }
.contact-info .info-item { margin-bottom: 1.5rem; }
.contact-info .info-item h4 { color: var(--primary); margin-bottom: 0.25rem; }
.contact-info .info-item p { color: var(--text-light); }
.contact-form input, .contact-form textarea { width: 100%; padding: 0.8rem 1rem; margin-bottom: 1rem; border: 2px solid var(--bg-alt); border-radius: var(--radius); font-family: var(--font); font-size: 0.95rem; background: var(--bg); color: var(--text); }
.contact-form input:focus, .contact-form textarea:focus { outline: none; border-color: var(--accent); }
.contact-form textarea { min-height: 150px; resize: vertical; }
.contact-form .btn { width: 100%; }
footer { background: var(--primary); color: rgba(255,255,255,0.7); padding: 3rem 0 1.5rem; margin-top: 3rem; font-size: 0.9rem; }
.footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 2rem; margin-bottom: 2rem; }
footer a { color: var(--accent); }
footer h4 { color: white; margin-bottom: 1rem; }
.footer-col { display: flex; flex-direction: column; gap: 0.5rem; }
.footer-bottom { text-align: center; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.1); }
{{ custom_css }}
@media (max-width: 768px) {
  .hero h1 { font-size: 2rem; }
  nav .nav-links { display: none; width: 100%; flex-direction: column; padding: 1rem 0; gap: 0.75rem; }
  nav .nav-links.show { display: flex; }
  .nav-toggle { display: block; }
  .products-grid, .services-grid, .blog-grid { grid-template-columns: 1fr; }
  .contact-grid, .mission-vision { grid-template-columns: 1fr; }
  .footer-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .page-header h1 { font-size: 1.8rem; }
}
"""

    # Build page body
    if page_name == "index":
        body = """<section class="hero">
  <div class="container">
    <h1>{{ tagline }}</h1>
    <p>Your trusted partner in {{ industry_name }} — delivering quality products worldwide.</p>
    <a href="products.html" class="btn">View Our Products</a>
  </div>
</section>

<section id="products">
  <div class="container">
    <h2 class="section-title">Our Products</h2>
    <p class="section-sub">High-quality products for global markets</p>
    <div class="products-grid">
      {% for product in products[:6] %}
      <div class="product-card">
        <div class="img-wrap">
          {% if product.image_urls and product.image_urls[0] %}
          <img src="{{ product.image_urls[0] }}" alt="{{ product.title }}">
          {% else %}
          <div class="no-img">&#x1f4e6;</div>
          {% endif %}
        </div>
        <div class="info">
          <h3>{{ product.title }}</h3>
          <p>{{ product.description[:120] }}{% if product.description|length > 120 %}...{% endif %}</p>
        </div>
      </div>
      {% else %}
      <div class="service-card" style="grid-column: 1/-1; text-align: center; padding: 3rem;">
        <p style="color: var(--text-light);">Product catalog coming soon. <a href="contact.html">Contact us</a> for inquiries.</p>
      </div>
      {% endfor %}
    </div>
  </div>
</section>

<section id="about">
  <div class="container">
    <h2 class="section-title">About {{ company_name }}</h2>
    <div class="about-content" style="max-width: 800px; margin: 0 auto; font-size: 1.1rem; line-height: 1.8;">
      {{ about_us }}
    </div>
    <div class="text-center" style="text-align: center; margin-top: 2rem;">
      <a href="about.html" class="btn" style="display: inline-block;">Learn More About Us</a>
    </div>
  </div>
</section>

<section id="services">
  <div class="container">
    <h2 class="section-title">Our Services</h2>
    <p class="section-sub">Comprehensive solutions tailored to your business needs</p>
    <div class="services-grid">
      {% for service in services %}
      <div class="service-card">
        <div class="icon">&#x2728;</div>
        <h3>{{ service.title }}</h3>
        <p>{{ service.description }}</p>
      </div>
      {% endfor %}
    </div>
  </div>
</section>

<section class="cta" style="text-align: center; padding: 4rem 0; background: var(--primary); color: white;">
  <div class="container">
    <h2 style="font-size: 2rem; margin-bottom: 1rem;">Ready to Start?</h2>
    <p style="margin-bottom: 2rem; opacity: 0.9;">Contact us today for competitive quotes and expert service.</p>
    <a href="contact.html" class="btn">Get in Touch</a>
  </div>
</section>"""

    elif page_name == "products":
        body = """<div class="page-header">
  <div class="container">
    <h1>Our Products</h1>
    <p>Explore our range of high-quality products for global markets</p>
  </div>
</div>

<section>
  <div class="container">
    <div class="products-grid">
      {% for product in products %}
      <div class="product-card">
        <div class="img-wrap">
          {% if product.image_urls and product.image_urls[0] %}
          <img src="{{ product.image_urls[0] }}" alt="{{ product.title }}">
          {% else %}
          <div class="no-img">&#x1f4e6;</div>
          {% endif %}
        </div>
        <div class="info">
          <h3>{{ product.title }}</h3>
          <p>{{ product.description[:150] }}{% if product.description|length > 150 %}...{% endif %}</p>
          {% if product.image_urls and product.image_urls|length > 1 %}
          <div style="display: flex; gap: 0.25rem; margin-top: 0.75rem;">
            {% for img in product.image_urls[:4] %}
            <img src="{{ img }}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; cursor: pointer;" onclick="this.parentElement.parentElement.querySelector('.img-wrap img').src=this.src;">
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </div>
      {% else %}
      <div class="service-card" style="grid-column: 1/-1; text-align: center; padding: 4rem 2rem;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">&#x1f4e6;</div>
        <h3>Products Coming Soon</h3>
        <p style="color: var(--text-light); margin-top: 0.5rem;">Our product catalog is being updated. Please check back later or <a href="contact.html">contact us</a>.</p>
      </div>
      {% endfor %}
    </div>
  </div>
</section>"""

    elif page_name == "about":
        body = """<div class="page-header">
  <div class="container">
    <h1>About {{ company_name }}</h1>
    <p>Learn about our story, mission, and commitment to excellence</p>
  </div>
</div>

<section>
  <div class="container">
    <div class="about-content" style="max-width: 800px; margin: 0 auto; font-size: 1.1rem; line-height: 1.8;">
      {{ about_us }}
    </div>
  </div>
</section>

<section style="background: var(--bg-alt);">
  <div class="container">
    <h2 class="section-title">Our Mission & Vision</h2>
    <div class="mission-vision">
      <div class="card"><h3>Our Mission</h3><p>To provide exceptional quality products that exceed our clients' expectations, fostering long-term partnerships built on trust and reliability.</p></div>
      <div class="card"><h3>Our Vision</h3><p>To become a globally recognized leader in our industry, known for innovation, integrity, and excellence in everything we do.</p></div>
    </div>
    <h2 class="section-title" style="margin-top: 3rem;">Why Choose Us</h2>
    <div class="stats-row">
      <div class="stat-item"><div class="num">500+</div><div class="label">Happy Clients</div></div>
      <div class="stat-item"><div class="num">50+</div><div class="label">Countries</div></div>
      <div class="stat-item"><div class="num">15+</div><div class="label">Years Exp.</div></div>
      <div class="stat-item"><div class="num">99%</div><div class="label">On-Time</div></div>
    </div>
    <div class="services-grid" style="margin-top: 2rem;">
      {% for service in services %}
      <div class="service-card">
        <h3>{{ service.title }}</h3>
        <p>{{ service.description }}</p>
      </div>
      {% endfor %}
    </div>
  </div>
</section>"""

    elif page_name == "blog":
        body = """<div class="page-header">
  <div class="container">
    <h1>Our Blog</h1>
    <p>Industry insights, product guides, and company news</p>
  </div>
</div>

<section>
  <div class="container">
    {% if blog_posts %}
    <div class="blog-grid">
      {% for post in blog_posts %}
      <div class="blog-card">
        <div class="img-wrap">
          {% if post.cover_image %}
          <img src="{{ post.cover_image }}" alt="{{ post.title }}">
          {% else %}
          <div class="no-img">&#x1f4d6;</div>
          {% endif %}
        </div>
        <div class="info">
          <div class="date">{{ post.published_at }}</div>
          <h3><a href="blog/{{ post.slug }}.html">{{ post.title }}</a></h3>
          <p>{{ post.excerpt[:150] }}{% if post.excerpt|length > 150 %}...{% endif %}</p>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div style="text-align: center; padding: 4rem 2rem;">
      <div style="font-size: 3rem; margin-bottom: 1rem;">&#x1f4dd;</div>
      <h3>Blog Coming Soon</h3>
      <p style="color: var(--text-light); margin-top: 0.5rem;">We're working on informative content. Stay tuned!</p>
    </div>
    {% endif %}
  </div>
</section>"""

    elif page_name == "contact":
        body = """<div class="page-header">
  <div class="container">
    <h1>Contact Us</h1>
    <p>We'd love to hear from you. Get in touch with our team.</p>
  </div>
</div>

<section class="contact-section">
  <div class="container">
    <div class="contact-grid">
      <div class="contact-info">
        <h2 style="margin-bottom: 2rem;">Get in Touch</h2>
        <div class="info-item"><h4>Email</h4><p><a href="mailto:{{ contact_email }}">{{ contact_email }}</a></p></div>
        <div class="info-item"><h4>Phone</h4><p>{{ contact_phone }}</p></div>
        <div class="info-item"><h4>Address</h4><p>{{ contact_address }}</p></div>
        <div class="info-item"><h4>Working Hours</h4><p>Mon-Fri: 9:00 AM - 6:00 PM</p><p>Sat: 9:00 AM - 1:00 PM</p></div>
      </div>
      <div class="contact-form">
        <h2 style="margin-bottom: 1.5rem;">Send Us a Message</h2>
        <form>
          <input type="text" name="name" placeholder="Your Name *" required>
          <input type="email" name="email" placeholder="Your Email *" required>
          <input type="text" name="subject" placeholder="Subject">
          <textarea name="message" placeholder="Your Message *" required></textarea>
          <button type="submit" class="btn">Send Message</button>
        </form>
      </div>
    </div>
  </div>
</section>"""

    else:
        raise ValueError(f"Unknown page: {page_name}")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{{{ company_name }}}} — {{{{ page_title }}}}</title>
<meta name="description" content="{{{{ seo_description }}}}">
<meta name="keywords" content="{{{{ seo_keywords|join(', ') }}}}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {{
{css_vars}
}}
{common_css}
{{{{ custom_css }}}}
{extra_css}
</style>
</head>
<body>

{nav}

<body>
{body}

{footer}

</body>
</html>"""

    return html


TEMPLATES = [
    ("minimal-corporate", "Minimal Corporate", "\u7b80\u7ea6\u5546\u52a1", "business",
     "--primary: #1a365d; --primary-light: #2b6cb0; --accent: #3182ce; --bg: #ffffff; --bg-alt: #f7fafc; --text: #2d3748; --text-light: #718096; --font: 'Inter', sans-serif; --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,0.1);",
     ""),
    ("modern-tech", "Modern Tech", "\u73b0\u4ee3\u79d1\u6280", "tech",
     "--primary: #0f172a; --primary-light: #1e293b; --accent: #06b6d4; --bg: #f8fafc; --bg-alt: #e2e8f0; --text: #0f172a; --text-light: #64748b; --font: 'Inter', sans-serif; --radius: 4px; --shadow: 0 4px 6px rgba(0,0,0,0.05);",
     ""),
    ("nature-green", "Nature Green", "\u81ea\u7136\u7eff", "eco",
     "--primary: #065f46; --primary-light: #059669; --accent: #10b981; --bg: #f0fdf4; --bg-alt: #dcfce7; --text: #14532d; --text-light: #6b7280; --font: 'Inter', sans-serif; --radius: 12px; --shadow: 0 2px 8px rgba(5,150,105,0.15);",
     ""),
    ("luxury-gold", "Luxury Gold", "\u5962\u534e\u91d1", "premium",
     "--primary: #1a0e00; --primary-light: #3d2b1f; --accent: #c9a94e; --bg: #fdfbf7; --bg-alt: #f5f0e8; --text: #1a0e00; --text-light: #8b7355; --font: 'Playfair Display', 'Inter', serif; --radius: 0px; --shadow: 0 8px 32px rgba(201,169,78,0.1);",
     ""),
    ("startup-vibrant", "Startup Vibrant", "\u521b\u4e1a\u6d3b\u529b", "startup",
     "--primary: #7c3aed; --primary-light: #a78bfa; --accent: #f59e0b; --bg: #ffffff; --bg-alt: #f5f3ff; --text: #1e1b4b; --text-light: #7c3aed; --font: 'Inter', sans-serif; --radius: 16px; --shadow: 0 10px 40px rgba(124,58,237,0.1);",
     ""),
    ("industrial-bold", "Industrial Bold", "\u5de5\u4e1a\u7c97\u72c2", "industry",
     "--primary: #27272a; --primary-light: #52525b; --accent: #f97316; --bg: #fafafa; --bg-alt: #e4e4e7; --text: #18181b; --text-light: #71717a; --font: 'Inter', sans-serif; --radius: 2px; --shadow: 0 1px 0 rgba(0,0,0,0.2);",
     ""),
    ("minimal-white", "Pure White", "\u7eaf\u767d\u6781\u7b80", "minimal",
     "--primary: #000000; --primary-light: #333333; --accent: #666666; --bg: #ffffff; --bg-alt: #f5f5f5; --text: #111111; --text-light: #888888; --font: 'Inter', sans-serif; --radius: 0px; --shadow: 0 0 0 transparent;",
     ""),
    ("dark-elegance", "Dark Elegance", "\u6697\u9ed1\u4f18\u96c5", "dark",
     "--primary: #0a0a0a; --primary-light: #1a1a1a; --accent: #a855f7; --bg: #0a0a0a; --bg-alt: #1a1a1a; --text: #fafafa; --text-light: #a1a1aa; --font: 'Inter', sans-serif; --radius: 12px; --shadow: 0 4px 20px rgba(168,85,247,0.15);",
     ""),
    ("gradient-modern", "Gradient Flow", "\u6e10\u53d8\u6d41\u52a8", "modern",
     "--primary: #0f0c29; --primary-light: #302b63; --accent: #24243e; --bg: #ffffff; --bg-alt: #f0f0ff; --text: #0f0c29; --text-light: #6b7280; --font: 'Inter', sans-serif; --radius: 20px; --shadow: 0 8px 32px rgba(48,43,99,0.1);",
     ""),
    ("neo-brutalism", "Neo Brutalism", "\u65b0\u7c97\u91ce\u4e3b\u4e49", "bold",
     "--primary: #ff4500; --primary-light: #ff6347; --accent: #0000ff; --bg: #ffffff; --bg-alt: #ffff00; --text: #000000; --text-light: #333333; --font: 'Inter', sans-serif; --radius: 0px; --shadow: 8px 8px 0px rgba(0,0,0,0.8);",
     ""),
    ("glassmorphism", "Glassmorphism", "\u73bb\u7483\u62df\u6001", "modern",
     "--primary: #0f172a; --primary-light: #1e293b; --accent: #818cf8; --bg: #0f172a; --bg-alt: #1e293b; --text: #f1f5f9; --text-light: #94a3b8; --font: 'Inter', sans-serif; --radius: 24px; --shadow: 0 8px 32px rgba(0,0,0,0.3);",
     "nav { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); } .service-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }"),
    ("cyberpunk", "Cyberpunk", "\u8d5b\u535a\u670b\u514b", "edgy",
     "--primary: #0a0a0f; --primary-light: #1a1a2e; --accent: #ffff00; --bg: #0a0a0f; --bg-alt: #1a1a2e; --text: #e0e0ff; --text-light: #8080aa; --font: 'Courier New', monospace; --radius: 0px; --shadow: 0 0 20px rgba(0,255,255,0.3);",
     ".hero { border-bottom: 2px solid #0ff; } .service-card { border: 1px solid rgba(0,255,255,0.2); } .hero .btn { border: 2px solid #0ff; background: transparent; } .hero .btn:hover { background: #0ff; color: #000; }"),
    ("japanese-minimal", "Japanese Zen", "\u548c\u98ce\u7985\u610f", "zen",
     "--primary: #2d1f00; --primary-light: #5c4033; --accent: #c04000; --bg: #f5f0eb; --bg-alt: #ede4db; --text: #2d1f00; --text-light: #8b7355; --font: 'Georgia', serif; --radius: 0px; --shadow: 0 1px 3px rgba(45,31,0,0.1);",
     ""),
    ("bold-typography", "Bold Type", "\u5927\u5b57\u6392\u7248", "editorial",
     "--primary: #111827; --primary-light: #374151; --accent: #ef4444; --bg: #ffffff; --bg-alt: #f3f4f6; --text: #111827; --text-light: #6b7280; --font: 'Inter', sans-serif; --radius: 0px; --shadow: 0 0 0 transparent;",
     ".hero h1 { font-size: 5rem; letter-spacing: -2px; } .section-title { font-size: 3rem; letter-spacing: -1px; }"),
    ("card-based", "Card Grid", "\u5361\u7247\u7f51\u683c", "clean",
     "--primary: #1e3a5f; --primary-light: #2d5a8e; --accent: #3b82f6; --bg: #f0f4f8; --bg-alt: #e2e8f0; --text: #1e293b; --text-light: #64748b; --font: 'Inter', sans-serif; --radius: 16px; --shadow: 0 4px 16px rgba(0,0,0,0.08);",
     ""),
    ("magazine", "Magazine", "\u6742\u5fd7\u98ce\u683c", "editorial",
     "--primary: #1a1a2e; --primary-light: #2d2d44; --accent: #e94560; --bg: #ffffff; --bg-alt: #f8f8f8; --text: #1a1a2e; --text-light: #7f8c8d; --font: 'Playfair Display', 'Inter', serif; --radius: 0px; --shadow: 0 2px 4px rgba(0,0,0,0.05);",
     ".hero { text-align: left; } .hero h1 { font-size: 4rem; font-style: italic; } .section-title { font-size: 2.5rem; font-style: italic; text-align: left; }"),
    ("retro-vintage", "Retro Vintage", "\u590d\u53e4\u98ce", "vintage",
     "--primary: #8b4513; --primary-light: #a0522d; --accent: #deb887; --bg: #fef9ef; --bg-alt: #f5e6cc; --text: #3e2723; --text-light: #8d6e63; --font: 'Georgia', serif; --radius: 4px; --shadow: 0 2px 8px rgba(139,69,19,0.1);",
     ""),
    ("material-design", "Material Design", "Material \u8bbe\u8ba1", "google",
     "--primary: #1565c0; --primary-light: #42a5f5; --accent: #ff6f00; --bg: #fafafa; --bg-alt: #f5f5f5; --text: #212121; --text-light: #757575; --font: 'Inter', sans-serif; --radius: 4px; --shadow: 0 2px 4px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);",
     ".hero .btn { text-transform: uppercase; letter-spacing: 1px; }"),
    ("brutalist", "Brutalist Heavy", "\u7c97\u91ce\u4e3b\u4e49", "raw",
     "--primary: #c0c0c0; --primary-light: #e0e0e0; --accent: #ff0000; --bg: #808080; --bg-alt: #999999; --text: #000000; --text-light: #333333; --font: 'Courier New', monospace; --radius: 0px; --shadow: 4px 4px 0px #000000;",
     ""),
    ("fluid-organic", "Fluid Organic", "\u6d41\u4f53\u6709\u673a", "creative",
     "--primary: #0d4f4f; --primary-light: #1a7a7a; --accent: #e8a87c; --bg: #f7f3ee; --bg-alt: #ede4db; --text: #2d2d2d; --text-light: #7a7a7a; --font: 'Inter', sans-serif; --radius: 30px 10px; --shadow: 0 10px 40px rgba(13,79,79,0.08);",
     ".hero { border-radius: 0 0 50% 50% / 20px; } .service-card { border-radius: 30px 10px; }"),
]


def generate_all():
    DIR.mkdir(exist_ok=True)

    # Remove old flat .html files
    for f in list(DIR.glob("*.html")):
        if f.name != "generate_templates.py":
            f.unlink()

    meta = []
    for name, display_name, display_name_zh, category, css_vars, extra_css in TEMPLATES:
        folder = DIR / name
        folder.mkdir(exist_ok=True)

        for page in ["index", "products", "about", "blog", "contact"]:
            html = make_page(page, css_vars, extra_css)
            (folder / f"{page}.html").write_text(html, encoding="utf-8")

        meta.append({"name": name, "display_name": display_name, "display_name_zh": display_name_zh, "category": category})
        print(f"  OK {name}/ (5 pages)")

    import json
    (DIR / "_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone! {len(TEMPLATES)} template folders (100 pages)")


if __name__ == "__main__":
    generate_all()
