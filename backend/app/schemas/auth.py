from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    department: Optional[str] = None
    # Editable profile fields so the settings form can re-populate after a save.
    phone: Optional[str] = None
    job_title: Optional[str] = None
    avatar_url: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    # Gates the admin shell renders before letting the user in.
    requires_2fa: bool = False
    has_2fa: bool = False
    must_reset_password: bool = False
