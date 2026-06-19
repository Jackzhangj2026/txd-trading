"""Email intelligence engine — ported from OpenLeads (openleads/emails/).

Pure functions for email permutation, pattern learning, and consensus scoring.
Zero network dependencies — integrates with TXD's SQLAlchemy models.
"""

from __future__ import annotations
import re
import sqlite3
from pathlib import Path

# ─── Local-part templates (most-likely first) ───────────────────────────
PATTERN_TEMPLATES = (
    "{first}.{last}",
    "{first}",
    "{first}{last}",
    "{f}{last}",
    "{first}_{last}",
    "{f}.{last}",
    "{last}",
    "{last}.{first}",
    "{first}.{f}",
    "{last}{f}",
)

ROLE_LOCALS = {
    "info", "admin", "support", "sales", "hello", "contact", "team", "office",
    "help", "billing", "careers", "jobs", "press", "media", "noreply", "no-reply",
    "webmaster", "postmaster", "abuse", "marketing", "hr", "legal", "accounts",
    "enquiries", "inquiries", "general", "mail", "newsletter", "notifications",
}

FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com",
    "pm.me", "gmx.com", "gmx.de", "mail.com", "zoho.com", "yandex.com",
    "fastmail.com", "hey.com", "tutanota.com", "tuta.io",
    "qq.com", "163.com", "126.com",
}

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "yopmail.com", "throwawaymail.com", "getnada.com",
    "temp-mail.org", "sharklasers.com", "grr.la", "maildrop.cc",
    "dispostable.com", "fakeinbox.com", "mailnesia.com",
}

# ─── Name parsing ────────────────────────────────────────────────────────

def name_parts(full_name: str) -> tuple[str | None, str | None]:
    """Split a display name into (first, last) tokens, ASCII-folded."""
    toks = [re.sub(r"[^a-z]", "", t.lower()) for t in (full_name or "").split()]
    toks = [t for t in toks if t]
    if not toks:
        return None, None
    return toks[0], toks[-1] if len(toks) > 1 else ""


def fill(template: str, first: str, last: str) -> str | None:
    """Render a local-part template. None if a needed part is missing."""
    if not first:
        return None
    f = first[0] if first else ""
    l = last[0] if last else ""
    if ("{last}" in template or "{l}" in template) and not last:
        return None
    try:
        return template.format(first=first, last=last, f=f, l=l)
    except (KeyError, IndexError):
        return None


# ─── Candidate generation ────────────────────────────────────────────────

def candidate_emails(full_name: str, domain: str) -> list[str]:
    """Generate likely email addresses for a name at a domain, best first."""
    first, last = name_parts(full_name)
    if not first:
        return []
    if not last:
        return [f"{first}@{domain}"]
    seen, out = set(), []
    for tmpl in PATTERN_TEMPLATES:
        lp = fill(tmpl, first, last)
        if lp and lp not in seen:
            seen.add(lp)
            out.append(f"{lp}@{domain}")
    return out


# ─── Classification helpers ──────────────────────────────────────────────

def is_role_account(email: str) -> bool:
    """True if the local-part is a generic/role mailbox."""
    return email.split("@", 1)[0].lower() in ROLE_LOCALS


def is_disposable(domain: str) -> bool:
    """True if the domain is a known disposable/throwaway provider."""
    return (domain or "").lower() in DISPOSABLE_DOMAINS


def is_free_provider(domain: str) -> bool:
    """True if the domain is a free/personal mailbox provider."""
    return (domain or "").lower() in FREE_PROVIDERS


def is_common_pattern(email: str, full_name: str) -> bool:
    """True if email uses first or first.last pattern."""
    first, last = name_parts(full_name)
    if not first:
        return False
    local = email.split("@", 1)[0].lower()
    common = {first}
    if last:
        common.add(f"{first}.{last}")
    return local in common


# ─── Pattern learning ────────────────────────────────────────────────────

def derive_pattern(local_part: str, full_name: str) -> str | None:
    """Infer which PATTERN_TEMPLATES produced this local_part for this name."""
    first, last = name_parts(full_name)
    if not first:
        return None
    local = (local_part or "").lower().strip()
    matches = []
    for tmpl in PATTERN_TEMPLATES:
        rendered = fill(tmpl, first, last)
        if rendered and rendered == local:
            matches.append(tmpl)
    if not matches:
        return None
    matches.sort(key=lambda t: len(fill(t, first, last) or ""), reverse=True)
    return matches[0]


