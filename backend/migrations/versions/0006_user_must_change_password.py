"""user must_change_password

Revision ID: 0006_must_change_password
Revises: 0005_timetable_review
Create Date: 2026-10-26 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_must_change_password'
down_revision: Union[str, None] = '0005_timetable_review'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing accounts keep working without a prompt; only new temporary passwords set the flag.
    op.add_column('user', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('user', 'must_change_password')
