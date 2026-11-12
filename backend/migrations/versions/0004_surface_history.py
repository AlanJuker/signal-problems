"""make room for 2014–2024 streetcar and bus delays

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"

TOTALS_COLUMNS = ["mode", "route", "route_name", "minutes", "occurred_at"]


def upgrade() -> None:
    # Incident words like "LATE LEAVING GARAGE - MANAGEMENT" run to 32 characters (#28)
    with op.batch_alter_table("surface_delays") as table:  # batch: SQLite can't alter a column
        table.alter_column("cause_code", type_=sa.String(40), existing_type=sa.String(8))
    # Covers the route ranking: 800,000 bus rows take 30 ms to rank instead of a second
    op.create_index("ix_surface_delays_totals", "surface_delays", TOTALS_COLUMNS)


def downgrade() -> None:
    op.drop_index("ix_surface_delays_totals", "surface_delays")
    with op.batch_alter_table("surface_delays") as table:
        table.alter_column("cause_code", type_=sa.String(8), existing_type=sa.String(40))
