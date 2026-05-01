# Jobito Scaffold

Biblioteca Python compartilhada do ecossistema **Jobito**: modelos de domínio, acesso a dados, migrações e integrações (mensageria e IA) pensadas para serem consumidas por vários serviços sem acoplar implementações concretas de infraestrutura.

## Propósito

Este pacote (`scaffold`) concentra o que é comum entre serviços:

- **Dados**: modelos SQLAlchemy 2 (async), convenções de nomenclatura, sessão async e repositórios por agregado.
- **Mensageria**: contrato estável (`QueueClient`, formatos de mensagem) com RabbitMQ por baixo e backend em memória para testes.
- **Cache**: contrato estável (`CacheClient`) com URL configurável e Redis isolado como implementação.
- **IA**: contrato estável (`AIClient`, níveis de inferência, saída texto ou JSON) com Groq (API compatível com OpenAI) e backend em memória para testes.

A ideia é que cada serviço dependa de **portas e contratos** (e de `Settings`), e que trocas de broker, de LLM ou de modelo fiquem centralizadas em configuração e em fábricas pequenas (`create_messaging_client`, `create_llm_backend`).

## Requisitos

- Python **3.11+**
- MySQL acessível pela URL async configurada (por omissão `mysql+asyncmy://…`)

## Instalação

```bash
cp .env.example .env
```

Edite o `.env` com a URL do MySQL e, se for usar integrações reais, credenciais de RabbitMQ, cache e Groq.

Instalação editável com ferramentas de desenvolvimento:

```bash
pip install -e ".[dev]"
```

Instalação da biblioteca:

```bash
pip install -e .
```

Extras opcionais por domínio (já incluídos em `[dev]` neste projeto):

- **`[ai]`**: `httpx` para o cliente Groq.

## Configuração

Variáveis são lidas a partir do `.env` e expostas em `scaffold.config.Settings` (via `get_settings()`).

| Área | Variáveis principais |
|------|----------------------|
| Base de dados | `DATABASE_URL` (async, ex.: `mysql+asyncmy://user:pass@host:3306/db`), `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_ECHO` |
| Mensageria | `MESSAGING_BACKEND` (`rabbitmq` ou `memory`), `RABBITMQ_URL` (obrigatório se `rabbitmq`) |
| Cache | `CACHE_URL` (URL completa do backend de cache, ex.: `redis://localhost:6379/0`), `CACHE_MAX_RETRIES` (tentativas em falhas transitórias de rede no `SyncJsonSessionStore`, omissão 4), `CACHE_RETRY_BASE_DELAY_S` (segundos base do backoff exponencial com jitter, omissão 0.08) |
| IA | `AI_PROVIDER` (`groq` ou `memory`), `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL_*`, `GROQ_TIMEOUT_S` |

Para desenvolvimento local sem RabbitMQ ou Groq, use `MESSAGING_BACKEND=memory` e `AI_PROVIDER=memory`.

## Uso da biblioteca

### Sessão e repositórios

A sessão async é criada a partir de `get_engine()` / `get_session_factory()` em `scaffold.db.session`. Os repositórios em `scaffold.repositories` encapsulam consultas comuns sobre os modelos em `scaffold.models`.

O padrão esperado num serviço é injetar ou construir uma `AsyncSession` (por exemplo a partir de `async_sessionmaker`) e delegar persistência aos repositórios, mantendo a lógica de negócio fora dos módulos de infraestrutura.

### Mensageria

```python
from scaffold.messaging import QueueClient
from scaffold.config import get_settings

settings = get_settings()
queue = QueueClient.from_settings(settings, "nome.da.fila")
await queue.connect()
try:
    await queue.publish({"evento": "exemplo"})
    msg = await queue.read()
    if msg is not None:
        corpo = msg.body
        tentativas = msg.read_count
        await queue.delete(msg)
finally:
    await queue.close()
```

O serviço não referencia RabbitMQ diretamente: apenas o nome da fila e o contrato de mensagens. Outro backend pode ser acrescentado na fábrica mantendo a mesma superfície.

### Cache

```python
from scaffold.cache import CacheClient
from scaffold.config import get_settings

cache = CacheClient.from_settings(get_settings())
await cache.connect()
try:
    await cache.set("job:url:hash", "123", ttl_s=300)
    valor = await cache.get("job:url:hash")
    await cache.set_json("job:payload", {"id": 123}, ttl_s=300)
    payload = await cache.get_json("job:payload")
finally:
    await cache.close()
```

O serviço usa apenas operações de cache. O backend concreto fica atrás de `CACHE_URL` e da factory do scaffold.

### IA

