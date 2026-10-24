from unittest.mock import AsyncMock, Mock

import pytest

from scaffold.ats_cadence import collection_interval
from scaffold.repositories.ats_collection_repository import AtsCollectionRepository


@pytest.mark.parametrize("configured,expected", [
    (None, 86400), (0, 86400), (60, 21600), (21600, 21600),
    (43200, 43200), (86400, 86400), (345600, 345600), (999999, 604800),
])
def test_daily_fallback_and_explicit_provider_schedules(configured, expected):
    assert collection_interval(configured) == expected


@pytest.mark.parametrize("configured,expected", [(None, 86400), (21600, 21600), (43200, 43200)])
async def test_repository_preserves_short_provider_schedule(configured, expected):
    session = AsyncMock()
    session.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=configured))
    assert await AtsCollectionRepository().interval(session, provider_id=1) == expected
