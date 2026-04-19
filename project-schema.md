# Jobito — Documentação Consolidada de Modelagem de Banco e Responsabilidades

## 1. Objetivo deste documento

Este documento consolida as decisões tomadas para a estrutura de banco de dados do Jobito, com foco em:

* organização do schema por domínio
* separação clara de responsabilidades
* correção das migrations atuais
* base conceitual para implementação dos sistemas a partir de agora

Este material considera apenas a modelagem persistida do projeto:

* migrations
* tabelas
* relacionamentos
* models ORM

Não trata de workers, filas, pipelines, integrações externas ou outros projetos.

---

## 2. Premissas gerais

### 2.1 O projeto de migrations é isolado

A modelagem deve ser pensada como uma base central de persistência, independente de como os fluxos serão executados depois.

### 2.2 Separação de responsabilidades é obrigatória

A estrutura do banco deve separar com clareza:

* coleta de vagas
* perfil-alvo do candidato
* catálogo central de vagas
* elegibilidade intermediária
* match final candidato ↔ vaga
* candidatura
* currículo
* billing
* tracking

### 2.3 A origem da vaga não define o destinatário final

Uma vaga pode entrar por vários caminhos, e isso não pode decidir quem é o candidato correto.

A associação correta deve acontecer em camadas:

1. a vaga entra no catálogo
2. a vaga passa por pré-filtragem barata
3. o sistema monta um pool elegível
4. o sistema calcula o match final
5. só depois a candidatura entra em cena

### 2.4 A associação candidato ↔ vaga não pode depender de search listening

O modelo antigo se aproximava da ideia de:

* candidato ouvindo busca
* vaga chegando por uma busca
* candidato recebendo vaga porque ouvia aquela busca

Esse modelo foi rejeitado.

Motivo:

* vagas podem chegar de fontes diferentes
* a vaga correta não pode deixar de ser associada ao candidato correto só porque não veio pela mesma busca

### 2.5 Também foi rejeitado o modelo de cruzamento total

Também não queremos um modelo em que toda vaga seja cruzada com todos os candidatos.

Motivo:

* custo operacional alto
* crescimento ruim
* escalabilidade ruim

A solução adotada é:

* catálogo central de vagas
* perfis-alvo do candidato
* keywords normalizadas
* camada de elegibilidade barata
* match final apenas no subconjunto elegível

---

## 3. Modelo conceitual final

O modelo final do banco deve refletir estas camadas:

### 3.1 Collection

Responsável apenas por trazer vagas.

Não decide candidato.

### 3.2 Candidate Target Profiles

Responsável por representar o alvo profissional do candidato.

É a base de roteamento/elegibilidade.

### 3.3 Jobs

Catálogo central único de vagas.

Toda vaga entra aqui, independentemente da origem.

### 3.4 Eligibility

Camada intermediária barata para reduzir o universo de candidatos por vaga.

Ainda não é match final.

### 3.5 Match

Associação final candidato ↔ vaga.

Aqui entra score, racional e estado final do match.

### 3.6 Application

Execução da candidatura com base em um match já criado.

---

## 4. Regra de negócio consolidada

### 4.1 Fluxo lógico aceito

1. Uma vaga entra no catálogo central `jobs`
2. A vaga é classificada por atributos estruturais e keywords roteáveis
3. O sistema encontra perfis-alvo potencialmente compatíveis
4. O sistema grava isso como elegibilidade
5. Somente os elegíveis seguem para avaliação detalhada
6. O resultado final da avaliação gera `job_matches`
7. `job_applications` continua dependendo de `job_matches`

### 4.2 Fluxo lógico rejeitado

Foi rejeitada a ideia de:

* search definition ser a base da distribuição para candidatos
* candidate subscription ser o centro da associação candidato-vaga
* usar coleta como proxy para relevância do candidato

### 4.3 Search/Collection não define match

O domínio de collection/search existe apenas para:

* definir coleta
* registrar execução
* armazenar checkpoint

