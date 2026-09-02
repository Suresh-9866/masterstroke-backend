import uuid
from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from . import Base

class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_sub = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(Enum("admin", "business", "customer", name="user_roles"), nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    status = Column(Enum("active", "suspended", "deleted", name="user_status"), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    deleted_reason = Column(String, nullable=True)