```python
from scaffold.ai import AIClient, ResponseMode
from scaffold.config import get_settings

client = AIClient.from_settings(get_settings())
resultado = await client.basic(
    "Explique em uma frase o que é um ATS.",
    ResponseMode.TEXT,
    system="Respostas curtas em português.",
)
texto = resultado.as_text()
```

Para saída estruturada, use `ResponseMode.JSON` e consuma com `resultado.as_json()`. Os métodos `basic`, `intermediate`, `complex` e `thinking` diferenciam **custo ou capacidade esperada**; o modelo concreto por nível vem só do `Settings` (`GROQ_MODEL_*`), o que permite evoluir modelos sem alterar o código do consumidor.

## Modelo de dados (visão geral)

O schema do contexto **`core`** separa responsabilidades em camadas:

| Área | Papel | Tabelas principais (ORM) |
|------|--------|---------------------------|
| Candidato | identidade, preferências globais, perfis-alvo roteáveis e keywords | `candidates`, `candidate_preferences`, `candidate_target_profiles`, `candidate_target_profile_keywords`, `candidate_events` |
| Coleta | definição e execução de busca de vagas, sem vínculo a candidato | `job_discovery_sources`, `job_collection_definitions`, `job_collection_runs`, `job_collection_checkpoints` |
| Vaga | catálogo central e keywords de roteamento | `jobs`, `job_raw_payloads`, `job_events`, `job_routing_keywords` |
| Match | elegibilidade barata e associação final candidato ↔ vaga | `job_candidate_eligibilities`, `job_matches`, `job_match_scores`, `job_match_evaluations`, `job_match_events` |
| Candidatura | fluxo de aplicação (depende de `job_matches`) | ver revisão `0008_application` |
| Tracking | eventos com identidade de sessão externa | `tracking_*` com coluna `session_key` onde aplicável |

Os repositórios em `scaffold.repositories` seguem esses agregados (por exemplo `JobCollectionDefinitionRepository`, `CandidateTargetProfileRepository`, `JobCandidateEligibilityRepository`).

## Migrações (Alembic)

Neste repositório existe o contexto **`core`**, configurado em `alembic.core.ini` e revisões em `migrations/core/versions/`. O Alembic lê `DATABASE_URL` via `get_settings()` (defina-a no ambiente ou no `.env` antes de executar comandos).

Aplicar todas as migrações até o estado atual:

```bash
uv run alembic -c alembic.core.ini upgrade head
```

Criar uma nova revisão (com modelos autogerados quando aplicável):

```bash
uv run alembic -c alembic.core.ini revision --autogenerate -m "descrição curta"
```

### Zerar o banco (wipe)

Depois de **alterações grandes nas revisões já existentes**, o histórico em `alembic_version` pode deixar de corresponder ao que o `downgrade base` assume. Nesse caso o caminho seguro é **apagar o banco e recriar o schema do zero**, em vez de depender só do downgrade.

Exemplo com cliente MySQL (ajuste usuário, host e nome do banco):

```bash
mysql -u USUARIO -p -h HOST -e "DROP DATABASE IF EXISTS nome_do_banco; CREATE DATABASE nome_do_banco CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Em seguida, com `DATABASE_URL` apontando para esse banco:

```bash
uv run alembic -c alembic.core.ini upgrade head
```

Use wipe apenas em **ambiente de desenvolvimento** ou com **backup**; o comando apaga todos os dados e a tabela de versão do Alembic.

Outros contextos de migração podem ser acrescentados no mesmo padrão quando existir necessidade e ficheiros `alembic.*.ini` correspondentes.

## Desenvolvimento

```bash
python3.11 -m pytest
python3.11 -m ruff check src tests
python3.11 -m mypy src/scaffold
```

Os testes cobrem sobretudo os backends em memória de mensageria e IA, de forma a validar contratos sem dependências externas.

## Estrutura do repositório

| Caminho | Conteúdo |
|---------|----------|
| `src/scaffold/` | Pacote instalável |
| `src/scaffold/models/` | Modelos ORM por domínio |
| `src/scaffold/repositories/` | Acesso a dados por área |
| `src/scaffold/db/` | Motor, sessão e tipos |
| `src/scaffold/messaging/` | Contratos, RabbitMQ, memória, `QueueClient` |
| `src/scaffold/ai/` | Contratos, Groq, memória, `AIClient` |
| `src/scaffold/config.py` | `Settings`, enums de backend |
| `migrations/core/` | Ambiente e revisões Alembic do núcleo |
| `tests/` | Testes automatizados |

## Licença e governança

Defina a licença e o processo de contribuição conforme a política da organização Jobito; este repositório serve como base técnica comum aos serviços que o consomem.
