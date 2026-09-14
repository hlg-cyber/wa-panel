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

# =====================
# USERS (Super Admin & Admin Klien)
# =====================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="client_admin")  # super_admin / client_admin
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="users")

# =====================
# CLIENTS (Klien/Tenant)
# =====================
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(Enum(ClientStatus), default=ClientStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="client")
    api_managers = relationship("ApiManager", back_populates="client")

# =====================
# API MANAGER (BM / App Meta)
# =====================
class ApiManager(Base):
    __tablename__ = "api_managers"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    name = Column(String, nullable=False)
    app_id = Column(String, nullable=False)
    app_secret_encrypted = Column(Text, nullable=False)   # Terenkripsi
    access_token_encrypted = Column(Text, nullable=False) # Terenkripsi
    business_manager_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="api_managers")
    wabas = relationship("Waba", back_populates="api_manager")

# =====================
# WABA (WhatsApp Business Account)
# =====================
class Waba(Base):
    __tablename__ = "wabas"
    id = Column(Integer, primary_key=True)
    api_manager_id = Column(Integer, ForeignKey("api_managers.id"), nullable=False)
    waba_id = Column(String, unique=True, nullable=False)
    phone_number_id = Column(String, nullable=False)
    display_phone_number = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    quality_rating = Column(Enum(QualityRating), default=QualityRating.unknown)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api_manager = relationship("ApiManager", back_populates="wabas")

# =====================
# MESSAGE LOGS
# =====================
class MessageLog(Base):
    __tablename__ = "message_logs"
    id = Column(Integer, primary_key=True)
    waba_id = Column(Integer, ForeignKey("wabas.id"), nullable=False)
    recipient = Column(String, nullable=False)
    direction = Column(String)  # inbound / outbound
    payload = Column(Text)      # JSON mentah
    status = Column(String)     # sent / delivered / read / failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())