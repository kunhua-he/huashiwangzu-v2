from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PermissionDefinition(Base, TimestampMixin):
    __tablename__ = "framework_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stable_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PermissionSet(Base, TimestampMixin):
    __tablename__ = "framework_permission_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stable_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    system_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PermissionSetMember(Base, TimestampMixin):
    __tablename__ = "framework_permission_set_members"
    __table_args__ = (UniqueConstraint("permission_set_id", "permission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    permission_set_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_permission_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class UserPermissionGrant(Base, TimestampMixin):
    __tablename__ = "framework_user_permission_grants"
    __table_args__ = (UniqueConstraint("user_id", "permission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class UserPermissionSetGrant(Base, TimestampMixin):
    __tablename__ = "framework_user_permission_set_grants"
    __table_args__ = (UniqueConstraint("user_id", "permission_set_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_set_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_permission_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class CapabilityIdentity(Base, TimestampMixin):
    __tablename__ = "framework_capability_identities"
    __table_args__ = (UniqueConstraint("module_key", "action"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    permission_match_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="all")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CapabilityPermissionRequirement(Base, TimestampMixin):
    __tablename__ = "framework_capability_permission_requirements"
    __table_args__ = (UniqueConstraint("capability_id", "permission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    capability_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_capability_identities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("framework_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
