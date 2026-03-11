from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: Optional[int] = None
    user_id: int
    action: str
    performed_by: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None


ACTION_EXPORT = "PII_EXPORT"
ACTION_DELETE = "PII_DELETE"
