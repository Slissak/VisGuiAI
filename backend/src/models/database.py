"""SQLAlchemy database models for Step Guide Backend.

These models correspond to the Pydantic schemas but are optimized for database operations.
"""

import enum
import uuid

from shared.schemas.guide_session import CompletionMethod, SessionStatus
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Import UserUsage and User models to ensure they're registered with Base.metadata


# Step status enum for adaptation support
class StepStatus(str, enum.Enum):
    """Status of a step in the guide."""

    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ALTERNATIVE = "alternative"


Base = declarative_base()


class GuideSessionModel(Base):
    """GuideSession database model."""

    __tablename__ = "guide_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    guide_id = Column(
        UUID(as_uuid=True), ForeignKey("step_guides.guide_id"), nullable=False
    )
    current_step_identifier = Column(
        String(10), nullable=False, default="0"
    )  # Support sub-indices like "1a", "1b"
    status = Column(
        String, nullable=False, default=SessionStatus.ACTIVE.value, index=True
    )
    completion_method = Column(
        String, nullable=False, default=CompletionMethod.HYBRID.value
    )
    session_metadata = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    guide = relationship("StepGuideModel", back_populates="sessions")
    completion_events = relationship(
        "CompletionEventModel", back_populates="session", cascade="all, delete-orphan"
    )
    progress_tracker = relationship(
        "ProgressTrackerModel",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Constraints
    # __table_args__ = (
    #     CheckConstraint(
    #         "(status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed')",
    #         name="completed_status_has_timestamp"
    #     ),
    # )


class StepGuideModel(Base):
    """StepGuide database model with section support."""

    __tablename__ = "step_guides"

    guide_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=False)
    total_steps = Column(Integer, nullable=False)
    total_sections = Column(Integer, nullable=False, default=1)
    estimated_duration_minutes = Column(Integer, nullable=False)
    difficulty_level = Column(String, nullable=False)
    category = Column(String(100), nullable=False)
    llm_prompt_template = Column(Text, nullable=True)
    generation_metadata = Column(JSON, nullable=True)
    guide_data = Column(
        JSON, nullable=False
    )  # Stores full structured guide with sections
    adaptation_history = Column(
        JSON, nullable=True, default=list
    )  # Track all adaptations made
    last_adapted_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Last adaptation timestamp
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    sections = relationship(
        "SectionModel",
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="SectionModel.section_order",
    )
    steps = relationship(
        "StepModel",
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="StepModel.step_index",
    )
    sessions = relationship("GuideSessionModel", back_populates="guide")
    llm_requests = relationship(
        "LLMGenerationRequestModel", back_populates="generated_guide"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("total_steps > 0", name="positive_total_steps"),
        CheckConstraint("total_sections > 0", name="positive_total_sections"),
        CheckConstraint("estimated_duration_minutes > 0", name="positive_duration"),
    )


class SectionModel(Base):
    """Section database model for organizing steps into logical groups."""

    __tablename__ = "sections"

    section_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id = Column(
        UUID(as_uuid=True), ForeignKey("step_guides.guide_id"), nullable=False
    )
    section_identifier = Column(
        String(100), nullable=False
    )  # e.g., "setup", "configuration"
    section_title = Column(String(200), nullable=False)
    section_description = Column(String(1000), nullable=False)
    section_order = Column(Integer, nullable=False)
    estimated_duration_minutes = Column(Integer, nullable=False)

    # Relationships
    guide = relationship("StepGuideModel", back_populates="sections")
    steps = relationship(
        "StepModel",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="StepModel.step_index",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "guide_id", "section_order", name="unique_section_order_per_guide"
        ),
        UniqueConstraint(
            "guide_id", "section_identifier", name="unique_section_identifier_per_guide"
        ),
        CheckConstraint("section_order >= 0", name="positive_section_order"),
        CheckConstraint(
            "estimated_duration_minutes > 0", name="positive_section_duration"
        ),
    )


