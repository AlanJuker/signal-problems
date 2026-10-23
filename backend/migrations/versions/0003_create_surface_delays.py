"""create surface delays

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.create_table(
        "surface_delays",
        sa.Column("fingerprint", sa.String(32), primary_key=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("route", sa.Integer(), nullable=False),
        sa.Column("route_name", sa.String(80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("location", sa.String(120), nullable=False),
        sa.Column("cause_code", sa.String(8), nullable=False),
        sa.Column("cause_category", sa.String(24), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("gap_minutes", sa.Integer(), nullable=False),
    )
    op.create_index("ix_surface_delays_route", "surface_delays", ["mode", "route", "occurred_at"])


def downgrade() -> None:
    op.drop_table("surface_delays")
