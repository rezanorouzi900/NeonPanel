"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("pass_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("trojan_pass", sa.String(64), nullable=False),
        sa.Column("ss_pass", sa.String(64), nullable=False),
        sa.Column("quota_gb", sa.Float(), nullable=False),
        sa.Column("used_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sub_token", sa.String(43), nullable=False, unique=True, index=True),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "trafficlog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("day", sa.String(10), nullable=False, index=True),
        sa.Column("up_bytes", sa.Integer(), nullable=False),
        sa.Column("down_bytes", sa.Integer(), nullable=False),
    )
    op.create_table(
        "setting",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(4000), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("setting")
    op.drop_table("trafficlog")
    op.drop_table("user")
    op.drop_table("admin")
