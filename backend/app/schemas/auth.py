import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignUpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company: str | None = Field(default=None, max_length=255)


class UpdateWorkspaceRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    tenant_id: uuid.UUID
    company_name: str
    tenant_slug: str
    onboarded: bool
    oauth_provider: str | None
    workspace_setup_complete: bool = True
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    is_new_user: bool
    access_token: str


class SessionResponse(BaseModel):
    user: UserResponse
    access_token: str


class TenantMembership(BaseModel):
    id: uuid.UUID
    company_name: str
    slug: str
    is_active: bool = False
