# Phase 1: Infrastructure Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python backend foundation — FastAPI app skeleton, database models, LLM provider abstraction, admin panel base, and project structure for the TXD Trade Agent System.

**Architecture:** Single FastAPI application with SQLAlchemy ORM (SQLite for dev, PostgreSQL for prod), LiteLLM for LLM abstraction, Jinja2+HTMX for admin panel. All routes organized by domain module. Background tasks via APScheduler.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, LiteLLM, Jinja2, HTMX (CDN), APScheduler, Pydantic v2

---

### Task 1: Project skeleton + core dependencies

**Files:**
- Create: `E:\hollowsheet\backend\requirements.txt`
- Create: `E:\hollowsheet\backend\.env.example`
- Create: `E:\hollowsheet\backend\__init__.py`

- [ ] **Step 1: Create requirements.txt**

```txt
# TXD Trade Agent System — Python Dependencies
# Core framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0
pydantic-settings==2.7.0

# Database
sqlalchemy==2.0.36
alembic==1.14.0
aiosqlite==0.20.0

# LLM abstraction
litellm==1.55.0

# Task scheduling
apscheduler==3.10.4

# Admin panel
jinja2==3.1.4
python-multipart==0.0.12
aiofiles==24.1.0

# Email (Phase 3+)
# httpx==0.28.0
# python-dotenv==1.0.1

# Dev
# pytest==8.3.0
# httpx==0.28.0 (for test client)
```

- [ ] **Step 2: Create .env.example**

```env
# === LLM Provider ===
# Change this to switch the LLM provider
ACTIVE_LLM=deepseek

# DeepSeek
DEEPSEEK_API_KEY=sk-your-deepseek-key-here

# OpenAI (optional, uncomment to use)
# OPENAI_API_KEY=sk-your-openai-key-here

# Anthropic (optional, uncomment to use)
# ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# === Database ===
# Default: SQLite (development)
DATABASE_URL=sqlite+aiosqlite:///./trade_agent.db
# Production: PostgreSQL (uncomment for prod)
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trade_agent

# === Email (for Phase 3) ===
# SMTP_DEFAULT_FROM=sales@txd.com

# === App ===
SECRET_KEY=change-this-to-a-random-string
DEBUG=true
```

- [ ] **Step 3: Create `backend/__init__.py`** (empty file)

- [ ] **Step 4: Create the directories**

```bash
mkdir -p backend/models backend/schemas backend/routers backend/services backend/agents backend/tasks backend/admin/templates backend/admin/static
```

- [ ] **Step 5: Install dependencies**

```bash
cd E:\hollowsheet
pip install -r backend\requirements.txt
```

Expected: all packages install successfully.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/__init__.py
git commit -m "feat: add backend project skeleton and dependencies"
```

---

### Task 2: FastAPI application entry point

**Files:**
- Create: `E:\hollowsheet\backend\main.py`
- Create: `E:\hollowsheet\backend\config.py`

- [ ] **Step 1: Create config.py**

```python
"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Provider
    active_llm: Literal["deepseek", "openai", "claude", "gemini", "qwen", "ollama"] = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./trade_agent.db"

    # App
    secret_key: str = "change-this-to-a-random-string"
    debug: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 2: Create main.py**

```python
"""TXD Trade Agent System — FastAPI Application Entry Point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

app = FastAPI(
    title="TXD Trade Agent API",
    description="International trade intelligence agent system for TXD CO., LTD",
    version="0.1.0",
)

# CORS — allow GitHub Pages frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0", "llm_provider": settings.active_llm}
```

- [ ] **Step 3: Test the app starts**

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Expected: Server starts on http://127.0.0.1:8000. Visit http://127.0.0.1:8000/api/health → `{"status":"ok","version":"0.1.0","llm_provider":"deepseek"}`

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/config.py
git commit -m "feat: add FastAPI app entry point and config"
```

---

### Task 3: Database foundation — engine, session, base model

**Files:**
- Create: `E:\hollowsheet\backend\database.py`
- Create: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\models\base.py`

