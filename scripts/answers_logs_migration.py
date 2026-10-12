"""Inspect or apply only revision 0060 using the Railway MySQL public URL."""

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = os.environ.get("MYSQL_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        raise SystemExit("MYSQL_PUBLIC_URL or DATABASE_URL is required")
    url = make_url(raw).set(drivername="mysql+pymysql")
    engine = create_engine(url)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        exists = inspect(connection).has_table("answers_logs")
    print(f"Current revision: {revision}; answers_logs exists: {exists}")
    if args.apply:
        if revision != "0059":
            raise SystemExit("Expected revision 0059; refusing to apply unrelated pending migrations")
        root = Path(__file__).resolve().parents[1]
        os.environ["DATABASE_URL"] = url.set(drivername="mysql+asyncmy").render_as_string(hide_password=False)
        config = Config(str(root / "alembic.core.ini"))
        config.set_main_option("script_location", str(root / "migrations/core"))
        command.upgrade(config, "0060")
        with engine.connect() as connection:
            print("Verified revision:", connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())
            print("Verified columns:", ", ".join(column["name"] for column in inspect(connection).get_columns("answers_logs")))
    engine.dispose()


if __name__ == "__main__":
    main()
