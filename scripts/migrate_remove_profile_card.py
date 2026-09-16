"""One-time: remove completion_presentation from confirm_professional_brief.

Run: uv run python -m scripts.migrate_remove_profile_card
"""
import asyncio
import json

from sqlalchemy import select, text
from scaffold.db.session import close_engine, get_session_factory


async def migrate():
    async with get_session_factory()() as session:
        # Use raw SQL to avoid model dependency
        result = await session.execute(
            text("SELECT id, options FROM resume_build_steps WHERE step_key = 'confirm_professional_brief'")
        )
        row = result.fetchone()
        
        if row is None:
            print("Step confirm_professional_brief not found")
            return
        
        step_id, options_json = row
        options = json.loads(options_json) if options_json else {}
        
        if "completion_presentation" in options:
            del options["completion_presentation"]
            await session.execute(
                text("UPDATE resume_build_steps SET options = :options WHERE id = :id"),
                {"options": json.dumps(options), "id": step_id}
            )
            await session.commit()
            print("✓ Removed completion_presentation from confirm_professional_brief")
        else:
            print("completion_presentation already removed")


async def main():
    try:
        await migrate()
    finally:
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
