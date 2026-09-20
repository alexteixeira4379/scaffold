-- Running upgrade 0039 -> 0040

-- REVIEW ONLY: online preflight must pass before executing this DDL;

CREATE TABLE auth_verified_identities (
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
) ENGINE=InnoDB;

CREATE TABLE candidate_notification_preferences (
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
) ENGINE=InnoDB;

CREATE TABLE job_candidate_preferences (
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
) ENGINE=InnoDB;

ALTER TABLE candidate_preferences
  ADD COLUMN reviewed_at DATETIME(6) NULL;

ALTER TABLE candidate_target_profiles
  ADD COLUMN notes TEXT NULL,
  ADD COLUMN archived_at DATETIME(6) NULL,
  ADD UNIQUE KEY uq_target_candidate_id (candidate_id, id),
  ADD KEY ix_target_candidate_archived (candidate_id, archived_at);

CREATE TABLE resume_personas (
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
) ENGINE=InnoDB;

ALTER TABLE resume_profiles
  ADD COLUMN headline VARCHAR(255) NULL,
  ADD COLUMN portfolio_url TEXT NULL,
  ADD COLUMN reviewed_sections JSON NULL,
  ADD COLUMN revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  ADD CONSTRAINT ck_resume_revision CHECK (revision >= 1),
  ADD CONSTRAINT ck_resume_reviewed_array CHECK (
    reviewed_sections IS NULL OR JSON_TYPE(reviewed_sections) = 'ARRAY'
  );

ALTER TABLE resume_versions
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
  ADD UNIQUE KEY uq_resume_current_scope (candidate_id, current_scope);

UPDATE alembic_version SET version_num='0040' WHERE alembic_version.version_num = '0039';