Ele não deve:

* conhecer candidato
* conhecer preset de candidato
* decidir para quem a vaga vai
* ser o centro da associação candidato-vaga

---

## 5. Organização por domínio

## 5.1 Candidate

### Objetivo

Representar o candidato, suas preferências globais e seus perfis-alvo.

### Tabelas finais

* `candidates`
* `candidate_preferences`
* `candidate_target_profiles`
* `candidate_target_profile_keywords`
* `candidate_events`

### Responsabilidades

#### `candidates`

Entidade principal do candidato.

Responsável por:

* identidade
* contato
* status da conta
* dados principais do usuário

#### `candidate_preferences`

Preferência global do candidato.

Responsável por:

* preferência padrão
* configuração geral
* fallback global

Não é a unidade de roteamento.

#### `candidate_target_profiles`

Perfil-alvo roteável do candidato.

Responsável por:

* alvo profissional
* hard filters principais
* segmentação do candidato para oportunidades

Exemplos conceituais:

* Backend BR
* Remote US
* Data/AI LATAM

#### `candidate_target_profile_keywords`

Keywords normalizadas do perfil-alvo.

Responsável por:

* include/exclude
* indexação barata
* pré-filtro textual
* evitar JSON genérico para retrieval

#### `candidate_events`

Histórico de eventos do candidato.

---

## 5.2 Collection

### Objetivo

Representar apenas a coleta de vagas.

### Tabelas finais

* `job_discovery_sources`
* `search_definitions` ou `job_collection_definitions`
* `search_runs` ou `job_collection_runs`
* `search_checkpoints` ou `job_collection_checkpoints`

### Responsabilidades

#### `job_discovery_sources`

Origem de descoberta da vaga.

Exemplos:

* LinkedIn
* Indeed
* site institucional
* página pública de carreira

#### `search_definitions` / `job_collection_definitions`

Definição executável de coleta.

Responsável por:

* termo de busca
* local
* país
* filtros de coleta
* schedule
* prioridade
* estado ativo

Não deve conhecer:

* candidato
* target profile
* subscription
* match

#### `search_runs` / `job_collection_runs`

Execuções da coleta.

#### `search_checkpoints` / `job_collection_checkpoints`

Checkpoint/cursor/paginação da coleta.

---

## 5.3 ATS

### Objetivo

Representar provedores de ATS e regras específicas.

### Tabelas finais

* `ats_providers`
* `ats_provider_domains`
* `ats_provider_configs`
* `ats_provider_rules`

### Responsabilidade

Domínio já considerado correto e mantido como está.

---

## 5.4 Company

### Objetivo

Representar empresas e seus domínios.

### Tabelas finais

* `companies`
* `company_domains`
* `company_events`

### Responsabilidade

Domínio já considerado correto e mantido como está.

---

## 5.5 Job

### Objetivo

Representar o catálogo central de vagas.

### Tabelas finais

* `jobs`
* `job_raw_payloads`
* `job_events`
* `job_routing_keywords`

### Responsabilidades

#### `jobs`

Catálogo único de vagas.

Toda vaga entra aqui, independentemente da origem.

A vaga deve poder existir mesmo sem relação imediata com candidato.

#### `job_raw_payloads`

Payload bruto da vaga para auditoria e reprocessamento.

#### `job_events`

Histórico de eventos da vaga.

#### `job_routing_keywords`

Keywords normalizadas da vaga.

Responsável por:

* apoio à elegibilidade barata
* indexação
* pré-filtro textual
* preparação para associação sem custo cartesiano

---

## 5.6 Eligibility

### Objetivo

Representar o pool reduzido de candidatos elegíveis para uma vaga.

### Tabelas finais

* `job_candidate_eligibilities`

### Responsabilidade

Camada intermediária entre:

* catálogo de vagas
* match final

Essa tabela existe para registrar:

* candidatos potencialmente compatíveis
* perfil-alvo usado
* resultado do roteamento barato
* estado da elegibilidade

