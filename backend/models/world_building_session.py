from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorldBuildingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    引导式世界观生成会话

    用户行为设计：
    - 用户随时可以退出，会话状态自动保存
    - 用户再次进入时，从 last_active_step 继续
    - 已完成的步骤数据保存在 session_data 中
    """
    __tablename__ = "world_building_sessions"
    __table_args__ = (
        Index(
            "ix_world_building_sessions_project_user",
            "project_id",
            "user_id",
        ),
        Index(
            "ix_world_building_sessions_status",
            "status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_step: Mapped[int] = mapped_column(default=1)
    last_active_step: Mapped[int] = mapped_column(default=1)
    session_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(default="in_progress", nullable=False, index=True)
    completed_steps: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="world_building_sessions")
    user: Mapped["User"] = relationship(back_populates="world_building_sessions")
