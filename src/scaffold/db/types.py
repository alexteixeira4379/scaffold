from __future__ import annotations

from enum import Enum, StrEnum

from sqlalchemy import text
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.sql.elements import TextClause

from scaffold.constants.schema_enums import members


def mysql_enum(py_enum: type[StrEnum], mysql_name: str) -> ENUM:
    vals = members(py_enum)
    return ENUM(*vals, name=mysql_name, native_enum=True)


def mysql_default(_mysql_name: str, member: Enum) -> TextClause:
    v = str(member.value).replace("'", "''")
    return text(f"'{v}'")
