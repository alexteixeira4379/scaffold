"""0040 ORM metadata must preserve the approved production constraints."""

from sqlalchemy import MetaData, String
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable
from scaffold.models import (
    AuthVerifiedIdentity,
    CandidateNotificationPreference,
    JobCandidatePreference,
    ResumePersona,
    ResumeProfile,
    ResumeVersion,
)


def ddl(model, dialect):
    return str(CreateTable(model.__table__).compile(dialect=dialect))


def test_mysql_verified_identity_and_notification_types():
    identity = ddl(AuthVerifiedIdentity, mysql.dialect())
    assert "ENUM('email','whatsapp')" in identity
    assert "VARCHAR(320) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin" in identity
    assert "verified_at DATETIME(6)" in identity
    assert "CURRENT_TIMESTAMP(6)" in identity
    assert "fk_auth_identity_candidate" in identity
    notification = ddl(CandidateNotificationPreference, mysql.dialect())
    assert "VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin" in notification
    assert "ENUM('email','whatsapp')" in notification


def test_mysql_persona_profile_checks_and_unsigned_revision():
    persona = ddl(ResumePersona, mysql.dialect())
    profile = ddl(ResumeProfile, mysql.dialect())
    for rendered in (persona, profile):
        assert "revision BIGINT UNSIGNED" in rendered
    assert "CONSTRAINT ck_persona_content_object CHECK" in persona
    assert "CONSTRAINT ck_persona_revision CHECK" in persona
    assert "CONSTRAINT ck_resume_reviewed_array CHECK" in profile
    assert "CONSTRAINT ck_resume_revision CHECK" in profile
    assert "fk_persona_owned_target" in persona
    assert "fk_resume_owned_target" in ddl(ResumeVersion, mysql.dialect())


def test_json_checks_are_mysql_only_including_cloned_metadata():
    # SQLite JSON_TYPE returns lowercase names; never apply MySQL uppercase checks.
    metadata = MetaData()
    for model in (ResumePersona, ResumeProfile):
        cloned = model.__table__.to_metadata(metadata)
        for column in cloned.columns:
            if isinstance(column.type, ENUM):
                column.type = String(128)
        # Include referenced parent tables so FK compilation can resolve names.
        for fk in model.__table__.foreign_keys:
            if fk.column.table.name not in metadata.tables:
                fk.column.table.to_metadata(metadata)
        original = ddl(model, sqlite.dialect()) if model is ResumePersona else "revision >= 1"
        copied = str(CreateTable(cloned).compile(dialect=sqlite.dialect()))
        for rendered in (original, copied):
            assert "JSON_TYPE" not in rendered
            assert "revision >= 1" in rendered


def test_boolean_defaults_compile_as_sql_literals():
    assert "DEFAULT FALSE" in ddl(JobCandidatePreference, mysql.dialect())
    assert "DEFAULT FALSE" in ddl(ResumePersona, mysql.dialect())