class StepModel(Base):
    """Step database model."""

    __tablename__ = "steps"

    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id = Column(
        UUID(as_uuid=True), ForeignKey("step_guides.guide_id"), nullable=False
    )
    section_id = Column(
        UUID(as_uuid=True), ForeignKey("sections.section_id"), nullable=True
    )
    step_index = Column(Integer, nullable=False)
    step_identifier = Column(
        String(10), nullable=False, default="0"
    )  # Support sub-indices like "1a", "1b"
    step_status = Column(
        String, nullable=False, default=StepStatus.ACTIVE.value
    )  # For adaptation
    replaces_step_index = Column(Integer, nullable=True)  # For alternative steps
    blocked_reason = Column(String(500), nullable=True)  # Why step was blocked
    title = Column(String(100), nullable=False)
    description = Column(String(2000), nullable=False)
    completion_criteria = Column(String(500), nullable=False)
    assistance_hints = Column(ARRAY(String), nullable=False, default=[])
    estimated_duration_minutes = Column(Integer, nullable=False)
    requires_desktop_monitoring = Column(Boolean, nullable=False, default=False)
    visual_markers = Column(ARRAY(String), nullable=False, default=[])
    prerequisites = Column(
        ARRAY(String), nullable=False, default=[]
    )  # String descriptions of prerequisites
    dependencies = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])

    # Relationships
    guide = relationship("StepGuideModel", back_populates="steps")
    section = relationship("SectionModel", back_populates="steps")
    completion_events = relationship("CompletionEventModel", back_populates="step")

    # Constraints
    __table_args__ = (
        UniqueConstraint("guide_id", "step_index", name="unique_step_index_per_guide"),
        CheckConstraint("step_index >= 0", name="positive_step_index"),
        CheckConstraint(
            "estimated_duration_minutes > 0", name="positive_step_duration"
        ),
    )


class CompletionEventModel(Base):
    """CompletionEvent database model."""

    __tablename__ = "completion_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("guide_sessions.session_id"), nullable=False
    )
    step_id = Column(UUID(as_uuid=True), ForeignKey("steps.step_id"), nullable=False)
    completion_method = Column(String, nullable=False)
    completed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    validation_score = Column(Float, nullable=True)
    validation_data = Column(JSON, nullable=True)
    user_feedback = Column(String(500), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Relationships
    session = relationship("GuideSessionModel", back_populates="completion_events")
    step = relationship("StepModel", back_populates="completion_events")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "validation_score IS NULL OR (validation_score >= 0.0 AND validation_score <= 1.0)",
            name="valid_validation_score",
        ),
        CheckConstraint("retry_count >= 0", name="positive_retry_count"),
        CheckConstraint("completed_at <= NOW()", name="completed_at_not_future"),
    )


class ProgressTrackerModel(Base):
    """ProgressTracker database model."""

    __tablename__ = "progress_trackers"

    tracker_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("guide_sessions.session_id"),
        nullable=False,
        unique=True,
    )
    completed_steps = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])
    current_step_id = Column(UUID(as_uuid=True), nullable=True)
    remaining_steps = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])
    completion_percentage = Column(Float, nullable=False, default=0.0)
    estimated_time_remaining_minutes = Column(Integer, nullable=False, default=0)
    time_spent_minutes = Column(Integer, nullable=False, default=0)
    started_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_activity_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    session = relationship("GuideSessionModel", back_populates="progress_tracker")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "completion_percentage >= 0.0 AND completion_percentage <= 100.0",
            name="valid_completion_percentage",
        ),
        CheckConstraint(
            "estimated_time_remaining_minutes >= 0", name="positive_estimated_time"
        ),
        CheckConstraint("time_spent_minutes >= 0", name="positive_time_spent"),
        CheckConstraint("last_activity_at >= started_at", name="activity_after_start"),
    )


class LLMGenerationRequestModel(Base):
    """LLMGenerationRequest database model."""

    __tablename__ = "llm_generation_requests"

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_query = Column(String(1000), nullable=False)
    llm_provider = Column(String, nullable=False)
    prompt_template_version = Column(String(50), nullable=False)
    generated_guide_id = Column(
        UUID(as_uuid=True), ForeignKey("step_guides.guide_id"), nullable=True
    )
    generation_time_seconds = Column(Float, nullable=False)
    token_usage = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    generated_guide = relationship("StepGuideModel", back_populates="llm_requests")

    # Constraints
    __table_args__ = (
        CheckConstraint("generation_time_seconds > 0", name="positive_generation_time"),
    )


class UserSessionModel(Base):
    """UserSession database model."""

    __tablename__ = "user_sessions"

    user_id = Column(String(255), primary_key=True)
    session_token = Column(String(500), nullable=False, unique=True)
    preferences = Column(JSON, nullable=True)
    active_guide_sessions = Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=[]
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
    )
