"""Check current onboard flow version.

Run: uv run python -m scripts.check_onboard_flow
"""
import asyncio

from sqlalchemy import text
from scaffold.db.session import close_engine, get_session_factory


async def check():
    async with get_session_factory()() as session:
        result = await session.execute(
            text("SELECT id, flow_key, version, active FROM onboard_flows ORDER BY version DESC LIMIT 5")
        )
        rows = result.fetchall()
        
        print("Current onboard flows:")
        for row in rows:
            print(f"  id={row[0]} flow_key={row[1]} version={row[2]} active={row[3]}")


async def main():
    try:
        await check()
    finally:
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
