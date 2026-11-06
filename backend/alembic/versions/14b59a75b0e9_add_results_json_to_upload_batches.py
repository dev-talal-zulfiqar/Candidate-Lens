"""add results_json to upload_batches

Revision ID: 14b59a75b0e9
Revises: a03d223d8648
Create Date: 2026-11-05 18:26:14.009674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '14b59a75b0e9'
down_revision: Union[str, Sequence[str], None] = 'a03d223d8648'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default so this is safe against existing rows — autogenerate
    # doesn't add one on its own, and a bare NOT NULL ADD COLUMN would fail
    # against any upload_batches row that already exists.
    op.add_column(
        'upload_batches',
        sa.Column(
            'results_json',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('upload_batches', 'results_json')
