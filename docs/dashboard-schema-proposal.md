# Proposta de banco para integração do dashboard

Status: **criação e testes isolados autorizados pelo usuário** ("Autorizar criação e testes isolados"). A migration `0040` foi criada e testada em MySQL 8.0.46 descartável. O DDL de upgrade abaixo foi preservado. Aplicação em produção e push do scaffold foram posteriormente autorizados pelo pedido explícito de push-railway. Resultado e evidências: [relatório de validação](dashboard-0040-validation.md).

## Base e revisão das pendências

Modelos e cadeia Alembic locais revisados em 2026-09-19. O plano recebido registra produção na revisão `0039`; essa informação ainda precisa ser reconfirmada no ambiente antes da aplicação. A cadeia original terminava em `0039`; agora há uma única migration nova, `0040_dashboard_persistence.py`, descendente de `0039`.

O comando do serviço `migration` em `deploy/migrations/railway.json` é `uv run alembic -c alembic.core.ini upgrade head && uv run python -m scaffold.messaging.sync`. Portanto, o push do scaffold pode aplicar banco e alterar mensageria. Antes de qualquer push, comparar novamente a revisão real com **todas** as revisões locais pendentes, conferir o diff da topologia e apresentar quaisquer mudanças adicionais.

## DDL proposto (MySQL 8)

Os IDs seguem o BIGINT assinado dos pais. FKs usam RESTRICT (padrão); não há exclusão em cascata de histórico. `updated_at` deve ser atualizado pela API/ORM, como nos modelos existentes. O charset/collation de IDs textuais de acesso é explícito para tornar a unicidade independente da collation do banco. E-mails e telefones devem ser normalizados pelo domínio de autenticação antes da escrita (telefone em E.164; e-mail sem espaços externos e política de caixa consistente em emissão e verificação).

```sql
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
```

`current_scope` é uma coluna técnica gerada para impor **um documento atual por candidato/objetivo**, incluindo o currículo principal (`target_profile_id NULL` → escopo `0`). Documentos históricos/arquivados recebem escopo NULL e continuam referenciáveis. Não basta UNIQUE(candidate_id, target_profile_id, is_current): NULL não garante unicidade do principal e a regra bloquearia múltiplas versões históricas. O escopo respeita a semântica atual de um documento corrente, independentemente de formato; se forem necessárias versões PDF e DOCX correntes simultâneas, ajustar a regra antes de aprovar.

A FK composta impede associar uma persona ou documento a um objetivo de outro candidato. A propriedade do objetivo continua sendo validada pela API. O índice `uq_target_candidate_id` é redundante em unicidade com o PK, mas necessário como chave referenciada composta.

A política de palavras-chave já usa VARCHAR(32), portanto não precisa de alteração DDL. Os valores `preferred`, `required` e `excluded` precisam de validação explícita e mapeamento compatível com `include`/`exclude` no código.

## Impacto e contratos de escrita

- Todas as quatro tabelas novas começam vazias. Nenhum e-mail/telefone existente é declarado verificado automaticamente. Cadastro novo só cria candidato após prova do e-mail; conflitos de identidade são tratados explicitamente.
- Campos opcionais novos ficam NULL. Currículos existentes começam em revisão 1. NULL em `reviewed_sections` representa ausência de revisão; não confirma nenhuma seção vazia.
- Documentos existentes continuam principais. Nenhum arquivo, match ou candidatura é excluído. Nenhuma persona é criada implicitamente a partir do currículo principal.
- Preferência de notificação ausente mantém o comportamento anterior. Tópicos aceitos pela API: `new_opportunities`, `application_updates`, `action_required`, `weekly_digest`, `billing`; autenticação e respostas solicitadas não passam por essas preferências.
- `content` da persona contém uma cópia independente validada das seis seções, seleção, ordem, resumo e adaptações. JSON válido apenas não basta: validar esquema completo na resume-api. Revisão é incrementada condicionalmente em toda escrita, inclusive importação e WhatsApp.
- Objetivo principal único: bloquear a linha do candidato (`SELECT ... FOR UPDATE`) antes de limpar/definir `is_default` na mesma transação, em **todos** os escritores. Nenhuma alteração de objetivos existentes na migration.
- Escrita de documento atual: serializar por candidato/objetivo, desmarcar o atual e inserir o novo na mesma transação. A constraint é a última proteção. Publicação de workers deverá manter compatibilidade durante a transição.
- Arquivamento é lógico; jobs autorizados continuam usando seus IDs de documentos. Duplicação cria objetivo pausado e copia persona como snapshot independente.
- Transição de assinatura e deduplicação semanal usam o mecanismo durável de domínio/outbox já existente; revisar seus contratos e chaves antes de implementar. Redis fica limitado a tokens, limites de requisição e cache, sem substituir as persistências deste documento.

## Pré-verificações e estratégia

1. Depois da autorização de criação: produzir migration aditiva posterior a `0039`; não alterar migrations antigas. O arquivo deve checar conflitos antes do primeiro DDL, incluindo múltiplos documentos atuais por candidato.
2. Em banco MySQL isolado e descartável, aplicar cadeia até `0039`, carregar fixtures de dois candidatos com documentos e objetivos, executar nova migration e verificar constraints, defaults, isolamento, concorrência e downgrade. Nenhuma variável de produção será reutilizada nesse teste.
3. Apresentar revisão/hash exatos, SQL produzido, resultado dos testes, versão do MySQL e o diff completo (incluindo mensageria) para **autorização de aplicação**.
4. Antes da aplicação autorizada: consultar `alembic_version`, versão real do MySQL, `SHOW CREATE TABLE`, collation, índices existentes e volume das tabelas. Confirmar backup/restauração e janela adequada. Construção de índices e coluna gerada STORED pode reconstruir tabela e adquirir metadata locks; não prometer ALTER instantâneo. Ajustar algoritmo à versão/volume medidos.
5. Consulta de conflito prévia: `SELECT candidate_id, COUNT(*) FROM resume_versions WHERE is_current = 1 GROUP BY candidate_id HAVING COUNT(*) > 1`. Se houver resultados, parar e apresentar IDs e proposta de correção; não eleger uma versão silenciosamente. Conferir também duplicidade de `is_default` e referências órfãs.
6. MySQL DDL não é revertido atomicamente junto com todos os ALTERs. Aplicar com verificação explícita de cada passo e recuperação documentada de aplicação parcial; não marcar revisão Alembic manualmente para ocultar erro. Se produção divergir, revisar a proposta antes de continuar.
7. Depois da autorização específica: aplicar esquema, verificar colunas/índices/revisão e deployment `migration`; publicar APIs/workers compatíveis e só depois dashboard. Atualizar pins do scaffold nos consumidores e conferir cada deployment contra seu commit.
8. Reversão operacional preferida: voltar código compatível mantendo esquema aditivo. Downgrade destrutivo perde identidades, preferências e personas e requer nova autorização; não faz parte da publicação normal.

## Autorizações

Recebida: criação da migration correspondente a esta proposta e testes em MySQL isolado. Recebida posteriormente: aplicação em produção e push do scaffold (pedido explícito de push-railway). Ver [resultado](dashboard-0040-validation.md). O DDL de upgrade aprovado não foi alterado; o downgrade restaura a FK de sessão e seu índice implícito, conforme o relatório.
