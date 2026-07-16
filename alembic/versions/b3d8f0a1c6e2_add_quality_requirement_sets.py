"""add quality requirement sets

Revision ID: b3d8f0a1c6e2
Revises: a7c1e9d2f4b8
Create Date: 2026-07-15 21:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b3d8f0a1c6e2'
down_revision: str | None = 'a7c1e9d2f4b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'quality_requirement_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('application', sa.String(length=80), nullable=False),
        sa.Column('geography', sa.String(length=80), nullable=False),
        sa.Column('reference_document', sa.String(length=200), nullable=False),
        sa.Column('reference_pair', sa.String(length=8), nullable=False),
        sa.Column('wobbe_min_mj_m3', sa.Float(), nullable=False),
        sa.Column('wobbe_max_mj_m3', sa.Float(), nullable=False),
        sa.Column('gross_cv_min_mj_m3', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )


def downgrade() -> None:
    op.drop_table('quality_requirement_sets')
