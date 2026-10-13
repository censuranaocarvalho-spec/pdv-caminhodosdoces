from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4

class Customer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    phone: str
    name: str
    address: str
    loyalty_points: int = 0
    segment: str = "NEW"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
