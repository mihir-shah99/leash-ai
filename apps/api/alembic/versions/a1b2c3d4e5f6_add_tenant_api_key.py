"""Add API key columns to tenants

Revision ID: a1b2c3d4e5f6
Revises: 5d8def269910
Create Date: 2026-06-01 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5d8def269910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tenants', sa.Column('api_key_hash', sa.String(), nullable=True))
    op.add_column('tenants', sa.Column('api_key_prefix', sa.String(), nullable=True))
    op.create_index(op.f('ix_tenants_api_key_hash'), 'tenants', ['api_key_hash'], unique=True)
    op.create_index(op.f('ix_tenants_api_key_prefix'), 'tenants', ['api_key_prefix'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tenants_api_key_prefix'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_api_key_hash'), table_name='tenants')
    op.drop_column('tenants', 'api_key_prefix')
    op.drop_column('tenants', 'api_key_hash')
