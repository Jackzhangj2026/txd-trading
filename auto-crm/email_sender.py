"""
TXD CO., LTD — Automated Email Sender
Sends beautiful HTML development emails with embedded product images.
"""

import smtplib, ssl, json, base64, datetime, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import os as _os
_BASE_DIR = Path(_os.environ.get('AUTO_CRM_DIR', str(Path('.').resolve())))
DATA_DIR = _BASE_DIR / "data"
TEMPLATE_DIR = _BASE_DIR / "templates"
CONFIG_FILE = DATA_DIR / "email_config.json"
SENT_LOG = DATA_DIR / "sent_log.json"

DEFAULT_CONFIG = {
    "sender_name": "TXD CO., LTD Sales Team",
    "sender_email": "",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "smtp_password": "",
    "daily_limit": 20,
    "interval_min": 180,
    "enabled": False,
}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def load_sent_log():
    if SENT_LOG.exists():
        return json.loads(SENT_LOG.read_text(encoding="utf-8"))
    return []

def save_sent_log(log):
    SENT_LOG.write_text(json.dumps(log[-500:], indent=2), encoding="utf-8")

# ---------------------------------------------------------------------------
# Image to base64 (guarantees images show in email)
# ---------------------------------------------------------------------------

def image_to_base64(img_path):
    """Convert local image to base64 data URI for reliable email display"""
    path = Path(img_path)
    if not path.exists():
        return ""
    try:
        from PIL import Image
        img = Image.open(path)
        if img.width > 400:
            ratio = 400.0 / img.width
            h = int(img.height * ratio)
            img = img.resize((400, h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return "data:image/jpeg;base64," + b64
    except ImportError:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = path.suffix.lower().lstrip(".") or "jpg"
        if ext in ("jpg", "jpeg"):
            ext = "jpeg"
        return "data:image/" + ext + ";base64," + b64

# ---------------------------------------------------------------------------
# HTML template engine
# ---------------------------------------------------------------------------

def build_email_html(contact_name, company_name, website_url,
                     image_1=None, image_2=None, image_3=None, image_4=None):
    tpl = TEMPLATE_DIR / "email_template.html"
    if not tpl.exists():
        return _fallback_html(contact_name, company_name, website_url)
    html = tpl.read_text(encoding="utf-8")
    for k, v in [("{{CONTACT_NAME}}", contact_name or "Sir/Madam"),
                 ("{{COMPANY_NAME}}", company_name or "your company"),
                 ("{{WEBSITE_URL}}", website_url),
                 ("{{IMAGE_1}}", image_1 or ""),
                 ("{{IMAGE_2}}", image_2 or ""),
                 ("{{IMAGE_3}}", image_3 or ""),
                 ("{{IMAGE_4}}", image_4 or "")]:
        html = html.replace(k, v)
    return html

def _fallback_html(name, company, url):
    return (
        '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
        '<div style="background:linear-gradient(135deg,#1a1a2e,#6c5ce7);padding:30px;text-align:center;">'
        '<h1 style="color:#fff;margin:0;">TXD CO., LTD</h1>'
        '<p style="color:rgba(255,255,255,0.7);">PP Hollow Board &amp; Packaging Solutions</p></div>'
        '<div style="padding:30px;background:#fff;">'
        '<p>Dear <strong>' + name + '</strong>,</p>'
        '<p>This is TXD CO., LTD, a manufacturer and exporter of PP hollow sheets in Xiamen, China.</p>'
        '<p>We believe our products could bring value to ' + company + '.</p>'
        '<div style="background:#f8f7ff;border-radius:8px;padding:20px;margin:20px 0;">'
        '<p><strong>Our Advantages:</strong></p>'
        '<p>PP Hollow Sheets (2-20mm) | Custom Boxes | ESD Material</p>'
        '<p>Direct Factory Price | FOB/CIF Shipping | ISO 9001</p></div>'
        '<p>See more: <a href="' + url + '" style="color:#6c5ce7;">' + url + '</a></p></div>'
        '<div style="background:#1a1a2e;padding:20px;text-align:center;">'
        '<p style="color:rgba(255,255,255,0.6);font-size:12px;">'
        'TXD CO., LTD | Xiamen, China | 4621710@qq.com</p></div></div>'
    )

# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_email(to_email, subject, html_body, cc=None):
    cfg = load_config()
    if not cfg.get("enabled") or not cfg.get("sender_email") or not cfg.get("smtp_password"):
        return {"success": False, "error": "Not configured. Run: python email_sender.py --setup"}
    msg = MIMEMultipart("alternative")
    msg["From"] = '"' + cfg["sender_name"] + '" <' + cfg["sender_email"] + ">"
    msg["To"] = to_email
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        context = ssl.create_default_context()
        port = cfg.get("smtp_port", 465)
        if port == 587:
            # TLS mode
            with smtplib.SMTP(cfg["smtp_server"], port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(cfg["sender_email"], cfg["smtp_password"])
                recipients = [to_email] + (cc or [])
                server.sendmail(cfg["sender_email"], recipients, msg.as_string())
        else:
            # SSL mode (default)
            with smtplib.SMTP_SSL(cfg["smtp_server"], port, context=context, timeout=30) as server:
                server.login(cfg["sender_email"], cfg["smtp_password"])
                recipients = [to_email] + (cc or [])
                server.sendmail(cfg["sender_email"], recipients, msg.as_string())
        log = load_sent_log()
        log.append({"to": to_email, "subject": subject, "time": datetime.datetime.now().isoformat(), "status": "sent"})
        save_sent_log(log)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Development email
# ---------------------------------------------------------------------------

def send_development_email(lead):
    name = lead.get("contact_person") or lead.get("company", "Sir/Madam")
    company = lead.get("company", "your company")
    email = lead.get("email", "")
    if not email:
        return {"success": False, "error": "No email"}
    subjects = [
        "Introduction from TXD CO., Ltd - PP Hollow Board Supplier",
        "Quick question about your packaging needs",
        "TXD CO., Ltd - PP Hollow Board Manufacturer in Xiamen",
        "Connection request from PP packaging supplier",
    ]
    subject = subjects[hash(email) % len(subjects)]
    img_dir = Path(__file__).parent / "email_images"
    img_1 = image_to_base64(img_dir / "product1-board.jpg")
    img_2 = image_to_base64(img_dir / "product2-box.jpg")
    img_3 = image_to_base64(img_dir / "product3-box.jpg")
    img_4 = image_to_base64(img_dir / "product4-esd.jpg")
    if not img_1:
        base_url = "https://jackzhangj2026.github.io/txd-trading"
        img_1 = base_url + "/images/products/sheets/IMG_20250425_154200.jpg"
        img_2 = base_url + "/images/products/boxes/mmexport1735607614973.jpg"
        img_3 = base_url + "/images/products/boxes/mmexport1735607619501.jpg"
        img_4 = base_url + "/images/products/sheets/IMG_20250912_144714.jpg"
        img_3 = base_url + "/images/products/boxes/mmexport1735607619501.jpg"
        img_4 = base_url + "/images/products/sheets/IMG_20250912_144714.jpg"
    html = build_email_html(name, company, "https://jackzhangj2026.github.io/txd-trading/",
                            img_1, img_2, img_3, img_4)
    return send_email(email, subject, html)

# ---------------------------------------------------------------------------
# Batch send
# ---------------------------------------------------------------------------

def send_daily_batch(leads, dry_run=False):
    cfg = load_config()
    if not dry_run and (not cfg.get("enabled") or not cfg.get("sender_email")):
        return {"error": "Not configured"}
    max_send = cfg.get("daily_limit", 20)
    interval = cfg.get("interval_min", 180)
    sent, failed = [], []
    total = min(len(leads), max_send)
    for i, lead in enumerate(leads[:total]):
        if dry_run:
            sent.append({"to": lead.get("email"), "company": lead.get("company")})
            continue
        result = send_development_email(lead)
        if result["success"]:
            sent.append(lead.get("email"))
        else:
            failed.append({"email": lead.get("email"), "error": result.get("error")})
        if i < total - 1:
            time.sleep(interval)
    return {"dry_run": dry_run, "target": total, "sent": sent, "failed": failed,
            "sent_count": len(sent), "failed_count": len(failed)}

# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

def setup_email():
    print()
    print("=" * 50)
    print("TXD CO., LTD - Email Configuration")
    print("=" * 50)
    cfg = load_config()
    email = input("Email [" + cfg.get("sender_email", "") + "]: ").strip()
    if email:
        cfg["sender_email"] = email
    pwd = input("SMTP Password/App Password: ").strip()
    if pwd:
        cfg["smtp_password"] = pwd
    server = input("SMTP Server [" + cfg.get("smtp_server", "smtp.qq.com") + "]: ").strip()
    if server:
        cfg["smtp_server"] = server
    port_str = input("SMTP Port [" + str(cfg.get("smtp_port", 465)) + "]: ").strip()
    if port_str:
        cfg["smtp_port"] = int(port_str)
    limit_str = input("Daily Limit [" + str(cfg.get("daily_limit", 20)) + "]: ").strip()
    if limit_str:
        cfg["daily_limit"] = int(limit_str)
    cfg["enabled"] = True
    save_config(cfg)
    print("Saved!")
    test = input("Send test? (y/n): ").strip().lower()
    if test == "y":
        img_dir = Path(__file__).parent / "email_images"
        i1 = image_to_base64(img_dir / "product1-board.jpg")
        i2 = image_to_base64(img_dir / "product2-box.jpg")
        i3 = image_to_base64(img_dir / "product3-box.jpg")
        i4 = image_to_base64(img_dir / "product4-esd.jpg")
        html = build_email_html("Test", "Test Co", "https://jackzhangj2026.github.io/txd-trading/",
                                i1, i2, i3, i4)
        r = send_email(cfg["sender_email"], "TXD CO., LTD - Test with Product Images", html)
        if r["success"]:
            print("Test sent! Check your inbox for images.")
        else:
            print("Failed: " + r.get("error", "unknown"))
    return cfg

def get_send_stats():
    log = load_sent_log()
    today = datetime.date.today().isoformat()
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    return {
        "total_sent": len(log),
        "today_sent": sum(1 for l in log if l["time"][:10] == today),
        "week_sent": sum(1 for l in log if l["time"][:10] >= week_ago),
        "daily_limit": load_config().get("daily_limit", 20),
    }

if __name__ == "__main__":
    import sys as _s
    if "--setup" in _s.argv:
        setup_email()
    elif "--stats" in _s.argv:
        import json as _j
        print(_j.dumps(get_send_stats(), indent=2))
    else:
        c = load_config()
        if c.get("enabled"):
            s = get_send_stats()
            print("Today: %d/%d" % (s["today_sent"], s["daily_limit"]))
        else:
            print("Use --setup")
