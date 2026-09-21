"""Receipts and optimistic checks belong to the domain transaction.

The caller must lock its owning candidate/resource before using this helper.
The mutation and its receipt commit together; transport retries return the receipt.
"""

from hashlib import sha256
import json
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Column, JSON, MetaData, String, Table, insert, select

receipts = Table(
    "assistant_command_receipts",
    MetaData(),
    Column("id", String(64), primary_key=True),
    Column("candidate_id", BigInteger, nullable=False),
    Column("service", String(48), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("result", JSON, nullable=False),
)


def fingerprint(value: Any) -> str:
    return sha256(
        json.dumps(
            jsonable_encoder(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9:_-]+$")
    action: str = Field(min_length=1, max_length=64)
    resource_id: int | None = Field(default=None, gt=0)
    expected: str = Field(min_length=64, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


async def previous_result(session, candidate_id, service, command):
    key = fingerprint([service, candidate_id, command.operation_id])
    row = (await session.execute(select(receipts).where(receipts.c.id == key))).mappings().first()
    if row:
        if row["request_hash"] != fingerprint(command.model_dump()):
            raise HTTPException(409, "Esta operação já foi utilizada com outro conteúdo.")
        return row["result"]
    return None


def check_snapshot(command, current):
    if command.expected != fingerprint(current):
        raise HTTPException(409, "Os dados mudaram. Revise uma nova proposta antes de aplicar.")


async def save_receipt(session, candidate_id, service, command, result):
    result = jsonable_encoder(result)
    await session.execute(
        insert(receipts).values(
            id=fingerprint([service, candidate_id, command.operation_id]),
            candidate_id=candidate_id,
            service=service,
            request_hash=fingerprint(command.model_dump()),
            result=result,
        )
    )
    return result
