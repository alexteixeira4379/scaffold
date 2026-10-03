"""Exercise retirement against a real SQL database with unrelated records."""
import importlib.util
from pathlib import Path

from sqlalchemy import Column, ForeignKey, Integer, JSON, MetaData, String, Table, create_engine, insert

spec = importlib.util.spec_from_file_location("retirement", Path(__file__).parents[1] / "scripts/retire_lever.py")
retirement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retirement)


def test_cleanup_follows_foreign_keys_and_non_fk_references_only():
    engine = create_engine("sqlite://")
    metadata = MetaData()

    def table(name, *columns):
        return Table(name, metadata, Column("id", Integer, primary_key=True), *columns)

    providers = table("ats_providers", Column("code", String), Column("base_url", String))
    jobs = table("jobs", Column("ats_provider_id", Integer), Column("canonical_url", String))
    matches = table("job_matches", Column("job_id", ForeignKey("jobs.id")))
    applications = table("job_applications", Column("job_match_id", ForeignKey("job_matches.id")))
    runs = table("application_runs", Column("job_application_id", ForeignKey("job_applications.id")))
    steps = table("application_steps", Column("application_run_id", ForeignKey("application_runs.id")))
    executions = table("ats_executions", Column("job_id", Integer))
    outbox = table("domain_outbox", Column("payload", JSON))
    projections = table("domain_projections", Column("aggregate", String), Column("data", JSON))
    for name in ["ats_discovery_sources", "ats_provider_configs", "ats_provider_domains",
                 "ats_provider_rules", "ats_provider_schedules"]:
        table(name, Column("ats_provider_id", Integer))
    for name in ["ats_discovery_prospects", "ats_discovery_observations", "ats_discovery_search_runs"]:
        table(name, Column("provider", String), Column("url", String), Column("config", JSON))
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.connection.driver_connection.create_function("SUBSTRING_INDEX", 3,
            lambda value, delimiter, count: delimiter.join((value or "").split(delimiter)[:count]
            if count > 0 else (value or "").split(delimiter)[count:]))
        conn.execute(insert(providers), [{"id": 1, "code": "lever"}, {"id": 2, "code": "greenhouse"}])
        conn.execute(insert(jobs), [{"id": 11, "ats_provider_id": 1, "canonical_url": "https://jobs.lever.co/acme/1"},
            {"id": 12, "ats_provider_id": 2, "canonical_url": "https://boards.greenhouse.io/acme/jobs/2"},
            {"id": 13, "ats_provider_id": None, "canonical_url": "https://jobs.eu.lever.co/acme/3"}])
        for t, column, first, second in [(matches, "job_id", 11, 12),
            (applications, "job_match_id", 1, 2), (runs, "job_application_id", 1, 2),
            (steps, "application_run_id", 1, 2), (executions, "job_id", 11, 12)]:
            conn.execute(insert(t), [{"id": 1, column: first}, {"id": 2, column: second}])
        conn.execute(insert(outbox), [{"id": 1, "payload": {"job": {"id": 11}}},
            {"id": 2, "payload": {"job": {"id": 12}}}, {"id": 3, "payload": {"candidate": {"id": 11}}}])
        conn.execute(insert(projections), [{"id": 1, "aggregate": "job:11", "data": {}},
            {"id": 2, "aggregate": "candidate:11", "data": {}}])
        selected, controls = retirement.collect(conn, metadata)
        assert {r["id"] for r in selected["jobs"]} == {11, 13}
        assert controls["ats_providers"][0]["code"] == "lever"
        for t in [matches, applications, runs, steps, executions, outbox, projections]:
            assert [r["id"] for r in selected[t.name]] == [1]
        for t in reversed(metadata.sorted_tables):
            if selected.get(t.name):
                conn.execute(t.delete().where(retirement.row_filter(t, selected[t.name])))
        assert [r.id for r in conn.execute(jobs.select())] == [12]
        assert [r.id for r in conn.execute(outbox.select())] == [2, 3]
        assert [r.id for r in conn.execute(providers.select())] == [1, 2]
