import asyncio

from sqlalchemy import text

import app.models  # noqa: F401  register all models
from app.db.base import Base
from app.db.session import engine


async def reset() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


asyncio.run(reset())
print("Database reset complete")