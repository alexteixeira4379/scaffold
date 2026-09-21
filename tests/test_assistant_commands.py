import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from scaffold.assistant.commands import (
    Command,
    fingerprint,
    previous_result,
    save_receipt,
    receipts,
    check_snapshot,
)


async def test_receipt_is_atomic_and_scoped(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/receipts.db")
    async with engine.begin() as connection:
        await connection.run_sync(receipts.metadata.create_all)
    sessions = async_sessionmaker(engine)
    command = Command(
        operation_id="test-operation-0001",
        action="profile.update",
        expected=fingerprint({"name": "old"}),
        payload={"name": "new"},
    )
    async with sessions() as session:
        await save_receipt(session, 1, "candidate-api", command, {"status": "applied"})
        await session.rollback()
    async with sessions() as session, session.begin():
        assert await previous_result(session, 1, "candidate-api", command) is None
        await save_receipt(session, 1, "candidate-api", command, {"status": "applied"})
    async with sessions() as session:
        assert await previous_result(session, 1, "candidate-api", command) == {"status": "applied"}
        assert await previous_result(session, 2, "candidate-api", command) is None
        assert await previous_result(session, 1, "other-api", command) is None
        with pytest.raises(HTTPException) as error:
            await previous_result(
                session,
                1,
                "candidate-api",
                command.model_copy(update={"payload": {"name": "different"}}),
            )
        assert error.value.status_code == 409
    check_snapshot(command, {"name": "old"})
    with pytest.raises(HTTPException):
        check_snapshot(command, {"name": "newer manual edit"})
    await engine.dispose()