Ela não substitui `job_matches`.

---

## 5.7 Match

### Objetivo

Representar a associação final entre candidato e vaga.

### Tabelas finais

* `job_matches`
* `job_match_scores`
* `job_match_evaluations`
* `job_match_events`

### Responsabilidades

#### `job_matches`

Associação final candidato ↔ vaga.

Responsável por:

* score final
* status do match
* vínculo definitivo
* referência ao perfil-alvo que originou o match

#### `job_match_scores`

Detalhamento dos scores por dimensão.

#### `job_match_evaluations`

Avaliação detalhada do motor de match.

#### `job_match_events`

Histórico do match.

---

## 5.8 Application

### Objetivo

Representar a execução da candidatura.

### Tabelas finais

* `job_applications`
* `application_runs`
* `application_steps`
* `application_artifacts`
* `application_sessions`
* `application_domain_rules`
* `application_messages`
* `application_failures`
* `application_events`

### Responsabilidade

Domínio já considerado correto e mantido.

Regra consolidada:

* application depende de match
* application não substitui match

---

## 5.9 Resume

### Objetivo

Representar builder e versões de currículo/carta.

### Tabelas finais

* `resume_build_steps`
* `resume_build_sessions`
* `resume_build_answers`
* `resume_versions`
* `cover_letter_versions`

### Responsabilidade

Domínio já considerado correto e mantido.

---

## 5.10 Billing

### Objetivo

Representar planos, cliente, assinatura, pagamento e eventos financeiros.

### Tabelas finais

* `billing_plans`
* `billing_customers`
* `billing_subscriptions`
* `billing_payments`
* `billing_events`

### Responsabilidade

Domínio já considerado correto e mantido.

---

## 5.11 Tracking

### Objetivo

Representar rastreamento de sessão, visita, clique, atribuição e eventos.

### Tabelas finais

* `tracking_visits`
* `tracking_sessions`
* `tracking_clicks`
* `tracking_attributions`
* `tracking_events`

### Regra consolidada

A identidade textual da sessão deve ser padronizada como:

* `session_key`

Essa padronização deve existir em todo o domínio de tracking.

---

## 6. Estado final esperado das migrations

## 6.1 Migration 0001 — Candidate

### Situação final esperada

* manter `candidates`
* manter `candidate_preferences`
* renomear `candidate_search_presets` para `candidate_target_profiles`
* remover keywords em JSON do profile
* criar `candidate_target_profile_keywords`
* manter `candidate_events`

### Regra consolidada

* `candidate_preferences` = preferência global
* `candidate_target_profiles` = unidade roteável

---

## 6.2 Migration 0002 — Company

### Situação final esperada

Sem redesenho estrutural.

---

## 6.3 Migration 0003 — ATS

### Situação final esperada

Sem redesenho estrutural.

---

## 6.4 Migration 0004 — Search / Collection

### Situação final esperada

* remover `search_templates`
* remover `candidate_search_subscriptions`
* remover qualquer dependência de candidato dentro de `search_definitions`
* manter apenas a responsabilidade de coleta
* manter runs e checkpoints
* opcionalmente renomear para `job_collection_*`

### Regra consolidada

Collection não decide match.

---

## 6.5 Migration 0005 — Job

### Situação final esperada

* manter `jobs`
* manter `job_raw_payloads`
* manter `job_events`
* criar `job_routing_keywords`

### Regra consolidada

`jobs` é o catálogo central único.

---

## 6.6 Migration 0006 — Resume

### Situação final esperada

Sem redesenho estrutural.

---

## 6.7 Migration 0007 — Match

### Situação final esperada

* criar `job_candidate_eligibilities`
* manter `job_matches` como associação final
* adicionar `candidate_target_profile_id` em `job_matches`
* manter scores/evaluations/events

### Regra consolidada

Eligibility vem antes de match.
Match final continua sendo a associação definitiva.

---

## 6.8 Migration 0008 — Application

