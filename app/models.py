from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class ClientStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class QualityRating(str, enum.Enum):
    green = "GREEN"
    yellow = "YELLOW"
    red = "RED"
    unknown = "UNKNOWN"


class BroadcastStatus(str, enum.Enum):
    draft = "draft"
    sending = "sending"
    done = "done"
    failed = "failed"


class TemplateStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class WabaRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    registering = "registering"  # sedang proses registrasi
    registered = "registered"     # registrasi selesai
    failed = "failed"             # registrasi gagal


# =====================
# USERS
# =====================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="client_admin")
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="users")


# =====================
# CLIENTS
# =====================
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(Enum(ClientStatus), default=ClientStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="client")
    api_managers = relationship("ApiManager", back_populates="client")
    wabas = relationship("Waba", back_populates="client")
    contacts = relationship("Contact", back_populates="client")
    broadcasts = relationship("Broadcast", back_populates="client")
    templates = relationship("MessageTemplate", back_populates="client")
    waba_requests = relationship("WabaRequest", back_populates="client")


# =====================
# API MANAGER
# =====================
class ApiManager(Base):
    __tablename__ = "api_managers"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    name = Column(String, nullable=False)
    app_id = Column(String, nullable=False)
    app_secret_encrypted = Column(Text, nullable=False)
    access_token_encrypted = Column(Text, nullable=False)
    business_manager_id = Column(String, nullable=True)
    max_waba_slots = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="api_managers")
    wabas = relationship("Waba", back_populates="api_manager")


# =====================
# WABA
# =====================
class Waba(Base):
    __tablename__ = "wabas"
    id = Column(Integer, primary_key=True)
    api_manager_id = Column(Integer, ForeignKey("api_managers.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    waba_id = Column(String, unique=True, nullable=True)
    phone_number_id = Column(String, nullable=True)
    display_phone_number = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    quality_rating = Column(Enum(QualityRating), default=QualityRating.unknown)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api_manager = relationship("ApiManager", back_populates="wabas")
    client = relationship("Client", back_populates="wabas")


# =====================
# WABA REQUESTS
# =====================
class WabaRequest(Base):
    __tablename__ = "waba_requests"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    phone_number = Column(String, nullable=False)      # display: 628xxx (tanpa +)
    display_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Enum(WabaRequestStatus), default=WabaRequestStatus.pending)
    api_manager_id = Column(Integer, ForeignKey("api_managers.id"), nullable=True)
    waba_id = Column(Integer, ForeignKey("wabas.id"), nullable=True)  # FK ke tabel wabas (panel)

    # === Registrasi Meta (BARU) ===
    meta_waba_id = Column(String, nullable=True)          # WABA ID dari Meta
    meta_phone_number_id = Column(String, nullable=True)  # Phone Number ID dari Meta
    otp_sent_at = Column(DateTime(timezone=True), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    pin_set = Column(Boolean, default=False)
    registration_error = Column(Text, nullable=True)

    rejection_reason = Column(Text, nullable=True)
    otp_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    client = relationship("Client", back_populates="waba_requests")


# =====================
# CONTACTS
# =====================
class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String, nullable=True)
    phone_number = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="contacts")


# =====================
# MESSAGE TEMPLATES
# =====================
class MessageTemplate(Base):
    __tablename__ = "message_templates"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    waba_id = Column(Integer, ForeignKey("wabas.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    language = Column(String, default="id")
    header_type = Column(String, nullable=True)
    header_text = Column(Text, nullable=True)
    body_text = Column(Text, nullable=False)
    footer_text = Column(Text, nullable=True)
    buttons_json = Column(Text, nullable=True)
    status = Column(Enum(TemplateStatus), default=TemplateStatus.draft)
    meta_template_id = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="templates")


# =====================
# BROADCASTS
# =====================
class Broadcast(Base):
    __tablename__ = "broadcasts"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    waba_id = Column(Integer, ForeignKey("wabas.id"), nullable=False)
    name = Column(String, nullable=False)
    message_type = Column(String, default="text")
    message_body = Column(Text, nullable=False)
    template_name = Column(String, nullable=True)
    status = Column(Enum(BroadcastStatus), default=BroadcastStatus.draft)
    total_recipients = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_read = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="broadcasts")


# =====================
# MESSAGE LOGS
# =====================
class MessageLog(Base):
    __tablename__ = "message_logs"
    id = Column(Integer, primary_key=True)
    waba_id = Column(Integer, ForeignKey("wabas.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    broadcast_id = Column(Integer, ForeignKey("broadcasts.id"), nullable=True)
    recipient = Column(String, nullable=False)
    direction = Column(String)
    message_type = Column(String, default="text")
    content = Column(Text)
    payload = Column(Text)
    status = Column(String)
    error_message = Column(Text, nullable=True)
    meta_message_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())