def learn_from_email(email: str, full_name: str, db_path: str = "trade_agent.db") -> str | None:
    """Derive a pattern from a real email and persist it to SQLite.

    Skips free providers — their patterns don't generalize.
    """
    if not email or "@" not in email:
        return None
    local, _, domain = email.lower().partition("@")
    if is_free_provider(domain):
        return None
    pattern = derive_pattern(local, full_name)
    if pattern:
        _upsert_pattern(db_path, domain, pattern)
    return pattern


def learned_candidates(full_name: str, domain: str, db_path: str = "trade_agent.db") -> list[str]:
    """Emails for full_name built from patterns already learned for domain."""
    if not domain:
        return []
    first, last = name_parts(full_name)
    if not first:
        return []
    out = []
    for row in _get_patterns(db_path, domain):
        rendered = fill(row[0], first, last)
        if rendered:
            addr = f"{rendered}@{domain.lower()}"
            if addr not in out:
                out.append(addr)
    return out


# ─── Internal DB helpers ─────────────────────────────────────────────────

def _upsert_pattern(db_path: str, domain: str, pattern: str):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS email_patterns (domain TEXT NOT NULL, pattern TEXT NOT NULL, support INTEGER DEFAULT 1, PRIMARY KEY (domain, pattern))"
    )
    conn.execute(
        "INSERT INTO email_patterns (domain, pattern, support) VALUES (?, ?, 1) "
        "ON CONFLICT(domain, pattern) DO UPDATE SET support = support + 1",
        (domain, pattern),
    )
    conn.commit()
    conn.close()