### Situação final esperada

Sem redesenho estrutural.

---

## 6.9 Migration 0009 — Billing

### Situação final esperada

Sem redesenho estrutural.

---

## 6.10 Migration 0010 — Tracking

### Situação final esperada

* padronizar `session_key`
* remover inconsistência entre `session_id` e `session_key`
* manter o domínio sem novas tabelas

---

## 7. Estrutura consolidada final

```text
candidate
  candidates
  candidate_preferences
  candidate_target_profiles
  candidate_target_profile_keywords
  candidate_events

company
  companies
  company_domains
  company_events

ats
  ats_providers
  ats_provider_domains
  ats_provider_configs
  ats_provider_rules

collection
  job_discovery_sources
  search_definitions / job_collection_definitions
  search_runs / job_collection_runs
  search_checkpoints / job_collection_checkpoints

job
  jobs
  job_raw_payloads
  job_events
  job_routing_keywords

eligibility
  job_candidate_eligibilities

match
  job_matches
  job_match_scores
  job_match_evaluations
  job_match_events

application
  job_applications
  application_runs
  application_steps
  application_artifacts
  application_sessions
  application_domain_rules
  application_messages
  application_failures
  application_events

resume
  resume_build_steps
  resume_build_sessions
  resume_build_answers
  resume_versions
  cover_letter_versions

billing
  billing_plans
  billing_customers
  billing_subscriptions
  billing_payments
  billing_events

tracking
  tracking_visits
  tracking_sessions
  tracking_clicks
  tracking_attributions
  tracking_events
```

---

## 8. Fronteiras de responsabilidade consolidadas

## 8.1 O que collection faz

* traz vaga
* registra execução
* registra checkpoint

## 8.2 O que collection não faz

* não define elegibilidade de candidato
* não define match
* não guarda assinatura de candidato

## 8.3 O que candidate target profile faz

* define o alvo profissional do candidato
* concentra os filtros principais de roteamento
* fornece base para indexação por keywords

## 8.4 O que eligibility faz

* reduz o universo de candidatos por vaga
* registra candidatos potencialmente elegíveis
* prepara o subconjunto para scoring final

## 8.5 O que match faz

* registra a associação final candidato ↔ vaga
* guarda score final
* guarda a trilha de avaliação

## 8.6 O que application faz

* executa a candidatura
* depende de match

---

## 9. Decisões rejeitadas

As decisões abaixo foram explicitamente rejeitadas:

### 9.1 Rejeitado

Usar `search_definitions` como centro da distribuição de vagas.

### 9.2 Rejeitado

Usar `candidate_search_subscriptions` como centro da associação candidato-vaga.

### 9.3 Rejeitado

Modelar vagas chegando apenas por busca do candidato.

### 9.4 Rejeitado

Cruzar toda vaga contra todos os candidatos.

### 9.5 Rejeitado

Manter keywords do perfil-alvo apenas em JSON genérico.

---

## 10. Critérios finais de consistência

A estrutura só pode ser considerada correta se:

1. o domínio de collection não conhecer candidato
2. `candidate_target_profiles` for a unidade roteável do candidato
3. houver tabela própria para keywords do perfil-alvo
4. `jobs` continuar sendo o catálogo central único
5. houver tabela própria para keywords roteáveis da vaga
6. houver uma camada intermediária explícita de elegibilidade
7. `job_matches` continuar sendo a associação final
8. `job_applications` continuar dependendo de `job_matches`
9. tracking usar `session_key` de forma consistente
10. migrations e models refletirem exatamente essa separação

---

## 11. Próximo passo de implementação

O próximo passo é aplicar essa consolidação diretamente nas:

* migrations
* models ORM

A ordem prática recomendada é:

1. corrigir candidate
2. corrigir collection
3. ajustar job
4. ajustar match
5. ajustar tracking
6. revisar FKs e models impactadas

Depois disso, a base persistida estará pronta para sustentar a construção dos sistemas em cima de um modelo consistente.
