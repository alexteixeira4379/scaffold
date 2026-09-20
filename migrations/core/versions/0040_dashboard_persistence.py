"""Add verified identities and persistent dashboard data (approved local DDL).

Revision ID: 0040
Revises: 0039

Frozen SQL: do not import current application models. MySQL DDL commits
implicitly; run preflight before the first statement and stop on any error.
Production application and publishing scaffold require separate approval.
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "auth_verified_identities",
    "candidate_notification_preferences",
    "job_candidate_preferences",
    "resume_personas",
)
NEW_COLUMNS = {
    "candidate_preferences": ("reviewed_at",),
    "candidate_target_profiles": ("notes", "archived_at"),
    "resume_profiles": ("headline", "portfolio_url", "reviewed_sections", "revision"),
    "resume_versions": ("target_profile_id", "archived_at", "current_scope"),
}
NEW_INDEXES = {
    "candidate_target_profiles": ("uq_target_candidate_id", "ix_target_candidate_archived"),
    "resume_versions": ("ix_resume_owned_target", "ix_resume_session", "uq_resume_current_scope"),
}


def preflight(bind) -> None:
    """Only reads. Reject data conflicts/drift before any implicit DDL commit."""
    if bind.dialect.name != "mysql":
        raise RuntimeError("0040 requires MySQL 8.0.16 or later")
    version = bind.execute(sa.text("SELECT VERSION()")).scalar_one()
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if "mariadb" in version.lower() or not match or tuple(map(int, match.groups())) < (8, 0, 16):
        raise RuntimeError("0040 requires MySQL >= 8.0.16 with enforced CHECK constraints")
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    partial = sorted(tables.intersection(NEW_TABLES))
    if partial:
        raise RuntimeError(
            f"0040 found existing/partial objects: {partial}; reconcile before retry"
        )
    required = set(NEW_COLUMNS) | {"candidates", "jobs", "resume_build_sessions"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(f"0040 missing baseline tables: {missing}")
    for table, additions in NEW_COLUMNS.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        collision = existing.intersection(additions)
        if collision:
            raise RuntimeError(
                f"0040 found existing/partial columns in {table}: {sorted(collision)}"
            )
    for table, additions in NEW_INDEXES.items():
        existing = {index["name"] for index in inspector.get_indexes(table)}
        if existing.intersection(additions):
            raise RuntimeError(f"0040 found existing/partial indexes in {table}")
    for parent in ("candidates", "jobs", "candidate_target_profiles"):
        column = next(c for c in inspector.get_columns(parent) if c["name"] == "id")
        if not isinstance(column["type"], sa.BigInteger) or getattr(
            column["type"], "unsigned", False
        ):
            raise RuntimeError(f"0040 expected signed BIGINT {parent}.id")
    checks = {
        "multiple current resumes": "SELECT candidate_id FROM resume_versions WHERE is_current = 1 GROUP BY candidate_id HAVING COUNT(*) > 1",
        "multiple primary targets": "SELECT candidate_id FROM candidate_target_profiles WHERE is_default = 1 GROUP BY candidate_id HAVING COUNT(*) > 1",
    }
    for table in (
        "candidate_preferences",
        "candidate_target_profiles",
        "resume_profiles",
        "resume_versions",
    ):
        checks[f"orphan candidate in {table}"] = (
            f"SELECT child.id FROM {table} child LEFT JOIN candidates parent "
            "ON parent.id = child.candidate_id WHERE parent.id IS NULL"
        )
    checks["orphan resume session"] = (
        "SELECT child.id FROM resume_versions child LEFT JOIN resume_build_sessions parent "
        "ON parent.id = child.session_id WHERE child.session_id IS NOT NULL AND parent.id IS NULL"
    )
    for label, query in checks.items():
        conflicts = list(bind.execute(sa.text(query + " LIMIT 20")).scalars())
        if conflicts:
            raise RuntimeError(
                f"0040 preflight: {label}; IDs (first 20): {conflicts}; no DDL applied"
            )


# Exact statements from the approved proposal, frozen for repeatable review.
UPGRADE_SQL = (
    """CREATE TABLE auth_verified_identities (
  id BIGINT NOT NULL AUTO_INCREMENT,
  candidate_id BIGINT NOT NULL,
  channel ENUM('email', 'whatsapp') NOT NULL,
  normalized_value VARCHAR(320) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  verified_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_auth_identity_channel_value (channel, normalized_value),
  UNIQUE KEY uq_auth_identity_candidate_channel (candidate_id, channel),
  CONSTRAINT fk_auth_identity_candidate FOREIGN KEY (candidate_id) REFERENCES candidates(id)
) ENGINE=InnoDB""",
    """CREATE TABLE candidate_notification_preferences (
  id BIGINT NOT NULL AUTO_INCREMENT,
  candidate_id BIGINT NOT NULL,
  topic VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  channel ENUM('email', 'whatsapp') NOT NULL,
  enabled BOOLEAN NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_notification_candidate_topic_channel (candidate_id, topic, channel),
  CONSTRAINT fk_notification_preference_candidate FOREIGN KEY (candidate_id) REFERENCES candidates(id)
) ENGINE=InnoDB""",
    """CREATE TABLE job_candidate_preferences (
  candidate_id BIGINT NOT NULL,
  job_id BIGINT NOT NULL,
  saved BOOLEAN NOT NULL DEFAULT FALSE,
  dismissed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (candidate_id, job_id),
  KEY ix_job_preference_job (job_id),
  KEY ix_job_preference_saved (candidate_id, saved, updated_at),
  KEY ix_job_preference_dismissed (candidate_id, dismissed, updated_at),
  CONSTRAINT fk_job_preference_candidate FOREIGN KEY (candidate_id) REFERENCES candidates(id),
  CONSTRAINT fk_job_preference_job FOREIGN KEY (job_id) REFERENCES jobs(id)
) ENGINE=InnoDB""",
    """ALTER TABLE candidate_preferences
  ADD COLUMN reviewed_at DATETIME(6) NULL""",
    """ALTER TABLE candidate_target_profiles
  ADD COLUMN notes TEXT NULL,
  ADD COLUMN archived_at DATETIME(6) NULL,
  ADD UNIQUE KEY uq_target_candidate_id (candidate_id, id),
  ADD KEY ix_target_candidate_archived (candidate_id, archived_at)""",
    """CREATE TABLE resume_personas (
  id BIGINT NOT NULL AUTO_INCREMENT,
  candidate_id BIGINT NOT NULL,
  target_profile_id BIGINT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  content JSON NOT NULL,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  source_updated_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_resume_persona_target (target_profile_id),
  KEY ix_persona_candidate_target (candidate_id, target_profile_id),
  CONSTRAINT fk_persona_candidate FOREIGN KEY (candidate_id) REFERENCES candidates(id),
  CONSTRAINT fk_persona_owned_target FOREIGN KEY (candidate_id, target_profile_id)
    REFERENCES candidate_target_profiles(candidate_id, id),
  CONSTRAINT ck_persona_revision CHECK (revision >= 1),
  CONSTRAINT ck_persona_content_object CHECK (JSON_TYPE(content) = 'OBJECT')
) ENGINE=InnoDB""",
    """ALTER TABLE resume_profiles
  ADD COLUMN headline VARCHAR(255) NULL,
  ADD COLUMN portfolio_url TEXT NULL,
  ADD COLUMN reviewed_sections JSON NULL,
  ADD COLUMN revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  ADD CONSTRAINT ck_resume_revision CHECK (revision >= 1),
  ADD CONSTRAINT ck_resume_reviewed_array CHECK (
    reviewed_sections IS NULL OR JSON_TYPE(reviewed_sections) = 'ARRAY'
  )""",
    """ALTER TABLE resume_versions
  ADD COLUMN target_profile_id BIGINT NULL,
  ADD COLUMN archived_at DATETIME(6) NULL,
  ADD COLUMN current_scope BIGINT GENERATED ALWAYS AS (
    CASE WHEN is_current = 1 AND archived_at IS NULL
      THEN COALESCE(target_profile_id, 0) ELSE NULL END
  ) STORED,
  ADD KEY ix_resume_owned_target (candidate_id, target_profile_id),
  ADD KEY ix_resume_session (session_id),
  ADD CONSTRAINT fk_resume_owned_target FOREIGN KEY (candidate_id, target_profile_id)
    REFERENCES candidate_target_profiles(candidate_id, id),
  ADD UNIQUE KEY uq_resume_current_scope (candidate_id, current_scope)""",
)

DOWNGRADE_SQL = (
    "DROP TABLE resume_personas",
    "DROP TABLE job_candidate_preferences",
    "DROP TABLE candidate_notification_preferences",
    "DROP TABLE auth_verified_identities",
    """ALTER TABLE resume_versions
       DROP FOREIGN KEY fk_resume_owned_target,
       DROP FOREIGN KEY fk_resume_versions_session_id_resume_build_sessions,
       DROP INDEX uq_resume_current_scope,
       DROP INDEX ix_resume_owned_target,
       DROP INDEX ix_resume_session,
       DROP COLUMN current_scope,
       DROP COLUMN target_profile_id,
       DROP COLUMN archived_at""",
    """ALTER TABLE resume_versions
       ADD CONSTRAINT fk_resume_versions_session_id_resume_build_sessions
         FOREIGN KEY (session_id) REFERENCES resume_build_sessions(id)""",
    """ALTER TABLE resume_profiles
       DROP CHECK ck_resume_reviewed_array,
       DROP CHECK ck_resume_revision,
       DROP COLUMN revision,
       DROP COLUMN reviewed_sections,
       DROP COLUMN portfolio_url,
       DROP COLUMN headline""",
    """ALTER TABLE candidate_target_profiles
       DROP INDEX ix_target_candidate_archived,
       DROP INDEX uq_target_candidate_id,
       DROP COLUMN archived_at,
       DROP COLUMN notes""",
    "ALTER TABLE candidate_preferences DROP COLUMN reviewed_at",
)


def upgrade() -> None:
    if op.get_context().as_sql:
        op.execute("-- REVIEW ONLY: online preflight must pass before executing this DDL")
    else:
        preflight(op.get_bind())
    for statement in UPGRADE_SQL:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # Destructive to new dashboard data; production rollback should retain
    # the additive schema. Exercised only on an isolated database in this task.
    # Recreate the original session FK in the following ALTER so InnoDB
    # restores its implicit supporting index. MySQL rejects dropping and
    # re-adding a named FK in one ALTER (1826). All writers must be stopped
    # for downgrade; retaining the additive schema is preferred in production.
    for statement in DOWNGRADE_SQL:
        op.execute(sa.text(statement))
