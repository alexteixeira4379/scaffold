"""Shrink candidates.status: drop ONBOARDING and PENDING from CandidateStatus.

Follow-up to migration 0026 (workflow orchestration). Once the onboarding
orchestrator owns `profile_onboard_flows.status` (in_progress/completed/
abandoned), `candidates.status` no longer needs to represent "still
onboarding" — that state lives entirely in the orchestrator tables now.
`CandidateStatus` shrinks to a purely commercial lifecycle: ACTIVE,
SUSPENDED, CHURNED, BLOCKED.

Data migration decision (D1, resolved for this Wave 0):
    Existing `candidates.status` rows holding 'onboarding' or 'pending' are
    backfilled to 'churned' *before* the column is narrowed (MySQL silently
    truncates values that fall outside a MODIFY COLUMN ENUM(...) list to the
    empty string, which is not a valid CandidateStatus member — this would
    corrupt those rows if left unhandled).

    'churned' was chosen over the other three remaining members:
      - NOT 'active': the candidate never completed activation (candidate-api
        only promotes to ACTIVE on search_goal / base_profile completion in
        Wave 2/3); mapping to ACTIVE would incorrectly grant commercial
        activation they never earned.
      - NOT 'suspended' / 'blocked': both imply a deliberate administrative
        action (abuse, policy violation, manual pause) that never happened to
        these rows — using them would misrepresent why the candidate isn't
        active.
      - 'churned' is the closest fit: "not part of the active commercial
        funnel". These candidates simply re-enter the funnel through the new
        onboarding orchestrator (profile_onboard_flows) and get promoted to
        ACTIVE by candidate-api once they complete the relevant domain
        workflow — same path as a brand new candidate.

    The column's server default also moves from PENDING to CHURNED for the
    same reason (see scaffold.models.candidate.candidates.Candidate.status).

Downgrade restores the 6-member enum and the PENDING default, but does not
attempt to restore which rows were originally ONBOARDING vs PENDING vs
genuinely CHURNED — the instruction for this migration only requires the
*enum* to be reversible, not the exact historical data (that distinction is
unrecoverable once collapsed into CHURNED).

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import CandidateStatus
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "candidates"
_COLUMN = "status"

# Full historical enum (pre-migration), kept here (not imported from the
# live CandidateStatus enum, which no longer has these members) so downgrade
# can restore it exactly.
_OLD_MEMBERS = ("pending", "active", "suspended", "churned", "blocked", "onboarding")
_old_status_enum = sa.dialects.mysql.ENUM(*_OLD_MEMBERS, name="candidate_status", native_enum=True)
_new_status_enum = mysql_enum(CandidateStatus, "candidate_status")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Backfill rows in the members being dropped *before* narrowing the
    #    column, so MySQL never has to coerce an out-of-range enum value.
    bind.execute(
        sa.text(
            f"UPDATE {_TABLE} SET {_COLUMN} = 'churned' "
            "WHERE status IN ('onboarding', 'pending')"
        )
    )

    # 2. Narrow the enum and flip the server default to CHURNED.
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=_old_status_enum,
        type_=_new_status_enum,
        server_default=mysql_default("candidate_status", CandidateStatus.CHURNED),
        existing_nullable=False,
        nullable=False,
    )


def downgrade() -> None:
    # Restore the 6-member enum and the original PENDING default. Rows that
    # were collapsed into CHURNED during upgrade() stay CHURNED — the
    # original onboarding/pending distinction is not recoverable, and the
    # scope of this migration is the enum shape, not the exact data.
    # `CandidateStatus.PENDING` no longer exists on the live enum, so the
    # original default is written as a literal rather than via mysql_default().
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=_new_status_enum,
        type_=_old_status_enum,
        server_default=sa.text("'pending'"),
        existing_nullable=False,
        nullable=False,
    )
