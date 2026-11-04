import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_pg():
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://trader:traderpassword@localhost:5432/trading_db")
    print(f"Connecting to database: {db_url}")
    try:
        engine = create_async_engine(db_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.fetchone()
            print("SUCCESS! PostgreSQL Connected:")
            print(f"Version: {row[0]}")
        await engine.dispose()
    except Exception as e:
        print(f"FAILED to connect to PostgreSQL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_pg())

