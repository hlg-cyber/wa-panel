from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# =====================
# ENUMS
# =====================
class ClientStatusEnum(str, Enum):
    active = "active"
    suspended = "suspended"


class QualityRatingEnum(str, Enum):
    green = "GREEN"
    yellow = "YELLOW"
    red = "RED"
    unknown = "UNKNOWN"


# =====================
# AUTH
# =====================
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    client_id: Optional[int] = None


# =====================
# USER
# =====================
class UserOut(BaseModel):
    id: int
    email: str
    role: str
    client_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =====================
# API MANAGER
# =====================
class ApiManagerCreate(BaseModel):
    name: str
    app_id: str
    app_secret: str
    access_token: str
    business_manager_id: Optional[str] = None
    client_id: Optional[int] = None


class ApiManagerUpdate(BaseModel):
    name: Optional[str] = None
    app_secret: Optional[str] = None
    access_token: Optional[str] = None
    business_manager_id: Optional[str] = None
    is_active: Optional[bool] = None


class ApiManagerOut(BaseModel):
    id: int
    name: str
    app_id: str
    business_manager_id: Optional[str]
    client_id: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =====================
# WABA
# =====================
class WabaCreate(BaseModel):
    api_manager_id: int
    client_id: Optional[int] = None
    waba_id: str
    phone_number_id: str
    display_phone_number: Optional[str] = None
    display_name: Optional[str] = None


class WabaUpdate(BaseModel):
    client_id: Optional[int] = None
    display_name: Optional[str] = None
    quality_rating: Optional[QualityRatingEnum] = None
    is_active: Optional[bool] = None


class WabaOut(BaseModel):
    id: int
    api_manager_id: int
    client_id: Optional[int]
    waba_id: str
    phone_number_id: str
    display_phone_number: Optional[str]
    display_name: Optional[str]
    quality_rating: QualityRatingEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =====================
# CLIENT
# =====================
class ClientCreate(BaseModel):
    name: str
    admin_email: str
    admin_password: str


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[ClientStatusEnum] = None


class ClientOut(BaseModel):
    id: int
    name: str
    status: ClientStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True


# =====================
# DASHBOARD
# =====================
class DashboardStats(BaseModel):
    total_api_managers: int
    total_clients: int
    active_clients: int
    suspended_clients: int
    total_wabas: int
    wabas_green: int
    wabas_yellow: int
    wabas_red: int


class ClientDashboardStats(BaseModel):
    total_wabas: int
    active_wabas: int
    wabas_green: int
    wabas_yellow: int
    wabas_red: int