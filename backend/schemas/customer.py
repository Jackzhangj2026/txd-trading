from datetime import datetime
from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    country: str = ""
    website: str = ""
    source: str = ""
    status: str = "lead"
    notes: str = ""


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    country: str | None = None
    website: str | None = None
    source: str | None = None
    status: str | None = None
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
    website: str = ""
    source: str
    status: str = "lead"
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
