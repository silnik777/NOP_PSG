"""add composition profiles and blend recipes

Revision ID: a7c1e9d2f4b8
Revises: f410e13a592e
Create Date: 2026-07-15 21:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a7c1e9d2f4b8'
down_revision: str | None = 'f410e13a592e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'composition_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('owner', sa.String(length=128), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.Column('fractions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'version', name='uq_profile_code_version'),
    )
    op.create_index(
        op.f('ix_composition_profiles_code'), 'composition_profiles', ['code'], unique=False
    )
    op.create_table(
        'blend_recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('owner', sa.String(length=128), nullable=False),
        sa.Column('streams', sa.JSON(), nullable=False),
        sa.Column('reference_pair', sa.String(length=8), nullable=False),
        sa.Column('config_checksum', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'version', name='uq_recipe_code_version'),
    )
    op.create_index(op.f('ix_blend_recipes_code'), 'blend_recipes', ['code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_blend_recipes_code'), table_name='blend_recipes')
    op.drop_table('blend_recipes')
    op.drop_index(op.f('ix_composition_profiles_code'), table_name='composition_profiles')
    op.drop_table('composition_profiles')
