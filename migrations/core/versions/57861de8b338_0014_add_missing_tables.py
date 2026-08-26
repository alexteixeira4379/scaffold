"""0014 Add missing tables

Revision ID: 57861de8b338
Revises: 0013
Create Date: 2026-08-25 19:56:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '57861de8b338'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('application_entitlements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('candidate_id', sa.BigInteger(), nullable=False),
        sa.Column('can_auto_apply', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('applications_limit', sa.Integer(), server_default='10', nullable=False),
        sa.Column('applications_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], name='fk_application_entitlements_candidate_id'),
        sa.PrimaryKeyConstraint('id', name='pk_application_entitlements'),
    )
    op.create_index('ix_application_entitlements_candidate_id', 'application_entitlements', ['candidate_id'])

    op.create_table('candidate_target_profile_entities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('candidate_target_profile_id', sa.BigInteger(), nullable=False),
        sa.Column('professional_entity_id', sa.BigInteger(), nullable=False),
        sa.Column('relevance', sa.String(32), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=False),
        sa.Column('source', sa.String(64), nullable=False),
        sa.Column('matched_text', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['candidate_target_profile_id'], ['candidate_target_profiles.id'], name='fk_ctpe_profile', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['professional_entity_id'], ['professional_entities.id'], name='fk_ctpe_entity', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_candidate_target_profile_entities'),
        sa.UniqueConstraint('candidate_target_profile_id', 'professional_entity_id', name='uq_candidate_target_profile_entities_profile_entity'),
    )
    op.create_index('ix_ctpe_candidate_target_profile_id', 'candidate_target_profile_entities', ['candidate_target_profile_id'])
    op.create_index('ix_ctpe_professional_entity_id', 'candidate_target_profile_entities', ['professional_entity_id'])


def downgrade() -> None:
    op.drop_index('ix_ctpe_professional_entity_id', table_name='candidate_target_profile_entities')
    op.drop_index('ix_ctpe_candidate_target_profile_id', table_name='candidate_target_profile_entities')
    op.drop_table('candidate_target_profile_entities')
    op.drop_index('ix_application_entitlements_candidate_id', table_name='application_entitlements')
    op.drop_table('application_entitlements')