def _get_patterns(db_path: str, domain: str) -> list[tuple[str, int]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT pattern, support FROM email_patterns WHERE domain = ? ORDER BY support DESC",
            (domain,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows


# ─── Consensus scoring (from OpenLeads score.py) ────────────────────────

def assess(signals: dict) -> dict:
    """Fold signals into {score, tier, confidence, reasons, confidence_pct}.

    tier: 'safe' | 'risky' | 'bad'
    """
    reasons = []

    # Hard fails
    if not signals.get("mx_exists"):
        return _verdict(0, "bad", "none", ["no mail server (no MX record)"])
    if signals.get("disposable"):
        return _verdict(0, "bad", "none", ["disposable / throwaway domain"])
    if signals.get("no_candidates"):
        return _verdict(0, "bad", "none", ["couldn't form an address from the name"])

    free = signals.get("free_provider")
    role = signals.get("role_account")

    # Infrastructure health
    health = 0
    if signals.get("mx_resolvers_ok", 0) >= 2:
        health += 1
    if signals.get("mx_agreement"):
        health += 1
    if signals.get("spf_present"):
        health += 1
        reasons.append("SPF configured")
    if signals.get("dmarc_present"):
        health += 1
        reasons.append("DMARC configured")
    healthy = health >= 2
    pro_host = signals.get("mx_provider") in ("google", "microsoft", "zoho", "proton")

    # Ground truth — published address
    if signals.get("groundtruth_exact"):
        reasons.insert(0, "found publicly (ground-truth address)")
        return _verdict(98, "safe", "verified", reasons, pct=98)

    # SMTP verified
    if signals.get("smtp_verified") and not signals.get("catch_all"):
        reasons.insert(0, "SMTP-verified mailbox")
        score = 90 + (4 if signals.get("mx_agreement") else 0) + (3 if signals.get("common_pattern") else 0)
        return _verdict(score, "safe", "verified", reasons, role, pct=min(99, score + 5))

    gravatar = signals.get("gravatar")
    learned = signals.get("learned_pattern_match")
    observed = signals.get("observed_pattern")
    common = signals.get("common_pattern")

    if gravatar:
        reasons.insert(0, "Gravatar profile exists")
    if observed:
        reasons.insert(0, "built from observed domain pattern")
    elif learned:
        reasons.insert(0, "matches learned domain pattern")

    # Free provider: can't guess
    if free:
        if gravatar:
            return _verdict(82, "safe", "verified", reasons + ["personal mailbox, confirmed"], role, pct=82)
        return _verdict(15, "bad", "none", ["personal mailbox — can't guess"], role, pct=10)

    # Corporate domain guesses
    if observed and not signals.get("catch_all"):
        score = 88 if healthy else 82
        return _verdict(score, "safe", "verified", reasons, role, pct=score)

    if learned and (gravatar or signals.get("smtp_reachable")) and not signals.get("catch_all"):
        return _verdict(86 if healthy else 80, "safe", "verified", reasons, role, pct=84)

    if gravatar and (common or learned) and healthy and not signals.get("catch_all"):
        return _verdict(80, "safe", "verified", reasons, role, pct=80)

    if learned and not signals.get("catch_all"):
        reasons.append("learned pattern, not yet confirmed")
        return _verdict(66, "risky", "pattern_guess", reasons, role, pct=66)

    # Uncertain → risky
    if signals.get("catch_all"):
        reasons.append("catch-all domain — accepts anything")
        score = 48 + (4 if common else 0) + (4 if gravatar else 0)
        return _verdict(score, "risky", "catch_all_guess", reasons, role, pct=min(score, 50))

    if signals.get("smtp_reachable"):
        reasons.append("server reachable but didn't confirm this address")
        return _verdict(38 + (5 if common else 0), "risky", "pattern_guess", reasons, role, pct=45 + (8 if common else 0))

    if signals.get("port25_blocked"):
        reasons.append("verification port 25 blocked — pattern + infra scored")
    else:
        reasons.append("mail server didn't answer")

    base = 34 + (6 if common else 0) + (6 if gravatar else 0) + (4 if healthy else 0)
    pct = 35
    if common and pro_host and healthy:
        pct = 62
        reasons.insert(0, "common pattern on professionally-hosted domain")
    elif common and healthy:
        pct = 52
    return _verdict(base, "risky", "pattern_guess", reasons, role, pct=pct)


def _verdict(score: int, tier: str, confidence: str, reasons: list, role: bool = False,
             pct: int | None = None) -> dict:
    if role:
        score = max(0, score - 25)
        reasons = reasons + ["role/shared mailbox (not a person)"]
        if tier == "safe":
            tier = "risky"
        if pct is not None:
            pct = max(0, pct - 20)
    score = max(0, min(100, score))
    return {
        "score": score,
        "tier": tier,
        "confidence": confidence,
        "reasons": reasons,
        "confidence_pct": max(0, min(100, pct if pct is not None else score)),
    }


# ─── Quick check for existing customers ─────────────────────────────────

def enrich_customer(name: str, company: str, email: str = "", db_path: str = "trade_agent.db") -> dict:
    """Analyze a customer's email and return intelligence.

    If no email, generates candidates from name + company domain.
    """
    result = {
        "name": name,
        "company": company,
        "email": email,
        "candidates": [],
        "learned_candidates": [],
        "assessment": None,
    }

    domain = ""
    if email and "@" in email:
        domain = email.rsplit("@", 1)[-1].lower()
        result["is_role"] = is_role_account(email)
        result["is_free"] = is_free_provider(domain)
        result["is_disposable"] = is_disposable(domain)
        result["is_common"] = is_common_pattern(email, name)

        # Score the email
        signals = {
            "mx_exists": True,
            "disposable": result["is_disposable"],
            "no_candidates": False,
            "free_provider": result["is_free"],
            "role_account": result["is_role"],
            "common_pattern": result["is_common"],
            "learned_pattern_match": email.lower() in learned_candidates(name, domain, db_path),
            "observed_pattern": bool(learned_candidates(name, domain, db_path)),
        }
        result["assessment"] = assess(signals)

    # If company website domain can be inferred
    if company and not domain:
        # Try to guess domain from company name
        clean = re.sub(r"[^a-z0-9]", "", company.lower())
        if clean:
            # Try common TLDs
            for tld in [".com", ".de", ".co.uk", ".fr", ".it", ".nl", ".pl"]:
                result["candidates"] = candidate_emails(name, clean + tld)
                if result["candidates"]:
                    break

    if domain:
        result["candidates"] = candidate_emails(name, domain)
        result["learned_candidates"] = learned_candidates(name, domain, db_path)

    return result
