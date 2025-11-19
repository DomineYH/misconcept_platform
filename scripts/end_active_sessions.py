import asyncio
import sys
import os
from datetime import datetime, timezone

# Add project root to Python path
sys.path.append(os.getcwd())

from sqlalchemy import select, update
from src.db.connection import AsyncSessionLocal
from src.models import Session

async def end_all_active_sessions():
    async with AsyncSessionLocal() as db:
        # Find active sessions
        stmt = select(Session).where(Session.ended_at.is_(None))
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        
        count = len(sessions)
        if count == 0:
            print("No active sessions to end.")
            return

        print(f"Found {count} active sessions. Ending them now...")

        # Update ended_at to current UTC time
        now = datetime.now(timezone.utc)
        update_stmt = (
            update(Session)
            .where(Session.ended_at.is_(None))
            .values(ended_at=now)
        )
        
        await db.execute(update_stmt)
        await db.commit()
        
        print(f"Successfully ended {count} sessions.")

if __name__ == "__main__":
    asyncio.run(end_all_active_sessions())
