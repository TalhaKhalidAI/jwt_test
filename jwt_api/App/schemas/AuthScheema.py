from enum import Enum
from pydantic import BaseModel, EmailStr, ConfigDict, SecretStr
from typing import Optional, Dict, Any

class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    USER = "user" 


class TokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class PasswordConfirmRequest(BaseModel):
    password: Optional[SecretStr] = None
    otp: Optional[str] = None  

class PasswordUpdateRequest(BaseModel):
    new_password: SecretStr
    old_password: SecretStr | None = None
    otp:Optional[str]=None
class UpdateUser(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    profile_pic: Optional[str] = None
    disabled: Optional[bool] = None
    user_role: Optional[UserRole] = None

class UserResponse(BaseModel):
    """For API responses"""
    model_config = ConfigDict(from_attributes=True)  # Add this
    
    id: int
    name: str
    email: EmailStr
    user_role: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    profile_pic: Optional[str] = None