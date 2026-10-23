"""Add procurement review records and audit events.

Revision ID: sl20261023a
Revises: c5178de73522
"""

from alembic import op
from onyx.db.procurement import procurement_metadata

revision = "sl20261023a"
down_revision = "c5178de73522"
branch_labels = None
depends_on = None


def upgrade() -> None:
    procurement_metadata.create_all(op.get_bind())


def downgrade() -> None:
    procurement_metadata.drop_all(op.get_bind())
