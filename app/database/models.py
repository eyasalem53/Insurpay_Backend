from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.session import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    users = relationship("User", back_populates="role")
    permissions = relationship("DashboardPermission", back_populates="role")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)

    # New profile fields
    date_naissance = Column(DateTime(timezone=False), nullable=True)
    phone_number = Column(String(30), nullable=True)
    num_adherent = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    account_status = Column(String(30), default="PENDING", nullable=False)

    role = relationship("Role", back_populates="users")


class Dashboard(Base):
    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    powerbi_embed_url = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    permissions = relationship("DashboardPermission", back_populates="dashboard")


class DashboardPermission(Base):
    __tablename__ = "dashboard_permissions"

    id = Column(Integer, primary_key=True, index=True)
    dashboard_id = Column(Integer, ForeignKey("dashboards.id", ondelete="CASCADE"))
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"))

    dashboard = relationship("Dashboard", back_populates="permissions")
    role = relationship("Role", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("dashboard_id", "role_id", name="uq_dashboard_role"),
    )