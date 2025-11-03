"""Add sections and update guide structure

Revision ID: 001
Revises:
Create Date: 2024-09-29 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sections table
    op.create_table('sections',
        sa.Column('section_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('guide_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_identifier', sa.String(length=100), nullable=False),
        sa.Column('section_title', sa.String(length=200), nullable=False),
        sa.Column('section_description', sa.String(length=1000), nullable=False),
        sa.Column('section_order', sa.Integer(), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=False),
        sa.CheckConstraint('section_order >= 0', name='positive_section_order'),
        sa.CheckConstraint('estimated_duration_minutes > 0', name='positive_section_duration'),
        sa.ForeignKeyConstraint(['guide_id'], ['step_guides.guide_id'], ),
        sa.PrimaryKey('section_id'),
        sa.UniqueConstraint('guide_id', 'section_identifier', name='unique_section_identifier_per_guide'),
        sa.UniqueConstraint('guide_id', 'section_order', name='unique_section_order_per_guide')
    )

    # Create step_guides table
    op.create_table('step_guides',
        sa.Column('guide_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=False),
        sa.Column('total_steps', sa.Integer(), nullable=False),
        sa.Column('total_sections', sa.Integer(), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('difficulty_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='difficultylevel'), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('llm_prompt_template', sa.Text(), nullable=True),
        sa.Column('generation_metadata', sa.JSON(), nullable=True),
        sa.Column('guide_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('estimated_duration_minutes > 0', name='positive_duration'),
        sa.CheckConstraint('total_sections > 0', name='positive_total_sections'),
        sa.CheckConstraint('total_steps > 0', name='positive_total_steps'),
        sa.PrimaryKey('guide_id'),
        postgresql_using='btree'
    )

    # Create steps table
    op.create_table('steps',
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('guide_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=False),
        sa.Column('completion_criteria', sa.String(length=500), nullable=False),
        sa.Column('assistance_hints', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('requires_desktop_monitoring', sa.Boolean(), nullable=False),
        sa.Column('visual_markers', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('prerequisites', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('dependencies', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.CheckConstraint('estimated_duration_minutes > 0', name='positive_step_duration'),
        sa.CheckConstraint('step_index >= 0', name='positive_step_index'),
        sa.ForeignKeyConstraint(['guide_id'], ['step_guides.guide_id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['sections.section_id'], ),
        sa.PrimaryKey('step_id'),
        sa.UniqueConstraint('guide_id', 'step_index', name='unique_step_index_per_guide')
    )

    # Create guide_sessions table
    op.create_table('guide_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('guide_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('current_step_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'PAUSED', 'COMPLETED', 'FAILED', name='sessionstatus'), nullable=False),
        sa.Column('completion_method', sa.Enum('MANUAL', 'AUTOMATED', 'HYBRID', name='completionmethod'), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('current_step_index >= 0', name='positive_step_index'),
        sa.CheckConstraint("(status = 'COMPLETED' AND completed_at IS NOT NULL) OR (status != 'COMPLETED')", name='completed_status_has_timestamp'),
        sa.ForeignKeyConstraint(['guide_id'], ['step_guides.guide_id'], ),
        sa.PrimaryKey('session_id')
    )
    op.create_index(op.f('ix_guide_sessions_status'), 'guide_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_guide_sessions_user_id'), 'guide_sessions', ['user_id'], unique=False)

    # Create completion_events table
    op.create_table('completion_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completion_method', sa.Enum('MANUAL', 'AUTOMATED', 'SKIPPED', name='completionmethodenum'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('validation_score', sa.Float(), nullable=True),
        sa.Column('validation_data', sa.JSON(), nullable=True),
        sa.Column('user_feedback', sa.String(length=500), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.CheckConstraint('completed_at <= NOW()', name='completed_at_not_future'),
        sa.CheckConstraint('retry_count >= 0', name='positive_retry_count'),
        sa.CheckConstraint('validation_score IS NULL OR (validation_score >= 0.0 AND validation_score <= 1.0)', name='valid_validation_score'),
        sa.ForeignKeyConstraint(['session_id'], ['guide_sessions.session_id'], ),
        sa.ForeignKeyConstraint(['step_id'], ['steps.step_id'], ),
        sa.PrimaryKey('event_id')
    )

    # Create llm_generation_requests table
    op.create_table('llm_generation_requests',
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_query', sa.String(length=1000), nullable=False),
        sa.Column('llm_provider', sa.Enum('OPENAI', 'ANTHROPIC', 'LM_STUDIO', name='llmprovider'), nullable=False),
        sa.Column('prompt_template_version', sa.String(length=50), nullable=False),
        sa.Column('generated_guide_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('generation_time_seconds', sa.Float(), nullable=False),
        sa.Column('token_usage', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('generation_time_seconds > 0', name='positive_generation_time'),
        sa.ForeignKeyConstraint(['generated_guide_id'], ['step_guides.guide_id'], ),
        sa.PrimaryKey('request_id')
    )

    # Create progress_trackers table
    op.create_table('progress_trackers',
        sa.Column('tracker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completed_steps', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('current_step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('remaining_steps', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('completion_percentage', sa.Float(), nullable=False),
        sa.Column('estimated_time_remaining_minutes', sa.Integer(), nullable=False),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('activity_after_start', name='last_activity_at >= started_at'),
        sa.CheckConstraint('completion_percentage >= 0.0 AND completion_percentage <= 100.0', name='valid_completion_percentage'),
        sa.CheckConstraint('estimated_time_remaining_minutes >= 0', name='positive_estimated_time'),
        sa.CheckConstraint('time_spent_minutes >= 0', name='positive_time_spent'),
        sa.ForeignKeyConstraint(['session_id'], ['guide_sessions.session_id'], ),
        sa.PrimaryKey('tracker_id'),
        sa.UniqueConstraint('session_id')
    )

    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('session_token', sa.String(length=500), nullable=False),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.Column('active_guide_sessions', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('expires_at > created_at', name='expires_after_creation'),
        sa.PrimaryKey('user_id'),
        sa.UniqueConstraint('session_token')
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation to handle foreign key constraints
    op.drop_table('user_sessions')
    op.drop_table('progress_trackers')
    op.drop_table('llm_generation_requests')
    op.drop_table('completion_events')
    op.drop_index(op.f('ix_guide_sessions_user_id'), table_name='guide_sessions')
    op.drop_index(op.f('ix_guide_sessions_status'), table_name='guide_sessions')
    op.drop_table('guide_sessions')
    op.drop_table('steps')
    op.drop_table('sections')
    op.drop_table('step_guides')