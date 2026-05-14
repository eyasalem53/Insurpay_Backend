from pydantic import BaseModel
from typing import Optional


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    is_active: bool
    role: Optional[str] = None

    class Config:
        from_attributes = True