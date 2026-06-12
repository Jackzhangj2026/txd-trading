"""Admin panel routes — Jinja2 + HTMX based management interface."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from backend.admin.i18n import t, js_translations

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(prefix="/admin", tags=["admin"])


def get_lang(request: Request) -> str:
    """Get language preference from cookie, default 'en'."""
    return request.cookies.get("lang", "en")


def render(request: Request, template: str):
    """Render template with language context."""
    lang = get_lang(request)
    return templates.TemplateResponse(
        request, template,
        {"lang": lang, "_t": lambda key: t(key, lang), "_js_t": js_translations(lang)}
    )


@router.get("/set-lang/{lang}")
async def set_language(lang: str, request: Request):
    """Set language preference via cookie and redirect back."""
    referer = request.headers.get("referer", "/admin")
    response = Response(status_code=302)
    response.headers["Location"] = referer
    if lang in ("en", "zh"):
        response.set_cookie(key="lang", value=lang, max_age=31536000, path="/admin")
    return response


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return render(request, "dashboard.html")


@router.get("/inquiries", response_class=HTMLResponse)
async def admin_inquiries(request: Request):
    return render(request, "inquiries.html")


@router.get("/customers", response_class=HTMLResponse)
async def admin_customers(request: Request):
    return render(request, "customers.html")


@router.get("/emails", response_class=HTMLResponse)
async def admin_emails(request: Request):
    return render(request, "emails.html")


@router.get("/markets", response_class=HTMLResponse)
async def admin_markets(request: Request):
    return render(request, "markets.html")


@router.get("/content", response_class=HTMLResponse)
async def admin_content(request: Request):
    return render(request, "content.html")


@router.get("/social", response_class=HTMLResponse)
async def admin_social(request: Request):
    return render(request, "social.html")
