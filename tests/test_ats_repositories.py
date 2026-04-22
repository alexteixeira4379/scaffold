from sqlalchemy import select
from sqlalchemy.dialects import mysql

from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource
from scaffold.repositories.ats_repositories import _last_collected_at_order_by


def test_last_collected_at_order_by_compiles_without_nulls_first_for_mysql() -> None:
    stmt = select(AtsDiscoverySource).order_by(*_last_collected_at_order_by())

    compiled = str(stmt.compile(dialect=mysql.dialect()))

    assert "NULLS FIRST" not in compiled
    assert "CASE WHEN (ats_discovery_sources.last_collected_at IS NULL)" in compiled
    assert "ats_discovery_sources.last_collected_at ASC" in compiled
    assert "ats_discovery_sources.code" in compiled
