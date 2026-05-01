# Pipeline de filas: `job.ingestion` → `job.new`

## Fluxo

1. **Produtores** (`jcrawler`, `ats_scrapper`) publicam em `job.ingestion`.
2. **job-ingestion** consome `job.ingestion`, processa e publica em `job.new`; falhas de fluxo vão para `job.ingestion.dlq` conforme `QUEUE_DLQ_NAME`.
3. **Topologia** (filas, DLX e DLQ de `job.new`) é declarada em `scaffold.messaging.definitions.jobs` e aplicada com `python -m scaffold.messaging.sync` e `RABBITMQ_URL` definido.

## Ordem recomendada de deploy

1. Atualizar e publicar a versão do `scaffold` com a nova topologia.
2. Na infraestrutura RabbitMQ: executar `sync` para criar `job.ingestion`, `job.ingestion.dlq`, `job.ingestion.dlx`, `job.new`, `job.new.dlq`, `job.new.dlx`.
3. Atualizar **job-ingestion** com variáveis `QUEUE_INPUT_NAME=job.ingestion`, `QUEUE_OUTPUT_NAME=job.new`, `QUEUE_DLQ_NAME=job.ingestion.dlq` e fazer rollout.
4. Atualizar **jcrawler** e **ats_scrapper** (`JCRAWLER_QUEUE_NAME`, `ATS_SCRAPPER_QUEUE_NAME` ou defaults) para publicar em `job.ingestion`.

## Filas legadas (`jobs.new`, `jcrawler.jobs.new`)

- O broker pode recusar `declare` se já existirem filas com o mesmo nome e argumentos incompatíveis (`PRECONDITION_FAILED`). Nesse caso, drenar ou remover a fila legada antes de novo `sync`, ou migrar mensagens manualmente para `job.ingestion`.
- Consumidores externos que liam `jobs.new` diretamente do crawler devem passar a consumir `job.new` na saída do **job-ingestion**.
