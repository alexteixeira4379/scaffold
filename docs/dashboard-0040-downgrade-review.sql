-- Running downgrade 0040 -> 0039

DROP TABLE resume_personas;

DROP TABLE job_candidate_preferences;

DROP TABLE candidate_notification_preferences;

DROP TABLE auth_verified_identities;

ALTER TABLE resume_versions
       DROP FOREIGN KEY fk_resume_owned_target,
       DROP FOREIGN KEY fk_resume_versions_session_id_resume_build_sessions,
       DROP INDEX uq_resume_current_scope,
       DROP INDEX ix_resume_owned_target,
       DROP INDEX ix_resume_session,
       DROP COLUMN current_scope,
       DROP COLUMN target_profile_id,
       DROP COLUMN archived_at;

ALTER TABLE resume_versions
       ADD CONSTRAINT fk_resume_versions_session_id_resume_build_sessions
         FOREIGN KEY (session_id) REFERENCES resume_build_sessions(id);

ALTER TABLE resume_profiles
       DROP CHECK ck_resume_reviewed_array,
       DROP CHECK ck_resume_revision,
       DROP COLUMN revision,
       DROP COLUMN reviewed_sections,
       DROP COLUMN portfolio_url,
       DROP COLUMN headline;

ALTER TABLE candidate_target_profiles
       DROP INDEX ix_target_candidate_archived,
       DROP INDEX uq_target_candidate_id,
       DROP COLUMN archived_at,
       DROP COLUMN notes;

ALTER TABLE candidate_preferences DROP COLUMN reviewed_at;

UPDATE alembic_version SET version_num='0039' WHERE alembic_version.version_num = '0040';

