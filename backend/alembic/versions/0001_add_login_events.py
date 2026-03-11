"""add login_events table

Revision ID: 0001
Revises:
Create Date: 2024-01-15 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("device_fingerprint", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), default=0.0),
        sa.Column("flagged", sa.Boolean(), default=False),
        sa.Column("flag_reasons", sa.Text(), nullable=True),
    )
    op.create_index("ix_login_events_user_id", "login_events", ["user_id"])
    op.create_index("ix_login_events_timestamp", "login_events", ["timestamp"])
    op.create_index("ix_login_events_flagged", "login_events", ["flagged"])


def downgrade() -> None:
    op.drop_index("ix_login_events_flagged", table_name="login_events")
    op.drop_index("ix_login_events_timestamp", table_name="login_events")
    op.drop_index("ix_login_events_user_id", table_name="login_events")
    op.drop_table("login_events")
