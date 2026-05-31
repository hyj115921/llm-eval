from pydantic import BaseModel
from typing import Optional, List, Any


class PaginatedParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditResponse(BaseModel):
    action: str
    detail: str
    status: str
    message: str
