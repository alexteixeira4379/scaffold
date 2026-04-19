# Jobito

Python monorepo for the Jobito ecosystem.

## Setup

```bash
cp .env.example .env
# edit .env with your database credentials
pip install -e ".[dev]"
```

## Migration Contexts

| Context | Owns |
|---|---|
| core | vac_search_definitions, vac_ats_sources, vac_jobs, job_profiles, job_user_sessions, vac_search_definition_profiles, vac_profile_jobs |
| jcrawler | crawler-specific operational tables |
| job_ingestion | ingestion pipeline tables |
| candidate_score_worker | scoring worker tables |
| nira | nira service tables |

## Running Migrations

Always run `core` first:

```bash
alembic -c alembic.core.ini upgrade head
alembic -c alembic.jcrawler.ini upgrade head
alembic -c alembic.job_ingestion.ini upgrade head
alembic -c alembic.candidate_score_worker.ini upgrade head
alembic -c alembic.nira.ini upgrade head
```

## Generating New Migrations

```bash
alembic -c alembic.core.ini revision --autogenerate -m "description"
alembic -c alembic.jcrawler.ini revision --autogenerate -m "description"
```
