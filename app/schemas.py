from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class ClientStatusEnum(str, Enum):
    active = "active"
    suspended = "suspended"


class QualityRatingEnum(str, Enum):
    green = "GREEN"
    yellow = "YELLOW"
    red = "RED"
    unknown = "UNKNOWN"


class BroadcastStatusEnum(str, Enum):
    draft = "draft"
    sending = "sending"
    done = "done"
    failed = "failed"


class TemplateStatusEnum(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ChatSessionStatusEnum(str, Enum):
    waiting_admin = "waiting_admin"
    in_progress = "in_progress"
    waiting_otp = "waiting_otp"
    completed = "completed"
    rejected = "rejected"
    closed = "closed"


class ChatTopicEnum(str, Enum):
    add_waba = "add_waba"


# AUTH
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    client_id: Optional[int] = None


class ClientSelfRegister(BaseModel):
    name: str
    admin_email: str
    admin_password: str


# USER
class UserOut(BaseModel):
    id: int
    email: str
    role: str
    client_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# API MANAGER
class ApiManagerCreate(BaseModel):
    name: str
    app_id: str
    app_secret: str
    access_token: str
    business_manager_id: Optional[str] = None
    max_waba_slots: int = 5
    client_id: Optional[int] = None


class ApiManagerUpdate(BaseModel):
    name: Optional[str] = None
    app_secret: Optional[str] = None
    access_token: Optional[str] = None
    business_manager_id: Optional[str] = None
    max_waba_slots: Optional[int] = None
    is_active: Optional[bool] = None


class ApiManagerOut(BaseModel):
    id: int
    name: str
    app_id: str
    business_manager_id: Optional[str]
    max_waba_slots: int
    client_id: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# WABA
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
    api_manager_id: Optional[int]
    client_id: Optional[int]
    waba_id: Optional[str]
    phone_number_id: Optional[str]
    display_phone_number: Optional[str]
    display_name: Optional[str]
    quality_rating: QualityRatingEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# CHAT
class ChatSessionCreate(BaseModel):
    topic: ChatTopicEnum = ChatTopicEnum.add_waba
    phone_number: str
    display_name: Optional[str] = None


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    sender_role: str
    sender_id: Optional[int]
    message_type: str
    action_type: Optional[str]
    content: str
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatSessionOut(BaseModel):
    id: int
    client_id: int
    topic: ChatTopicEnum
    phone_number: str
    display_name: Optional[str]
    status: ChatSessionStatusEnum
    otp_code: Optional[str]
    otp_requested_at: Optional[datetime]
    meta_waba_id: Optional[str]
    meta_phone_number_id: Optional[str]
    waba_id: Optional[int]
    api_manager_id: Optional[int]
    rejection_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatSessionDetail(ChatSessionOut):
    messages: List[ChatMessageOut] = []
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    checklist_state: Optional[Dict[str, Any]] = None


class ChecklistUpdate(BaseModel):
    step_key: str
    completed: bool


class CompleteWabaRequest(BaseModel):
    meta_waba_id: str
    meta_phone_number_id: str
    api_manager_id: int
    otp_code: Optional[str] = None


# CLIENT
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


# DASHBOARD
class DashboardStats(BaseModel):
    total_api_managers: int
    total_clients: int
    active_clients: int
    suspended_clients: int
    total_wabas: int
    wabas_green: int
    wabas_yellow: int
    wabas_red: int
    pending_chats: int


class ClientDashboardStats(BaseModel):
    total_wabas: int
    active_wabas: int
    wabas_green: int
    wabas_yellow: int
    wabas_red: int
    total_contacts: int
    total_broadcasts: int
    total_messages_sent: int
    total_messages_delivered: int
    total_messages_read: int
    total_messages_failed: int
    active_chats: int


# CONTACT
class ContactCreate(BaseModel):
    name: Optional[str] = None
    phone_number: str


class ContactBulkImport(BaseModel):
    contacts: List[ContactCreate]


class ContactOut(BaseModel):
    id: int
    name: Optional[str]
    phone_number: str
    created_at: datetime

    class Config:
        from_attributes = True


# MESSAGE
class SendMessageRequest(BaseModel):
    waba_id: int
    to: str
    message_type: str = "text"
    text: Optional[str] = None
    template_name: Optional[str] = None
    template_language: Optional[str] = "id"
    template_params: Optional[List[str]] = None
    media_url: Optional[str] = None
    media_caption: Optional[str] = None


class SendMessageResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class MessageLogOut(BaseModel):
    id: int
    waba_id: int
    client_id: Optional[int]
    broadcast_id: Optional[int]
    recipient: str
    direction: str
    message_type: str
    content: Optional[str]
    status: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# TEMPLATE
class TemplateCreate(BaseModel):
    waba_id: int
    name: str
    category: str = "MARKETING"
    language: str = "id"
    header_type: Optional[str] = None
    header_text: Optional[str] = None
    body_text: str
    footer_text: Optional[str] = None
    buttons: Optional[List[dict]] = None


class TemplateUpdate(BaseModel):
    category: Optional[str] = None
    language: Optional[str] = None
    header_type: Optional[str] = None
    header_text: Optional[str] = None
    body_text: Optional[str] = None
    footer_text: Optional[str] = None
    buttons: Optional[List[dict]] = None


class TemplateOut(BaseModel):
    id: int
    client_id: int
    waba_id: int
    name: str
    category: str
    language: str
    header_type: Optional[str]
    header_text: Optional[str]
    body_text: str
    footer_text: Optional[str]
    buttons_json: Optional[str]
    status: TemplateStatusEnum
    meta_template_id: Optional[str]
    rejection_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# BROADCAST
class BroadcastCreate(BaseModel):
    waba_id: int
    name: str
    message_type: str = "text"
    message_body: str
    template_name: Optional[str] = None
    recipients: Optional[List[str]] = None
    use_contacts: bool = False


class BroadcastOut(BaseModel):
    id: int
    client_id: int
    waba_id: int
    name: str
    message_type: str
    message_body: str
    template_name: Optional[str]
    status: BroadcastStatusEnum
    total_recipients: int
    total_sent: int
    total_delivered: int
    total_read: int
    total_failed: int
    created_at: datetime

    class Config:
        from_attributes = True