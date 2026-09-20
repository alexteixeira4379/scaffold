"""Dialect variants for the additive 0040 schema; SQLite stays usable in tests."""

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

DATETIME_6 = DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), "mysql")
UNSIGNED_REVISION = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
IDENTITY_CHANNEL = String(16).with_variant(mysql.ENUM("email", "whatsapp"), "mysql")
NOTIFICATION_CHANNEL = String(16).with_variant(mysql.ENUM("email", "whatsapp"), "mysql")
IDENTITY_VALUE = String(320).with_variant(
    mysql.VARCHAR(320, charset="utf8mb4", collation="utf8mb4_bin"), "mysql"
)
NOTIFICATION_TOPIC = String(64).with_variant(
    mysql.VARCHAR(64, charset="ascii", collation="ascii_bin"), "mysql"
)


class CurrentTimestamp6(FunctionElement):
    type = DateTime()
    inherit_cache = True


@compiles(CurrentTimestamp6)
def timestamp_default(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"


@compiles(CurrentTimestamp6, "mysql")
def timestamp_mysql(element, compiler, **kw):
    return "CURRENT_TIMESTAMP(6)"


def mysql_ddl_only(compiler):
    # SQLAlchemy's Table.to_metadata copies _create_rule, but not ddl_if.
    # Preserve the same MySQL-only CHECK when fixtures clone the metadata.
    return compiler.dialect.name == "mysql"
