"""add source column to prompts

Revision ID: 002_prompt_source
Revises: 001_initial
Create Date: 2026-06-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_prompt_source'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prompts',
        sa.Column('source', sa.String(32), nullable=False, server_default='prompt_page'))


def downgrade() -> None:
    op.drop_column('prompts', 'source')
