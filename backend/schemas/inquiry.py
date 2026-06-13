from datetime import datetime
from pydantic import BaseModel


class InquiryCreate(BaseModel):
    customer_id: str | None = None
    product_id: str | None = None
    message: str
    source: str = "website"
    # Auto-create customer fields
    customer_name: str = ""
    customer_email: str = ""
    customer_company: str = ""
    customer_country: str = ""


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
