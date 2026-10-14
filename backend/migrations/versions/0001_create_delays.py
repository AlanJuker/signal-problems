"""create delays

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "delays",
        sa.Column("fingerprint", sa.String(32), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("location_kind", sa.String(16), nullable=False),
        sa.Column("station_id", sa.String(40)),
        sa.Column("segment_end_id", sa.String(40)),
        sa.Column("line", sa.String(1)),
        sa.Column("cause_code", sa.String(8), nullable=False),
        sa.Column("cause_category", sa.String(24), nullable=False),
        sa.Column("is_signal_problem", sa.Boolean(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("gap_minutes", sa.Integer(), nullable=False),
    )
    op.create_index("ix_delays_station_occurred_at", "delays", ["station_id", "occurred_at"])
    op.create_index("ix_delays_line_occurred_at", "delays", ["line", "occurred_at"])


def downgrade() -> None:
    op.drop_table("delays")
