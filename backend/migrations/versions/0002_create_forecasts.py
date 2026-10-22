"""create forecasts

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "forecasts",
        sa.Column("station_id", sa.String(40), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("hour", sa.Integer(), primary_key=True),
        sa.Column("probability", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("forecasts")
