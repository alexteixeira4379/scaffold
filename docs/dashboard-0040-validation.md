# Migration 0040 — resultado dos testes isolados

**Validada em MySQL 8.0.46 e 9.4.0: 11 testes aprovados em cada versão.** Após a autorização inicial de criação/testes, o usuário autorizou a aplicação e publicação com o pedido "faz o push-railway agora". A integração completa do dashboard continua em andamento.

## Entrega para revisão

- [Migration 0040](../migrations/core/versions/0040_dashboard_persistence.py), descendente de `0039`.
- [SQL de upgrade](dashboard-0040-review.sql): exportado pelo Alembic, com os oito comandos DDL aprovados; leitura/validação online de preflight não é executada na exportação. **Não executar esse SQL diretamente para contornar o preflight.**
- [SQL de downgrade](dashboard-0040-downgrade-review.sql): apenas para revisão e teste isolado; destrói dados das novas estruturas.
- [Diff completo de código local do scaffold](dashboard-0040-code-review.patch), incluindo as mudanças de autenticação/cache da etapa anterior, a migration e os testes. Os documentos de revisão são arquivos separados.
- [Resultados dos testes](dashboard-0040-test-results.txt), [schema testado das oito tabelas](dashboard-0040-tested-schema.json) e [hashes/versão/imagem](dashboard-0040-evidence.json).
- [Proposta e impactos aprovados para criação](dashboard-schema-proposal.md).

Base do repositório: `484f6a0a560766a79a8e394657329343c5905cf1`.
SHA-256 da migration testada: `bc86e0ebdd9850e42ea0fdc1f1c3bced746c1b5c18cf61d30602c2b276d0c761`.

## Ambiente e abrangência

Docker MySQL **8.0.46**, imagem `sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b`. Container novo com diretório de dados em tmpfs, rede Docker interna, credenciais exclusivas de teste e sem variáveis de serviços de produção. As 39 migrations existentes foram executadas desde um banco vazio; depois foram inseridos dois candidatos fictícios, objetivos, perfis e documentos principais/históricos. A migration nova foi aplicada sobre esses dados.

Os containers e redes criados para estes testes foram removidos. Os containers locais que já existiam foram preservados.

O teste é reproduzível e cria seu próprio ambiente; não aceita URL de banco externo:

```bash
RUN_DASHBOARD_MYSQL_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_dashboard_migration_mysql.py -v
```

O resultado foi `11 passed in 21.64s`. Ruff e `git diff --check` também passaram.

| Cenário | Resultado |
| --- | --- |
| Documentos atuais duplicados, objetivos principais duplicados e candidatos órfãos | Upgrade recusado antes do primeiro DDL; revisão permanece 0039 |
| Aplicação parcial simulada | Recusada sem stamp; recuperação explícita da única tabela vazia criada restaura o baseline |
| Registros existentes | Valores anteriores preservados; documentos continuam principais; campos opcionais NULL e revisão inicial 1 |
| Identidades | Unicidade por canal/valor e candidato/canal; nenhuma identidade existente é marcada como verificada |
| Preferências | Chaves candidato/assunto/canal e candidato/vaga únicas; FKs e defaults conferidos |
| Personas | FK composta bloqueia objetivo de outro candidato; persona por objetivo é única; cópia preservada após alterar currículo e desativar persona |
| JSON e revisões | Banco rejeita tipo JSON incompatível e revisão zero |
| Documentos por objetivo | Principal e documento por objetivo coexistem; duplicação do atual e objetivo de outro candidato são recusados; histórico/arquivado permanece |
| Concorrência de documentos | Duas transações independentes: uma criação e uma rejeição por unicidade |
| Concorrência de revisão | Dois UPDATEs condicionais: um altera a revisão, outro retorna zero linhas |
| Downgrade e reaplicação | `0039 → 0040 → 0039 → 0040`, preservando o schema lógico baseline e reproduzindo o schema novo |

Comparações de schema ignoram somente o contador AUTO_INCREMENT e a ordem textual das definições emitidas por SHOW CREATE TABLE. Tipos, colunas, constraints, nomes de índices e valores default são conferidos.

## Correção feita durante o teste

O DDL de **upgrade aprovado permanece igual**. O downgrade precisou tratar o índice de sessão do InnoDB: ao adicionar `ix_resume_session`, o MySQL substitui o índice implícito que sustentava a FK de `session_id`. Remover o índice novo diretamente falha (1553). Restaurar um índice explícito equivalente deixa um índice redundante na reaplicação.

O downgrade final remove a FK de sessão no ALTER que desfaz as adições e a recria no ALTER imediatamente seguinte. Assim o InnoDB restaura o índice implícito original. MySQL 8.0.46 recusa remover e recriar a constraint com o mesmo nome em um único ALTER (1826), portanto esses são dois comandos.

**Downgrade exige todos os escritores parados** por haver uma janela entre esses ALTERs, além de destruir as novas persistências. Em produção, a reversão preferida é manter o schema aditivo e voltar o código compatível; downgrade de produção não está autorizado.

## Pendências antes de aplicação em produção

- A única migration local nova em relação à revisão `0039` registrada no plano é `0040`; há um único head. Nenhuma migration antiga foi editada.
- Preflight de produção executado em transação somente de leitura: revisão `0039`, MySQL `9.4.0`, sem conflitos. Volumes: 2 candidatos, 1 objetivo, 1 perfil e 1 documento. A suíte foi repetida em MySQL 9.4.0 isolado: 11 testes aprovados em 22.06s.
- Não há diff em `src/scaffold/messaging` nem em `deploy/migrations`. Porém o comando já existente do serviço `migration` também executa `scaffold.messaging.sync`; antes do push, verificar o estado e as diferenças de topologia que esse comando pode aplicar no ambiente real.
- Confirmar backup/restauração e janela para metadata locks/reconstrução de tabela. Parar os escritores durante o preflight e a alteração evita corrida entre a verificação e a criação do índice único. Não foi feito benchmark com volume de produção.
- Em falha após algum DDL, Alembic continuará na revisão anterior enquanto objetos parciais podem existir. O próximo upgrade recusa os objetos existentes. Registrar o último comando concluído, conferir o schema e dados, e preparar recuperação explícita; **não usar stamp nem apagar tabelas com dados para forçar passagem**. O teste de recuperação cobre a primeira tabela vazia; não certifica recuperação automática de todos os pontos possíveis.
- O teste de UPDATE condicional valida a capacidade do schema. Ainda é necessário implementar essa política em todos os escritores do currículo. Também falta o uso dos novos modelos/contratos pelas APIs e a integração das telas. Os novos nomes de tabela não devem ser removidos por autogeração Alembic enquanto os modelos correspondentes estiverem pendentes.
- O código local de autenticação da etapa anterior continua dependente de uma nova versão do scaffold; não publicar auth-api/dashboard com pins antigos. A aplicação da migration não encerra a integração das funcionalidades.

## Próxima autorização

Autorização específica recebida: aplicar a migration 0040 e fazer o push do scaffold pelo fluxo push-railway. O hash da migration e seu DDL permanecem iguais aos testados. A publicação ainda deve ser confirmada pelo deployment e pela revisão real, sem confundir este relatório de preparação com evidência de aplicação.
