"""Admin panel routes — Jinja2 + HTMX based management interface."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/inquiries", response_class=HTMLResponse)
async def admin_inquiries(request: Request):
    return templates.TemplateResponse("inquiries.html", {"request": request})


@router.get("/customers", response_class=HTMLResponse)
async def admin_customers(request: Request):
    return templates.TemplateResponse("customers.html", {"request": request})


@router.get("/content", response_class=HTMLResponse)
async def admin_content(request: Request):
    return templates.TemplateResponse("content.html", {"request": request})
