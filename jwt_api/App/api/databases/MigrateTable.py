# App/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func,JSON,ForeignKey,Text,BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy.orm import relationship
from App.core.Connector import Base  # Import from new connector
import uuid
class User(Base):  # Changed from Users to User (singular, PEP8)
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)  # Renamed for clarity
    profile_pic = Column(String(500), nullable=True)
    user_role = Column(String(50), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)  # Better name than 'disable'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    disabled=Column(Boolean,default=False)
    permissions = Column(JSON, default=dict)  # FIX: mutable default avoided
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    mfa_enabled=Column(Boolean,default=False,nullable=False)
    mfa_secret_encrypted = Column(String(500), nullable=True)
    mfa_method = Column(String(20), nullable=True)


# ==========================================
# VERIFLOW TABLES
# ==========================================

class CryptoKey(Base):
    __tablename__ = "crypto_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    kid = Column(String(100), unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    private_key_encrypted = Column(Text, nullable=False)
    
    status = Column(String(20), nullable=False, default="active")
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(255), nullable=True)
    
    created_by = Column(ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    key_id = Column(ForeignKey("crypto_keys.id"), nullable=False)
    device_id = Column(String(255), nullable=True)
    
    status = Column(String(20), nullable=False, default="active")
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(255), nullable=True)

    user = relationship("User")
    crypto_key = relationship("CryptoKey")


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=False)
    
    # Changed from Text to JSONB
    jwt_scanned = Column(JSONB, nullable=False) 
    
    status = Column(String(10), nullable=False)
    reason = Column(String(255), nullable=True)
    
    scanned_at = Column(DateTime(timezone=True), nullable=False) 
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    shift = relationship("Shift")



class InventoryRule(Base):
    __tablename__ = "inventory_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    key_id = Column(ForeignKey("crypto_keys.id"), nullable=True)
    
    rule_name = Column(String(100), nullable=False)
    matching_claim_key = Column(String(100), nullable=False)
    expected_value = Column(String(255), nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    crypto_key = relationship("CryptoKey")