- [ ] **Step 1: Create database.py**

```python
"""Database engine, session factory, and lifecycle."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from backend.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables (dev convenience — use Alembic in prod)."""
    from backend.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 2: Create models/base.py**

```python
"""Declarative base with common mixins."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UUIDMixin:
    """Adds a string UUID primary key."""

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
```

- [ ] **Step 3: Create models/__init__.py**

```python
from backend.models.base import Base, UUIDMixin, TimestampMixin
```

- [ ] **Step 4: Test DB initializes**

Add to main.py (temporarily):

```python
from contextlib import asynccontextmanager
from backend.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# Change the FastAPI instantiation to use lifespan
app = FastAPI(..., lifespan=lifespan)
```

Run `uvicorn backend.main:app --reload` and check that `trade_agent.db` is created.

- [ ] **Step 5: Commit**

```bash
git add backend/database.py backend/models/
git commit -m "feat: add database engine, session, base model"
```

---

### Task 4: Core data models — Product, Customer, Inquiry

**Files:**
- Modify: `E:\hollowsheet\backend\models\__init__.py`
- Create: `E:\hollowsheet\backend\models\product.py`
- Create: `E:\hollowsheet\backend\models\customer.py`
- Create: `E:\hollowsheet\backend\models\inquiry.py`
- Create: `E:\hollowsheet\backend\schemas\__init__.py`
- Create: `E:\hollowsheet\backend\schemas\product.py`
- Create: `E:\hollowsheet\backend\schemas\customer.py`
- Create: `E:\hollowsheet\backend\schemas\inquiry.py`

- [ ] **Step 1: Create models/product.py**

```python
"""Product model — PP hollow sheets, boxes, and future categories."""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    name_zh: Mapped[str] = mapped_column(String(200), default="")
    name_en: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # sheet / box / catalog
    description: Mapped[str] = mapped_column(Text, default="")
    description_zh: Mapped[str] = mapped_column(Text, default="")
    specs: Mapped[str] = mapped_column(Text, default="{}")  # JSON string
    images: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of URLs
    active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 2: Create models/customer.py**

```python
"""Customer/Lead model — tracks prospects and clients."""

from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), index=True, default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    company: Mapped[str] = mapped_column(String(200), index=True, default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(50), default="")  # website / email / alibaba / linkedin / import
    score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100 lead score
    matched_market: Mapped[str] = mapped_column(String(100), default="")  # Target market name
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
```

- [ ] **Step 3: Create models/inquiry.py**

```python
"""Inquiry model — contact form submissions and their classifications."""

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDMixin, TimestampMixin


class Inquiry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inquiries"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new / classified / replied / closed
    classification: Mapped[str] = mapped_column(String(20), default="")  # high / medium / low / spam
    source: Mapped[str] = mapped_column(String(50), default="website")  # website / email / alibaba
    ai_summary: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 4: Create schemas (Pydantic)**

Create `backend/schemas/product.py`:

```python
"""Product Pydantic schemas for API request/response."""

from datetime import datetime
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name_en: str
    name_zh: str = ""
    category: str
    description: str = ""
    description_zh: str = ""
    specs: str = "{}"
    images: str = "[]"


class ProductUpdate(BaseModel):
    name_en: str | None = None
    name_zh: str | None = None
    category: str | None = None
    description: str | None = None
    description_zh: str | None = None
    specs: str | None = None
    images: str | None = None
    active: bool | None = None


class ProductResponse(BaseModel):
    id: str
    name_en: str
    name_zh: str
    category: str
    description: str
    description_zh: str
    specs: str
    images: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductList(BaseModel):
    items: list[ProductResponse]
    total: int
```

Create `backend/schemas/customer.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    country: str = ""
    source: str = ""
    notes: str = ""


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    country: str | None = None
    source: str | None = None
    score: int | None = None
    matched_market: str | None = None
    notes: str | None = None
    tags: str | None = None


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    company: str
    country: str
    source: str
    score: int
    matched_market: str
    notes: str
    tags: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerList(BaseModel):
    items: list[CustomerResponse]
    total: int
```

Create `backend/schemas/inquiry.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class InquiryCreate(BaseModel):
    customer_id: str | None = None
    product_id: str | None = None
    message: str
    source: str = "website"


class InquiryUpdate(BaseModel):
    status: str | None = None
    classification: str | None = None
    ai_summary: str | None = None


class InquiryResponse(BaseModel):
    id: str
    customer_id: str | None
    product_id: str | None
    message: str
    status: str
    classification: str
    source: str
    ai_summary: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InquiryList(BaseModel):
    items: list[InquiryResponse]
    total: int
```

Create `backend/schemas/__init__.py`:

```python
from backend.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductList
from backend.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerList
from backend.schemas.inquiry import InquiryCreate, InquiryUpdate, InquiryResponse, InquiryList
```

- [ ] **Step 5: Update models/__init__.py**

```python
from backend.models.base import Base, UUIDMixin, TimestampMixin
from backend.models.product import Product
from backend.models.customer import Customer
from backend.models.inquiry import Inquiry
```

- [ ] **Step 6: Test models import correctly**

```bash
cd E:\hollowsheet
python -c "from backend.database import init_db; import asyncio; asyncio.run(init_db()); print('DB initialized with all models')"
```

Expected: `trade_agent.db` created with tables `products`, `customers`, `inquiries`.

- [ ] **Step 7: Commit**

```bash
git add backend/models/ backend/schemas/
git commit -m "feat: add core data models — Product, Customer, Inquiry"
```

---

### Task 5: Product API CRUD routes

**Files:**
- Create: `E:\hollowsheet\backend\routers\__init__.py`
- Create: `E:\hollowsheet\backend\routers\products.py`
- Modify: `E:\hollowsheet\backend\main.py`

- [ ] **Step 1: Create routers/products.py**

```python
"""Product management API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.product import Product
from backend.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductList

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductList)
async def list_products(
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).where(Product.active == True)

    if category:
        query = query.where(Product.category == category)
    if search:
        query = query.where(Product.name_en.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Product.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return ProductList(items=items, total=total)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = Product(**data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, data: ProductUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.active = False  # Soft delete
    await db.commit()
```

- [ ] **Step 2: Create routers/__init__.py** (empty file)

- [ ] **Step 3: Register router in main.py**

Edit `backend/main.py` — add import and router registration:

```python
from backend.database import init_db
from backend.routers import products

# After app = FastAPI(...)
app.include_router(products.router)
```

Also ensure the `lifespan` context manager is set up:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(..., lifespan=lifespan)
```

- [ ] **Step 4: Test the API**

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Test in another terminal:
```bash
# Create a product
curl -X POST http://127.0.0.1:8000/api/products -H "Content-Type: application/json" -d "{\"name_en\":\"PP Hollow Sheet 4mm\",\"category\":\"sheet\"}"

# List products
curl http://127.0.0.1:8000/api/products
```

Expected: Product created and listed successfully. Visit http://127.0.0.1:8000/docs for auto-generated Swagger UI.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/ backend/main.py
git commit -m "feat: add Product CRUD API routes"
```

---

### Task 6: LLM provider abstraction

**Files:**
- Create: `E:\hollowsheet\backend\agents\__init__.py`
- Create: `E:\hollowsheet\backend\agents\base_agent.py`

- [ ] **Step 1: Create agents/base_agent.py**

```python
"""LLM provider abstraction — unified interface for any model provider."""

from typing import Any
from litellm import acompletion
from backend.config import settings

# Provider configuration map
LLM_PROVIDERS = {
    "deepseek": {
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "api_base": "https://api.openai.com/v1",
    },
    "claude": {
        "model": "claude-sonnet-4-20250514",
        "api_base": "https://api.anthropic.com",
    },
    "gemini": {
        "model": "gemini/gemini-2.0-flash",
        "api_base": "https://generativelanguage.googleapis.com",
    },
    "qwen": {
        "model": "openai/qwen-turbo",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "ollama": {
        "model": "ollama/llama3.2",
        "api_base": "http://localhost:11434",
    },
}


def get_provider_config(provider_name: str) -> dict[str, Any]:
    """Get provider configuration, falling back to deepseek."""
    provider = LLM_PROVIDERS.get(provider_name, LLM_PROVIDERS["deepseek"])
    config: dict[str, Any] = {
        "model": provider["model"],
        "api_base": provider["api_base"],
    }

    # Inject the correct API key
    api_key_map = {
        "deepseek": settings.deepseek_api_key,
        "openai": settings.openai_api_key,
        "claude": settings.anthropic_api_key,
    }
    if provider_name in api_key_map and api_key_map[provider_name]:
        config["api_key"] = api_key_map[provider_name]

    return config


class TradeAgent:
    """Base class for all trade intelligence agents.

    Provides a unified LLM interface. All agents subclass this.
    """

    def __init__(self, system_prompt: str | None = None):
        provider_cfg = get_provider_config(settings.active_llm)
        self.model = provider_cfg["model"]
        self.api_base = provider_cfg["api_base"]
        self.api_key = provider_cfg.get("api_key")
        self.system_prompt = system_prompt or "You are a helpful international trade assistant."

    async def chat(self, message: str, temperature: float = 0.3) -> str:
        """Send a message to the LLM and return the response."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message},
        ]
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await acompletion(**kwargs)
        return response.choices[0].message.content

    async def classify(self, text: str, categories: list[str]) -> str:
        """Classify text into one of the given categories."""
        prompt = f"""Classify the following text into exactly one of these categories: {', '.join(categories)}

Text: {text}

Category:"""
        result = await self.chat(prompt, temperature=0.1)
        # Clean up the response to match a known category
        for cat in categories:
            if cat.lower() in result.strip().lower():
                return cat
        return categories[0]  # Default to first
```

- [ ] **Step 2: Create agents/__init__.py**

```python
from backend.agents.base_agent import TradeAgent, get_provider_config
```

- [ ] **Step 3: Test the agent works**

Create a quick test:

```bash
cd E:\hollowsheet
python -c "
import asyncio
from backend.agents.base_agent import TradeAgent

async def test():
    agent = TradeAgent()
    result = await agent.chat('Say hello in one word')
    print(f'LLM response: {result}')

asyncio.run(test())
"
```

Expected: LLM responds (requires valid API key in .env). If no API key set, it will fail gracefully — that's fine.

- [ ] **Step 4: Commit**

```bash
git add backend/agents/
git commit -m "feat: add LLM provider abstraction with TradeAgent base class"
```

---

### Task 7: Admin panel base (Jinja2 + HTMX)

**Files:**
- Create: `E:\hollowsheet\backend\admin\__init__.py`
- Create: `E:\hollowsheet\backend\admin\router.py`
- Create: `E:\hollowsheet\backend\admin\templates\base.html`
- Create: `E:\hollowsheet\backend\admin\templates\dashboard.html`
- Modify: `E:\hollowsheet\backend\main.py`

- [ ] **Step 1: Create admin/router.py**

```python
"""Admin panel routes — Jinja2 + HTMX based management interface."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
```

- [ ] **Step 2: Create admin/templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TXD Trade Agent — {% block title %}Dashboard{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0a0a0f; color: #e8e8ed; font-family: system-ui, sans-serif; }
        .sidebar { background: #111; border-right: 1px solid #222; }
        .card { background: #1a1a24; border: 1px solid #2a2a35; border-radius: 12px; padding: 1.5rem; }
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
    </style>
</head>
<body class="flex min-h-screen">
    <!-- Sidebar -->
    <nav class="sidebar w-64 p-6 flex flex-col gap-6">
        <div class="text-xl font-bold bg-gradient-to-r from-purple-400 to-purple-200 bg-clip-text text-transparent">
            TXD<span class="text-gray-500 font-normal"> Agent</span>
        </div>
        <div class="flex flex-col gap-2 text-sm">
            <a href="/admin" class="px-3 py-2 rounded-lg hover:bg-white/5 transition">📊 Dashboard</a>
            <a href="/admin/inquiries" class="px-3 py-2 rounded-lg hover:bg-white/5 transition">📩 Inquiries</a>
            <a href="/admin/customers" class="px-3 py-2 rounded-lg hover:bg-white/5 transition">👥 Customers</a>
            <a href="/admin/products" class="px-3 py-2 rounded-lg hover:bg-white/5 transition">📦 Products</a>
            <span class="text-gray-600 text-xs mt-4 px-3">COMING SOON</span>
            <a href="#" class="px-3 py-2 rounded-lg text-gray-500">📧 Emails</a>
            <a href="#" class="px-3 py-2 rounded-lg text-gray-500">🎯 Target Markets</a>
            <a href="#" class="px-3 py-2 rounded-lg text-gray-500">📱 Social Media</a>
        </div>
    </nav>

    <!-- Main content -->
    <main class="flex-1 p-8">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 3: Create admin/templates/dashboard.html**

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="mb-8">
    <h1 class="text-3xl font-bold">Dashboard</h1>
    <p class="text-gray-500 mt-1">TXD Trade Agent System — overview</p>
</div>

<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
    <div class="card">
        <div class="text-gray-400 text-sm">New Inquiries</div>
        <div class="text-3xl font-bold mt-2" id="inquiry-count">—</div>
    </div>
    <div class="card">
        <div class="text-gray-400 text-sm">Total Customers</div>
        <div class="text-3xl font-bold mt-2" id="customer-count">—</div>
    </div>
    <div class="card">
        <div class="text-gray-400 text-sm">Active Products</div>
        <div class="text-3xl font-bold mt-2" id="product-count">—</div>
    </div>
</div>

<div class="card">
    <h2 class="text-lg font-semibold mb-4">System Status</h2>
    <div class="text-sm text-gray-400 space-y-2">
        <div>🔧 LLM Provider: <span id="llm-provider" class="text-white">loading...</span></div>
        <div>💾 Database: <span id="db-status" class="text-white">connecting...</span></div>
        <div>📡 API Version: <span id="api-version" class="text-white">0.1.0</span></div>
    </div>
</div>

<script>
    // Fetch live data from API
    fetch('/api/health')
        .then(r => r.json())
        .then(d => {
            document.getElementById('llm-provider').textContent = d.llm_provider;
            document.getElementById('api-version').textContent = d.version;
        });
    fetch('/api/products')
        .then(r => r.json())
        .then(d => document.getElementById('product-count').textContent = d.total)
        .catch(() => document.getElementById('product-count').textContent = '0');
</script>
{% endblock %}
```

- [ ] **Step 4: Create admin/__init__.py** (empty file)

- [ ] **Step 5: Register admin router in main.py**

```python
from backend.admin.router import router as admin_router

# Add with other includes
app.include_router(admin_router)
```

- [ ] **Step 6: Test admin panel**

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Visit http://127.0.0.1:8000/admin — should show the dark-themed admin dashboard with sidebar navigation.

- [ ] **Step 7: Commit**

```bash
git add backend/admin/
git commit -m "feat: add admin panel base with Jinja2 + HTMX + Tailwind"
```

---

### Phase 1 Completion Verification

Run the full application:

```bash
cd E:\hollowsheet
uvicorn backend.main:app --reload
```

Verify:
- [ ] http://127.0.0.1:8000/api/health → `{"status":"ok","version":"0.1.0","llm_provider":"deepseek"}`
- [ ] http://127.0.0.1:8000/docs → Swagger UI with all API endpoints
- [ ] http://127.0.0.1:8000/admin → Dark theme dashboard
- [ ] `POST /api/products` → creates product in DB
- [ ] `GET /api/products` → lists products
- [ ] `trade_agent.db` file exists

Phase 1 complete. Ready to proceed with Phase 2 (Website Enhancement) or apply `subagent-driven-development` to execute Phase 1.
