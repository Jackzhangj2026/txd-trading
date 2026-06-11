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
