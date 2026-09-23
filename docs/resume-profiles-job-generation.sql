-- Adiciona o valor 'job_generation' ao enum de origem do perfil de currículo.
-- Necessário para a geração de currículo especializado a partir de vaga
-- (POST /resume-profiles/{candidate_id}/generate-from-job no resume-api).

ALTER TABLE resume_profiles
  MODIFY COLUMN source ENUM('workflow', 'direct_api', 'job_generation') NOT NULL;
